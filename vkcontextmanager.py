# Making Vulkan Initialization Exception Safe 
# Copyright (C) 2016 by VLAM3D Software inc. https://www.vlam3d.com
# This code is licensed under the MIT license (MIT) (http://opensource.org/licenses/MIT)
from __future__ import print_function
import os
import pyvulkan as vk
import pyglslang
from PIL import Image
import numpy as np
from contextlib2 import contextmanager,ExitStack
from transforms import *
from glsl_to_spv import *
from cube_data import *

class MappedMemoryWrapper:
    def __init__(self, obj):
        self.mem = obj
    def unmap(self):
        del self.mem

@contextmanager
def vkunmapping(vkmappedmem):
    try:
        mapped_mem_wrapper = MappedMemoryWrapper(vkmappedmem)
        yield mapped_mem_wrapper
    finally:
        mapped_mem_wrapper.unmap()            
    
@contextmanager
def vkreleasing(vkcreatedobj):
    assert(hasattr(vkcreatedobj,'this'))
    try:        
        yield vkcreatedobj  
    finally:
        del vkcreatedobj.this

# http://stackoverflow.com/questions/2169478/how-to-make-a-checkerboard-in-numpy
def check(w, h, c0, c1, blocksize):    
    tile = np.array([[c0,c1],[c1,c0]]).repeat(blocksize, axis=0).repeat(blocksize, axis=1)
    grid = np.tile(tile, ( int(h/(2*blocksize))+1, int(w/(2*blocksize))+1) )
    return grid[:h,:w]

# ported from the Lunar SDK 
def memory_type_from_properties(physicalDevice, memoryTypeBits, properties):
    # Search memtypes to find first index with those properties
    memory_props = vk.getPhysicalDeviceMemoryProperties(physicalDevice)
    for i,mt in enumerate(memory_props.memoryTypes):        
        if memoryTypeBits & 1 == 1:
            # Type is available, does it match user properties?
            if (mt.propertyFlags & properties) == properties:
                return i
        
        memoryTypeBits = memoryTypeBits >> 1

    return None  

def delete_this(obj):
    del obj.this

class VkContextManager:
    # Acronym for ExitStack Push to reduce the clutter
    # push a destructor for the refcounted handle wrapper on the ExitStack that will be called in unwinding order in __exit__
    def ESP(self, obj):
        try:
            self.stack.callback(delete_this, obj)
        except IndexError as e:
            print(e.message)            
        except:
            pass
        return obj

    def init_global_layer_properties(self):
        self.instance_layer_properties = []
        layer_properties = vk.enumerateInstanceLayerProperties()
        assert(layer_properties is not None)
        for lp in layer_properties:
            ext_props = vk.enumerateInstanceExtensionProperties(lp.layerName)
            assert(ext_props is not None)
            self.instance_layer_properties.extend(ext_props)  

    def init_instance(self):
        self.instance_ext_names = [vk.VK_KHR_SURFACE_EXTENSION_NAME, vk.VK_EXT_DEBUG_REPORT_EXTENSION_NAME]        
        if self.surface_type == VkContextManager.VKC_WIN32:
            self.instance_ext_names.append(vk.VK_KHR_WIN32_SURFACE_EXTENSION_NAME)
        app = vk.ApplicationInfo("foo", 1, "bar", 1, vk.makeVersion(1,0,3))
        assert(app is not None)
        instance_create_info = vk.InstanceCreateInfo(0, app, ['VK_LAYER_LUNARG_standard_validation'], self.instance_ext_names)
        self.instance = self.ESP( vk.createInstance(instance_create_info) )
        vk.load_vulkan_fct_ptrs(self.instance)
        full_degug = vk.VK_DEBUG_REPORT_ERROR_BIT_EXT | vk.VK_DEBUG_REPORT_WARNING_BIT_EXT | vk.VK_DEBUG_REPORT_PERFORMANCE_WARNING_BIT_EXT
        errors_only = vk.VK_DEBUG_REPORT_ERROR_BIT_EXT
        nothing = 0
        # even when setting any error reporting this tests that the functions pointers are correctly loaded
        self.error_reporting = self.ESP(vk.install_stdout_error_reporting(self.instance,full_degug))
        assert(self.instance is not None)

    def init_enumerate_device(self):
        self.physical_devices = vk.enumeratePhysicalDevices(self.instance)
        self.memory_properties = vk.getPhysicalDeviceMemoryProperties(self.physical_devices[0])
        self.gpu_props = vk.getPhysicalDeviceProperties(self.physical_devices[0])

    def init_device(self):
        self.device_extension_names = [vk.VK_KHR_SWAPCHAIN_EXTENSION_NAME]        
        queue_props = vk.getPhysicalDeviceQueueFamilyProperties(self.physical_devices[0])
        graphic_queues_indices = [ i for i,qp in enumerate(queue_props) if qp.queueFlags & vk.VK_QUEUE_GRAPHICS_BIT]
        self.device_queue_index = graphic_queues_indices[0]
        dev_queue_ci = vk.DeviceQueueCreateInfo(0, self.device_queue_index, vk.floatVector(1,0.0))
        vec_dev_queue_ci = vk.VkDeviceQueueCreateInfoVector()
        vec_dev_queue_ci.append(dev_queue_ci)
        device_ci = vk.DeviceCreateInfo(0, vec_dev_queue_ci, [], self.device_extension_names, None)
        self.device = self.ESP( vk.createDevice(self.physical_devices[0], device_ci) )    
        assert(self.device is not None)
       
    def delete_window(self):
        self.widget = None

    def init_window(self):   
        from PyQt4.QtGui import QWidget
        self.widget = QWidget()
        self.widget.resize(self.output_size[0], self.output_size[1])
        self.stack.callback(self.delete_window)   
        
    def init_graphic_queue(self):
        # test that we can find a queue with the graphics bit and that can present
        queue_props = vk.getPhysicalDeviceQueueFamilyProperties(self.physical_devices[0])

        support_present = []        
        if self.surface is not None:        
            for i in range(0,len(queue_props)):
                support_present.append( vk.getPhysicalDeviceSurfaceSupportKHR(self.physical_devices[0], i, self.surface) != 0)
        else:
            support_present = [True for i in range(0,len(queue_props))]

        graphic_queues_indices = [ i for i,qp in enumerate(queue_props) if qp.queueFlags & vk.VK_QUEUE_GRAPHICS_BIT and support_present[i] ]
        assert(len(graphic_queues_indices)>=1)
        self.graphics_queue_family_index = graphic_queues_indices[0]
        
    def init_win32_swap_chain_ext(self):
        surface_ci = vk.Win32SurfaceCreateInfoKHR(0, vk.GetThisEXEModuleHandle(), self.widget.winId())       
        self.surface = self.ESP( vk.createWin32SurfaceKHR(self.instance, surface_ci) )
        assert(self.surface is not None)

        self.init_graphic_queue()
               
        surface_formats = vk.getPhysicalDeviceSurfaceFormatsKHR(self.physical_devices[0], self.surface)
        B8G8R8A8_format_found = False
        self.format = None
        self.color_space = None
        for f in surface_formats:
            # from LunarSDK samples and Sascha Willems samples this format seems to be a good default
            if f.format == vk.VK_FORMAT_B8G8R8A8_UNORM:
                B8G8R8A8_format_found = True
                self.format = f.format
                self.color_space = f.colorSpace
                break

        assert(B8G8R8A8_format_found)

    def init_without_surface(self):
        self.format = vk.VK_FORMAT_R8G8B8A8_UNORM
        self.color_space = None # not required without surface and swap chain
        self.surface = None # not required
        self.init_graphic_queue()

    def init_command_buffers(self):
        self.command_pool = self.ESP( vk.createCommandPool(self.device, vk.CommandPoolCreateInfo(vk.VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, self.graphics_queue_family_index)) )
        cbai = vk.CommandBufferAllocateInfo(self.command_pool, vk.VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1)
        self.command_buffers = self.ESP( vk.allocateCommandBuffers(self.device, cbai) )
        assert(self.command_buffers is not None)
        vk.beginCommandBuffer(self.command_buffers[0], vk.CommandBufferBeginInfo(0,None))

    def init_device_queue(self):
        self.device_queue = vk.getDeviceQueue(self.device, self.graphics_queue_family_index, 0)

    def init_swap_chain(self):
        assert(self.surface_type != VkContextManager.VKC_OFFSCREEN and self.surface is not None)
        present_modes = vk.getPhysicalDeviceSurfacePresentModesKHR(self.physical_devices[0], self.surface)
        present_mode = vk.VK_PRESENT_MODE_FIFO_KHR
        for pm in present_modes:
            if pm == vk.VK_PRESENT_MODE_MAILBOX_KHR:
                present_mode = pm
        surface_caps = vk.getPhysicalDeviceSurfaceCapabilitiesKHR(self.physical_devices[0], self.surface)
        req_image_count = surface_caps.minImageCount + 1
        if surface_caps.maxImageCount > 0 and req_image_count > surface_caps.maxImageCount:
            req_image_count = surface_caps.maxImageCount

        pre_transform = surface_caps.currentTransform
        if surface_caps.supportedTransforms & vk.VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR:
            pre_transform = vk.VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR

        swp_ci = vk.SwapchainCreateInfoKHR(0, 
                                           self.surface, 
                                           req_image_count, 
                                           self.format,
                                           self.color_space, 
                                           surface_caps.currentExtent, # image extent
                                           1, # image array layers
                                           vk.VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | vk.VK_IMAGE_USAGE_TRANSFER_DST_BIT , # image usage
                                           vk.VK_SHARING_MODE_EXCLUSIVE, # image sharing mode
                                           [], 
                                           pre_transform, 
                                           vk.VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR, # composite  alpha, 
                                           present_mode, # present mode
                                           True, # clipped
                                           None) # old_swp_chain
        
        self.swap_chain = self.ESP( vk.createSwapchainKHR(self.device, swp_ci) )
        self.images = vk.getSwapchainImagesKHR(self.device, self.swap_chain)
        components = vk.ComponentMapping(vk.VK_COMPONENT_SWIZZLE_R, vk.VK_COMPONENT_SWIZZLE_G, vk.VK_COMPONENT_SWIZZLE_B, vk.VK_COMPONENT_SWIZZLE_A)
        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
        self.image_views = []
        for img in self.images:
            subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
            ivci = vk.ImageViewCreateInfo(0, img, vk.VK_IMAGE_VIEW_TYPE_2D, self.format, components, subresource_range)            
            self.image_views.append( self.ESP(vk.createImageView(self.device, ivci)) )

    def init_ouput_images(self):
        self.swap_chain = None        
        w,h = self.get_surface_extent()
        ici = vk.ImageCreateInfo(   0, 
                                    vk.VK_IMAGE_TYPE_2D, 
                                    self.format, # the output format
                                    vk.Extent3D(w,h,1),
                                    1, 
                                    1, 
                                    vk.VK_SAMPLE_COUNT_1_BIT, 
                                    vk.VK_IMAGE_TILING_OPTIMAL, 
                                    vk.VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|vk.VK_IMAGE_USAGE_TRANSFER_SRC_BIT,
                                    vk.VK_SHARING_MODE_EXCLUSIVE, 
                                    [], 
                                    vk.VK_IMAGE_LAYOUT_UNDEFINED)

        self.offscreen_output_image =  self.ESP( vk.createImage(self.device, ici) )
        mem_reqs = vk.getImageMemoryRequirements(self.device, self.offscreen_output_image);
        
        mem_type_index = memory_type_from_properties(self.physical_devices[0], mem_reqs.memoryTypeBits, 0)
        assert(mem_type_index is not None)

        self.offscreen_output_image_men = self.ESP( vk.allocateMemory(self.device, vk.MemoryAllocateInfo(mem_reqs.size, mem_type_index) ) )
        vk.bindImageMemory(self.device, self.offscreen_output_image, self.offscreen_output_image_men, 0)

        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
        img_mem_barrier = vk.ImageMemoryBarrier(0, vk.VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT, vk.VK_IMAGE_LAYOUT_UNDEFINED, vk.VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, 0, 0, self.offscreen_output_image, subresource_range)

        vk.cmdPipelineBarrier(self.command_buffers[0], 
                              vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                              vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                              vk.VkMemoryBarrierVector(), 
                              vk.VkBufferMemoryBarrierVector(),
                              vk.VkImageMemoryBarrierVector(1,img_mem_barrier))

        components = vk.ComponentMapping(vk.VK_COMPONENT_SWIZZLE_R, vk.VK_COMPONENT_SWIZZLE_G, vk.VK_COMPONENT_SWIZZLE_B, vk.VK_COMPONENT_SWIZZLE_A)
        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)        
        self.offscreen_output_image_view = self.ESP( vk.createImageView(self.device, vk.ImageViewCreateInfo(0, self.offscreen_output_image, vk.VK_IMAGE_VIEW_TYPE_2D, self.format, components, subresource_range)) )
        self.images = [self.offscreen_output_image]
        self.image_views = [self.offscreen_output_image_view]

    def get_surface_extent(self):           
        if self.surface_type == VkContextManager.VKC_WIN32: 
            assert(self.surface is not None)
            surface_caps = vk.getPhysicalDeviceSurfaceCapabilitiesKHR(self.physical_devices[0], self.surface)
            return surface_caps.currentExtent.width, surface_caps.currentExtent.height
        
        return self.output_size[0],self.output_size[1]

    def init_depth_buffer(self):
        self.depth_format = vk.VK_FORMAT_D16_UNORM
        fp = vk.getPhysicalDeviceFormatProperties(self.physical_devices[0], self.depth_format)        
        tiling = 0        
        if fp.optimalTilingFeatures & vk.VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT:
            tiling = vk.VK_IMAGE_TILING_OPTIMAL
        elif fp.linearTilingFeatures & vk.VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT:
            tiling = vk.VK_IMAGE_TILING_LINEAR
        else:
            raise RuntimeError('VK_FORMAT_D16_UNORM not supported on this physical device')
        
        w,h = self.get_surface_extent()
        ici = vk.ImageCreateInfo(   0, 
                                    vk.VK_IMAGE_TYPE_2D, 
                                    self.depth_format,
                                    vk.Extent3D(w,h,1),
                                    1, 
                                    1, 
                                    vk.VK_SAMPLE_COUNT_1_BIT, 
                                    tiling, 
                                    vk.VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT,
                                    vk.VK_SHARING_MODE_EXCLUSIVE, 
                                    [], 
                                    vk.VK_IMAGE_LAYOUT_UNDEFINED)

        self.depth_image =  self.ESP( vk.createImage(self.device, ici) )
        mem_reqs = vk.getImageMemoryRequirements(self.device, self.depth_image);
        
        mem_type_index = memory_type_from_properties(self.physical_devices[0], mem_reqs.memoryTypeBits, 0)
        assert(mem_type_index is not None)

        self.depth_mem = self.ESP( vk.allocateMemory(self.device, vk.MemoryAllocateInfo(mem_reqs.size, mem_type_index) ) )
        vk.bindImageMemory(self.device, self.depth_image, self.depth_mem, 0)

        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_DEPTH_BIT, 0, 1, 0, 1)
        img_mem_barrier = vk.ImageMemoryBarrier(0, vk.VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT, vk.VK_IMAGE_LAYOUT_UNDEFINED, vk.VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL, 0, 0, self.depth_image, subresource_range)

        vk.cmdPipelineBarrier(self.command_buffers[0], 
                              vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                              vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                              vk.VkMemoryBarrierVector(), 
                              vk.VkBufferMemoryBarrierVector(),
                              vk.VkImageMemoryBarrierVector(1,img_mem_barrier))

        components = vk.ComponentMapping(vk.VK_COMPONENT_SWIZZLE_R, vk.VK_COMPONENT_SWIZZLE_G, vk.VK_COMPONENT_SWIZZLE_B, vk.VK_COMPONENT_SWIZZLE_A)
        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_DEPTH_BIT, 0, 1, 0, 1)
        self.depth_view = self.ESP( vk.createImageView(self.device, vk.ImageViewCreateInfo(0, self.depth_image, vk.VK_IMAGE_VIEW_TYPE_2D, self.depth_format, components, subresource_range)) )

    def init_image(self, texture_file_path = None):
        if texture_file_path is None or texture_file_path.empty() or not os.path.exists(texture_file_path):
            texture_file_path = 'lena_std.png'

        if not os.path.exists(texture_file_path):
            img_size = (640,480)
            self.img_array = check(img_size[0],img_size[1],0,255,32).astype(np.uint8)
            tex_format = vk.VK_FORMAT_R8_UNORM
        else:
            # awfully complex way to load an image and store it in a numpy array without getting a "unclosed file" warning
            # seems related to https://github.com/python-pillow/Pillow/issues/835
            with open(texture_file_path, 'rb') as img_file:
                with Image.open(img_file) as pil_img:
                    assert(pil_img.mode == 'RGBA') # for the unit test's purpose we don't need more
                    flat_array = np.fromstring( pil_img.tobytes(), dtype=np.uint8)
                    # note that we create a numpy array with width = 4 * image width to keep the color packed per pixel
                    # the default behavior of numpy.array(pil_img) would be to split the colors in planes, which is not what we want for a texture
                    img_size = pil_img.size
                    self.img_array = flat_array.reshape( (pil_img.height, pil_img.width*4) )
                    
            tex_format = vk.VK_FORMAT_R8G8B8A8_UNORM

        format_props = vk.getPhysicalDeviceFormatProperties(self.physical_devices[0], tex_format)
        need_staging = (format_props.linearTilingFeatures & vk.VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT) == 0
        if need_staging:
            usage = vk.VK_IMAGE_USAGE_TRANSFER_SRC_BIT
        else:
            usage = vk.VK_IMAGE_USAGE_SAMPLED_BIT

        ici = vk.ImageCreateInfo(   0, 
                                    vk.VK_IMAGE_TYPE_2D, 
                                    tex_format,
                                    vk.Extent3D(img_size[0],img_size[1],1),
                                    1, 
                                    1, 
                                    vk.VK_SAMPLE_COUNT_1_BIT, 
                                    vk.VK_IMAGE_TILING_LINEAR,
                                    usage,
                                    vk.VK_SHARING_MODE_EXCLUSIVE, 
                                    [], 
                                    vk.VK_IMAGE_LAYOUT_UNDEFINED)

        self.tex_image =  self.ESP( vk.createImage(self.device, ici) )
        mem_reqs = vk.getImageMemoryRequirements(self.device, self.tex_image);
        
        mem_type_index = memory_type_from_properties(self.physical_devices[0], mem_reqs.memoryTypeBits, vk.VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)
        assert(mem_type_index is not None)

        self.tex_mem = self.ESP( vk.allocateMemory(self.device, vk.MemoryAllocateInfo(mem_reqs.size, mem_type_index) ) )
        vk.bindImageMemory(self.device, self.tex_image, self.tex_mem, 0)

        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
        img_mem_barrier = vk.ImageMemoryBarrier(0, vk.VK_ACCESS_MEMORY_READ_BIT, vk.VK_IMAGE_LAYOUT_UNDEFINED, vk.VK_IMAGE_LAYOUT_GENERAL, 0, 0, self.tex_image, subresource_range)

        vk.cmdPipelineBarrier(self.command_buffers[0], 
                              vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                              vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                              vk.VkMemoryBarrierVector(), 
                              vk.VkBufferMemoryBarrierVector(),
                              vk.VkImageMemoryBarrierVector(1,img_mem_barrier))

        vk.endCommandBuffer(self.command_buffers[0])

        with vkreleasing( vk.createFence(self.device, vk.FenceCreateInfo(0)) ) as cmd_fence:
            submit_info_vec = vk.VkSubmitInfoVector()
            cmd_buf = vk.VkCommandBufferVector(1, self.command_buffers[0])        
            submit_info_vec.append( vk.SubmitInfo(vk.VkSemaphoreVector(), vk.VkFlagVector(), cmd_buf, vk.VkSemaphoreVector()) ) 
            vk.queueSubmit(self.device_queue, submit_info_vec, cmd_fence)
        
            layout = vk.getImageSubresourceLayout(self.device, self.tex_image, vk.ImageSubresource(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 0))

            command_buffer_finished = False
            cmd_fences = vk.VkFenceVector(1,cmd_fence)
            while not command_buffer_finished:
                try:
                    vk.waitForFences(self.device, cmd_fences, True, 1000000)
                    command_buffer_finished = True
                except RuntimeError:
                    pass

        # note that we pass the shape of the numpy array we want mapped, in this case the numpy array number of column is 4x the image width because colors are packed per pixel
        # layout.rowPitch could be different from width * sizeof(pixel format) that why it must be passed to mapMemory2D
        with vkunmapping( vk.mapMemory2D(self.device, self.tex_mem, 0, 0, np.dtype('ubyte').num, self.img_array.shape[1], self.img_array.shape[0], layout.rowPitch ) ) as mapped_array:
            assert(mapped_array.mem.strides[0] == layout.rowPitch)
            np.copyto(mapped_array.mem, self.img_array)

        vk.resetCommandBuffer(self.command_buffers[0], 0);
        vk.beginCommandBuffer(self.command_buffers[0], vk.CommandBufferBeginInfo(0,None))

        if not need_staging:
            subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
            img_mem_barrier = vk.ImageMemoryBarrier(vk.VK_ACCESS_MEMORY_READ_BIT, vk.VK_ACCESS_SHADER_READ_BIT, vk.VK_IMAGE_LAYOUT_GENERAL, vk.VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, 0, 0, self.tex_image, subresource_range)

            vk.cmdPipelineBarrier(self.command_buffers[0], 
                                  vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                                  vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                                  vk.VkMemoryBarrierVector(), 
                                  vk.VkBufferMemoryBarrierVector(),
                                  vk.VkImageMemoryBarrierVector(1,img_mem_barrier))

            self.dst_img = self.tex_image
        else:
            ###############################
            # !!! NOT CURRENTLY TESTED !!!
            ici.tiling = vk.VK_IMAGE_TILING_OPTIMAL
            ici.usage =  vk.VK_IMAGE_USAGE_TRANSFER_DST_BIT | vk.VK_IMAGE_USAGE_SAMPLED_BIT
            self.dst_img = self.ESP( vk.createImage(self.device, ici) )

            mem_reqs = vk.getImageMemoryRequirements(self.device, self.dst_img);
            mem_type_index = memory_type_from_properties(self.physical_devices[0], mem_reqs.memoryTypeBits, vk.VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)
            assert(mem_type_index is not None)

            self.dst_mem = self.ESP( vk.allocateMemory(self.device, vk.MemoryAllocateInfo(mem_reqs.size, mem_type_index) ) )
            vk.bindImageMemory(self.device, self.dst_img, self.dst_mem, 0)

            subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
            img_mem_barrier = vk.ImageMemoryBarrier(vk.VK_ACCESS_MEMORY_READ_BIT, vk.VK_ACCESS_MEMORY_WRITE_BIT, vk.VK_IMAGE_LAYOUT_GENERAL, vk.VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, 0, 0, self.tex_image, subresource_range)

            vk.cmdPipelineBarrier(self.command_buffers[0], 
                                  vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                                  vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                                  vk.VkMemoryBarrierVector(), 
                                  vk.VkBufferMemoryBarrierVector(),
                                  vk.VkImageMemoryBarrierVector(1,img_mem_barrier))

            subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
            img_mem_barrier = vk.ImageMemoryBarrier(0, vk.VK_ACCESS_MEMORY_WRITE_BIT, old_image_layout, vk.VK_IMAGE_LAYOUT_UNDEFINED, vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 0, 0, self.dst_img, subresource_range)

            vk.cmdPipelineBarrier(self.command_buffers[0], 
                                  vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                                  vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                                  vk.VkMemoryBarrierVector(), 
                                  vk.VkBufferMemoryBarrierVector(),
                                  vk.VkImageMemoryBarrierVector(1,img_mem_barrier))
            
            copy_regions = vk.VkImageCopyVector(1,vk.ImageCopy(vk.ImageSubresourceLayers(vk.VK_IMAGE_ASPECT_COLOR_BIT,0,0,1),vk.Offset3D(0,0,0), 
                                                               vk.ImageSubresourceLayers(vk.VK_IMAGE_ASPECT_COLOR_BIT,0,0,1),vk.Offset3D(0,0,0), vk.Extent3D(img_size[0],img_size[1],1)))
            vk.cmdCopyImage(self.command_buffers[0], self.tex_image, vk.VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, self.dst_img, vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, copy_regions)

            subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
            img_mem_barrier = vk.ImageMemoryBarrier(vk.VK_ACCESS_MEMORY_WRITE_BIT, vk.VK_ACCESS_MEMORY_READ_BIT, vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, vk.VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, 0, 0, self.dst_img, subresource_range)

            vk.cmdPipelineBarrier(self.command_buffers[0], 
                                  vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                                  vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                                  vk.VkMemoryBarrierVector(), 
                                  vk.VkBufferMemoryBarrierVector(),
                                  vk.VkImageMemoryBarrierVector(1,img_mem_barrier))
            ## End not tested section
            ###############################

        components = vk.ComponentMapping(vk.VK_COMPONENT_SWIZZLE_R, vk.VK_COMPONENT_SWIZZLE_G, vk.VK_COMPONENT_SWIZZLE_B, vk.VK_COMPONENT_SWIZZLE_A)
        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
        ivci = vk.ImageViewCreateInfo(0, self.dst_img, vk.VK_IMAGE_VIEW_TYPE_2D, tex_format, components, subresource_range)
        self.tex_img_view = self.ESP(vk.createImageView(self.device, ivci)) 

    def init_sampler(self):
        self.sampler = self.ESP( vk.createSampler(self.device, vk.SamplerCreateInfo(0, 
                                                                                    vk.VK_FILTER_NEAREST, 
                                                                                    vk.VK_FILTER_NEAREST, 
                                                                                    vk.VK_SAMPLER_MIPMAP_MODE_NEAREST, 
                                                                                    vk.VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                                                                                    vk.VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                                                                                    vk.VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                                                                                    0.0, 
                                                                                    False, 
                                                                                    0,
                                                                                    False,
                                                                                    vk.VK_COMPARE_OP_NEVER,
                                                                                    0.0,
                                                                                    0.0,
                                                                                    vk.VK_BORDER_COLOR_FLOAT_OPAQUE_WHITE,
                                                                                    False)))

    def init_uniform_buffer(self):
        P = np.matrix( perspective(45.0, 1.0, 0.1, 100.0) )
        V = np.matrix( look_at( np.array([5, 3, 10]), np.array([0, 0, 0]), np.array([0, -1, 0]) ) )
        M = np.matrix( np.eye(4) )
        MVP = (M * V * P).astype(np.single)

        self.uniform_buffer = self.ESP( vk.createBuffer(self.device, vk.BufferCreateInfo(0, MVP.nbytes, vk.VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT, vk.VK_SHARING_MODE_EXCLUSIVE, [])) )
        self.uniform_buffer_bytes = MVP.nbytes

        mem_reqs = vk.getBufferMemoryRequirements(self.device, self.uniform_buffer)
        memory_type_index = memory_type_from_properties(self.physical_devices[0], mem_reqs.memoryTypeBits, vk.VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)
        self.uniform_buffer_mem = self.ESP( vk.allocateMemory(self.device, vk.MemoryAllocateInfo(mem_reqs.size, memory_type_index)) )
        with vkunmapping( vk.mapMemory(self.device, self.uniform_buffer_mem , 0, mem_reqs.size, 0) ) as mapped_array:
            np.copyto(np.frombuffer(mapped_array.mem, dtype=np.single, count=len(MVP.flat)), MVP.flat)

        vk.bindBufferMemory(self.device, self.uniform_buffer, self.uniform_buffer_mem, 0)

    def init_descriptor_and_pipeline_layouts(self):
        layout_bindings = vk.VkDescriptorSetLayoutBindingVector()
        layout_bindings.append( vk.DescriptorSetLayoutBinding(0, vk.VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, 1, vk.VK_SHADER_STAGE_VERTEX_BIT, vk.VkSamplerVector()) )
        layout_bindings.append( vk.DescriptorSetLayoutBinding(1, vk.VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1, vk.VK_SHADER_STAGE_FRAGMENT_BIT, vk.VkSamplerVector()) )
        self.desc_layout = self.ESP(vk.createDescriptorSetLayout(self.device, vk.DescriptorSetLayoutCreateInfo(0, layout_bindings)))
        self.pipeline_layout = self.ESP(vk.createPipelineLayout(self.device, vk.PipelineLayoutCreateInfo(0, vk.VkDescriptorSetLayoutVector(1,self.desc_layout), vk.VkPushConstantRangeVector())))

    def init_render_pass(self,clear):
        if clear:
            loadOp = vk.VK_ATTACHMENT_LOAD_OP_CLEAR
        else:
            loadOp = vk.VK_ATTACHMENT_LOAD_OP_DONT_CARE

        if self.surface_type == VkContextManager.VKC_OFFSCREEN:
            initial_layout = vk.VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL
        else:
            initial_layout = vk.VK_IMAGE_LAYOUT_UNDEFINED

        attachments = vk.VkAttachmentDescriptionVector()        
        attachments.append( vk.AttachmentDescription(0, self.format, 
                                                        vk.VK_SAMPLE_COUNT_1_BIT, 
                                                        loadOp,  
                                                        vk.VK_ATTACHMENT_STORE_OP_STORE, 
                                                        vk.VK_ATTACHMENT_LOAD_OP_DONT_CARE, 
                                                        vk.VK_ATTACHMENT_STORE_OP_DONT_CARE, 
                                                        initial_layout,
                                                        vk.VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL) )

        attachments.append( vk.AttachmentDescription(0, self.depth_format, 
                                                        vk.VK_SAMPLE_COUNT_1_BIT, 
                                                        loadOp,  
                                                        vk.VK_ATTACHMENT_STORE_OP_STORE, 
                                                        vk.VK_ATTACHMENT_LOAD_OP_LOAD,
                                                        vk.VK_ATTACHMENT_STORE_OP_STORE, 
                                                        vk.VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL,
                                                        vk.VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL) )

        color_attachments = vk.VkAttachmentReferenceVector(1,vk.AttachmentReference(0,vk.VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL))
        depth_attachment = vk.AttachmentReference(1,vk.VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL)
        
        subpasses = vk.VkSubpassDescriptionVector()
        subpasses.append(  vk.SubpassDescription(0, vk.VK_PIPELINE_BIND_POINT_GRAPHICS, vk.VkAttachmentReferenceVector(), color_attachments, vk.VkAttachmentReferenceVector(), depth_attachment, []) )
        self.render_pass = self.ESP( vk.createRenderPass(self.device, vk.RenderPassCreateInfo(0, attachments, subpasses, vk.VkSubpassDependencyVector())) )

    def init_shaders(self, vertex_shader_text, frag_shader_text):
        if vertex_shader_text is not None and len(vertex_shader_text) > 0:
            spv = glsl_to_spv(pyglslang.EShLangVertex, vertex_shader_text)
            self.vertex_shader = self.ESP( vk.createShaderModule(self.device, vk.ShaderModuleCreateInfo(0, spv)) )
        if frag_shader_text is not None and len(frag_shader_text) > 0:
            spv = glsl_to_spv(pyglslang.EShLangFragment, frag_shader_text)
            self.fragment_shader = self.ESP( vk.createShaderModule(self.device, vk.ShaderModuleCreateInfo(0, spv)) )

    def init_framebuffer(self):
        w,h = self.get_surface_extent()
        self.framebuffers = []
        for img_view in self.image_views:
            attachments = vk.VkImageViewVector()
            attachments.append(img_view)
            attachments.append(self.depth_view)        
            self.framebuffers.append( self.ESP( vk.createFramebuffer(self.device, vk.FramebufferCreateInfo(0, self.render_pass, attachments, w, h, 1)) ) )            

    def init_vertex_buffer(self, coords):
        self.vertex_buffer = self.ESP(vk.createBuffer( self.device, vk.BufferCreateInfo(0, coords.nbytes, vk.VK_BUFFER_USAGE_VERTEX_BUFFER_BIT, vk.VK_SHARING_MODE_EXCLUSIVE, [])))
        mem_reqs = vk.getBufferMemoryRequirements(self.device, self.vertex_buffer)
        memory_type_index = memory_type_from_properties(self.physical_devices[0], mem_reqs.memoryTypeBits, vk.VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|vk.VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)
        self.vertex_buffer_mem = self.ESP( vk.allocateMemory(self.device, vk.MemoryAllocateInfo(mem_reqs.size, memory_type_index)) )
        with vkunmapping( vk.mapMemory(self.device, self.vertex_buffer_mem , 0, mem_reqs.size, 0) ) as mapped_array:
            np.copyto(np.frombuffer(mapped_array.mem,dtype=np.single, count=len(coords.flat)), coords.flat)

        vk.bindBufferMemory(self.device, self.vertex_buffer, self.vertex_buffer_mem, 0)

    def init_descriptor_pool(self):
        pool_sizes = vk.VkDescriptorPoolSizeVector()
        pool_sizes.append(vk.DescriptorPoolSize(vk.VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, 1))
        pool_sizes.append(vk.DescriptorPoolSize(vk.VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1))
        self.descriptor_pool = self.ESP( vk.createDescriptorPool(self.device, vk.DescriptorPoolCreateInfo(0, 1, pool_sizes)) )

    def init_descriptor_set(self):        
        alloc_info = vk.DescriptorSetAllocateInfo(self.descriptor_pool, vk.VkDescriptorSetLayoutVector(1,self.desc_layout))
        self.descriptor_set = self.ESP( vk.allocateDescriptorSets(self.device,alloc_info,False) )
        assert(self.descriptor_set is not None and len(self.descriptor_set) == 1)
        writes = vk.VkWriteDescriptorSetVector()
        writes.append( vk.WriteDescriptorSet(self.descriptor_set[0], 
                                             0, # dstBindings 
                                             0, # dstArrayElements
                                             1,
                                             vk.VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                                             vk.VkDescriptorImageInfoVector(), 
                                             vk.VkDescriptorBufferInfoVector(1,vk.DescriptorBufferInfo(self.uniform_buffer, 0, self.uniform_buffer_bytes)),
                                             vk.VkBufferViewVector()) )
        writes.append( vk.WriteDescriptorSet(self.descriptor_set[0], 
                                             1, # dstBindings 
                                             0, # dstArrayElements
                                             1,
                                             vk.VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 
                                             vk.VkDescriptorImageInfoVector(1,vk.DescriptorImageInfo(self.sampler, self.tex_img_view, vk.VK_IMAGE_LAYOUT_GENERAL)), 
                                             vk.VkDescriptorBufferInfoVector(),
                                             vk.VkBufferViewVector()) )
        vk.updateDescriptorSets(self.device, writes, vk.VkCopyDescriptorSetVector())

    def init_pipeline_cache(self):
        self.pipeline_cache = self.ESP( vk.createPipelineCache( self.device, vk.PipelineCacheCreateInfo(0, vk.uint8Vector()) ) )
        assert(self.pipeline_cache is not None)

    def init_pipeline(self, vertex_buffer_stride_bytes):
        psscis = vk.VkPipelineShaderStageCreateInfoVector()
        psscis.append(vk.PipelineShaderStageCreateInfo(0, vk.VK_SHADER_STAGE_VERTEX_BIT, self.vertex_shader, "main", None))
        psscis.append(vk.PipelineShaderStageCreateInfo(0, vk.VK_SHADER_STAGE_FRAGMENT_BIT, self.fragment_shader, "main", None))

        dynamic_states = vk.VkDynamicStateVector()
        dynamic_states.append( vk.VK_DYNAMIC_STATE_VIEWPORT )
        dynamic_states.append( vk.VK_DYNAMIC_STATE_SCISSOR )        
        pdsci = vk.PipelineDynamicStateCreateInfo(0, dynamic_states)
        vi_bindings = vk.VertexInputBindingDescription(0, vertex_buffer_stride_bytes, vk.VK_VERTEX_INPUT_RATE_VERTEX)
        vi_attribs = vk.VkVertexInputAttributeDescriptionVector()
        vi_attribs.append(vk.VertexInputAttributeDescription(0, 0, vk.VK_FORMAT_R32G32B32A32_SFLOAT, 0))
        vi_attribs.append(vk.VertexInputAttributeDescription(1, 0, vk.VK_FORMAT_R32G32_SFLOAT, 16))
        pvisci = vk.PipelineVertexInputStateCreateInfo(0, vk.VkVertexInputBindingDescriptionVector(1,vi_bindings), vi_attribs)
        piasci = vk.PipelineInputAssemblyStateCreateInfo(0, vk.VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, False)
        line_width = 1.0 # this must set to avoid a reported error
        prsci = vk.PipelineRasterizationStateCreateInfo(0, True, False, vk.VK_POLYGON_MODE_FILL, vk.VK_CULL_MODE_BACK_BIT, vk.VK_FRONT_FACE_CLOCKWISE, False, 0, 0, 0, line_width)
        pcbsci = vk.PipelineColorBlendStateCreateInfo(0, False, vk.VK_LOGIC_OP_NO_OP, 
                                                      vk.VkPipelineColorBlendAttachmentStateVector(1, vk.PipelineColorBlendAttachmentState(False, 
                                                                                                                                           vk.VK_BLEND_FACTOR_ZERO,  
                                                                                                                                           vk.VK_BLEND_FACTOR_ZERO,
                                                                                                                                           vk.VK_BLEND_OP_ADD,
                                                                                                                                           vk.VK_BLEND_FACTOR_ZERO,
                                                                                                                                           vk.VK_BLEND_FACTOR_ZERO,
                                                                                                                                           vk.VK_BLEND_OP_ADD,
                                                                                                                                           0xF)),
                                                      [1.0,1.0,1.0,1.0])

        # https://www.khronos.org/registry/vulkan/specs/1.0/man/html/VkPipelineViewportStateCreateInfo.html
        # pViewports is a pointer to an array of VkViewport structures, defining the viewport transforms. If the viewport state is dynamic, this member is ignored.
        # pScissors is a pointer to an array of VkRect2D structures which define the rectangular bounds of the scissor for the corresponding viewport. If the scissor state is dynamic, this member is ignored.
        # below we create unintialized instances of VkViewport and VkRect2D to set the value viewportCount and scissorCount to 1, because we set their states to DYNAMIC above
        pvsci = vk.PipelineViewportStateCreateInfo(0, vk.VkViewportVector(1), vk.VkRect2DVector(1))
        op = vk.StencilOpState(vk.VK_STENCIL_OP_KEEP,vk.VK_STENCIL_OP_KEEP,vk.VK_STENCIL_OP_KEEP,vk.VK_COMPARE_OP_ALWAYS,0,0,0)
        pdssci = vk.PipelineDepthStencilStateCreateInfo(0, True, True, vk.VK_COMPARE_OP_LESS_OR_EQUAL, False, False, op, op, 0, 0)
        pmsci = vk.PipelineMultisampleStateCreateInfo(0, vk.VK_SAMPLE_COUNT_1_BIT, False, 0, None, False, False)

        pipeline_cis = vk.VkGraphicsPipelineCreateInfoVector()
        pipeline_cis.append( vk.GraphicsPipelineCreateInfo(0, psscis, pvisci, piasci, None, pvsci, prsci, pmsci, pdssci, pcbsci, pdsci, self.pipeline_layout, self.render_pass, 0, None, 0) )
        self.pipeline = self.ESP( vk.createGraphicsPipelines(self.device, self.pipeline_cache, pipeline_cis) )
        
    def init_presentable_image(self):  
        if self.swap_chain is not None:      
            self.current_buffer = vk.acquireNextImageKHR(self.device, self.swap_chain, 0xffffffffffffffff, self.present_complete_semaphore, None)
        else:
            # with the offscreen image and no swap chain, we don't do double buffering so current buffer is always 0
            self.current_buffer = 0
               
    def make_render_pass_begin_info(self):
        w,h = self.get_surface_extent()
        
        clear_color_val = vk.VkClearValue()
        clear_color_val.color.float32 = [1.0,0.2,0.2,0.2]

        clear_depth_val = vk.VkClearValue()
        clear_depth_val.depthStencil.depth = 1.0
        clear_depth_val.depthStencil.stencil = 0

        clear_values = vk.VkClearValueVector()
        
        clear_values.append( clear_color_val )
        clear_values.append( clear_depth_val )

        return vk.RenderPassBeginInfo(self.render_pass, self.framebuffers[self.current_buffer], vk.Rect2D(vk.Offset2D(0,0), vk.Extent2D(w,h)), clear_values) 

    def init_viewports(self):
        w,h = self.get_surface_extent()
        vk.cmdSetViewport(self.command_buffers[0], 0, vk.VkViewportVector(1, vk.Viewport(0, 0, w, h, 0.0, 1.0)))

    def init_scissors(self):
        w,h = self.get_surface_extent()
        vk.cmdSetScissor(self.command_buffers[0], 0, vk.VkRect2DVector(1, vk.Rect2D(vk.Offset2D(0,0), vk.Extent2D(w,h))))

    # http://stackoverflow.com/questions/37524032/how-to-deal-with-the-layouts-of-presentable-images
    # Here's the mandatory explicit transition from VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL to VK_IMAGE_LAYOUT_PRESENT_SRC_KHR
    # to avoid any validation error after queuePresentKHR - note that we don't need an explicit transition back to VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL
    # because we specified this transition in the render pass
    def execute_pre_present_barrier(self):
        pre_present_barrier = vk.ImageMemoryBarrier(vk.VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT, 
                                                    vk.VK_ACCESS_MEMORY_READ_BIT,
                                                    vk.VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
                                                    vk.VK_IMAGE_LAYOUT_PRESENT_SRC_KHR, 
                                                    vk.VK_QUEUE_FAMILY_IGNORED,
                                                    vk.VK_QUEUE_FAMILY_IGNORED,
                                                    self.images[self.current_buffer], 
                                                    vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1))
        
        vk.cmdPipelineBarrier(self.command_buffers[0], 
                              vk.VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 
                              vk.VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, 
                              0,
                              vk.VkMemoryBarrierVector(), 
                              vk.VkBufferMemoryBarrierVector(),
                              vk.VkImageMemoryBarrierVector(1,pre_present_barrier))

    def init_readback_image(self):
        w,h = self.get_surface_extent()
        self.read_back_host_array = np.empty(shape=(h,4*w),dtype=np.uint8)
        tex_format = vk.VK_FORMAT_R8G8B8A8_UNORM

        ici = vk.ImageCreateInfo(   0, 
                                    vk.VK_IMAGE_TYPE_2D, 
                                    tex_format,
                                    vk.Extent3D(w,h,1),
                                    1, 
                                    1, 
                                    vk.VK_SAMPLE_COUNT_1_BIT, 
                                    vk.VK_IMAGE_TILING_LINEAR,
                                    vk.VK_IMAGE_USAGE_TRANSFER_DST_BIT,
                                    vk.VK_SHARING_MODE_EXCLUSIVE, 
                                    [], 
                                    vk.VK_IMAGE_LAYOUT_UNDEFINED)

        self.readback_image =  self.ESP( vk.createImage(self.device, ici) )
        mem_reqs = vk.getImageMemoryRequirements(self.device, self.readback_image);
        
        mem_type_index = memory_type_from_properties(self.physical_devices[0], mem_reqs.memoryTypeBits, vk.VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)
        assert(mem_type_index is not None)

        self.readback_image_mem = self.ESP( vk.allocateMemory(self.device, vk.MemoryAllocateInfo(mem_reqs.size, mem_type_index) ) )
        vk.bindImageMemory(self.device, self.readback_image, self.readback_image_mem, 0)

        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
        img_mem_barrier = vk.ImageMemoryBarrier(0, 
                                                vk.VK_ACCESS_MEMORY_READ_BIT, 
                                                vk.VK_IMAGE_LAYOUT_UNDEFINED, 
                                                vk.VK_IMAGE_LAYOUT_GENERAL, 
                                                0, 0, self.readback_image, subresource_range)

        vk.cmdPipelineBarrier(self.command_buffers[0], 
                              vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                              vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                              vk.VkMemoryBarrierVector(), 
                              vk.VkBufferMemoryBarrierVector(),
                              vk.VkImageMemoryBarrierVector(1,img_mem_barrier))

    def stage_readback_copy(self):
        w,h = self.get_surface_extent()
        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
        img_mem_barrier = vk.ImageMemoryBarrier(vk.VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT, 
                                                vk.VK_ACCESS_TRANSFER_READ_BIT, 
                                                vk.VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, 
                                                vk.VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, 
                                                0, 0, self.images[self.current_buffer], 
                                                subresource_range)

        vk.cmdPipelineBarrier(  self.command_buffers[0], 
                                vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                                vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                                vk.VkMemoryBarrierVector(), 
                                vk.VkBufferMemoryBarrierVector(),
                                vk.VkImageMemoryBarrierVector(1,img_mem_barrier))

        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
        img_mem_barrier = vk.ImageMemoryBarrier(vk.VK_ACCESS_MEMORY_READ_BIT, 
                                                vk.VK_ACCESS_TRANSFER_WRITE_BIT, 
                                                vk.VK_IMAGE_LAYOUT_GENERAL, 
                                                vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 
                                                0, 0, self.readback_image, 
                                                subresource_range)

        vk.cmdPipelineBarrier(  self.command_buffers[0], 
                                vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                                vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                                vk.VkMemoryBarrierVector(), 
                                vk.VkBufferMemoryBarrierVector(),
                                vk.VkImageMemoryBarrierVector(1,img_mem_barrier))
            
        copy_regions = vk.VkImageCopyVector(1,vk.ImageCopy(vk.ImageSubresourceLayers(vk.VK_IMAGE_ASPECT_COLOR_BIT,0,0,1),
                                                           vk.Offset3D(0,0,0), 
                                                           vk.ImageSubresourceLayers(vk.VK_IMAGE_ASPECT_COLOR_BIT,0,0,1),
                                                           vk.Offset3D(0,0,0), 
                                                           vk.Extent3D(w,h,1)))

        vk.cmdCopyImage(self.command_buffers[0], self.images[self.current_buffer], vk.VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, self.readback_image, vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, copy_regions)
        
        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
        img_mem_barrier = vk.ImageMemoryBarrier(vk.VK_ACCESS_TRANSFER_WRITE_BIT, 
                                                vk.VK_ACCESS_MEMORY_READ_BIT, 
                                                vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 
                                                vk.VK_IMAGE_LAYOUT_GENERAL, 
                                                0, 0, self.readback_image, subresource_range)

        vk.cmdPipelineBarrier(  self.command_buffers[0], 
                                vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                                vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                                vk.VkMemoryBarrierVector(), 
                                vk.VkBufferMemoryBarrierVector(),
                                vk.VkImageMemoryBarrierVector(1,img_mem_barrier))

    # call after the queue as finished processing the above "stage_readback_copy" commands
    def readback_map_copy(self):
        layout = vk.getImageSubresourceLayout(self.device, self.readback_image, vk.ImageSubresource(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 0))
        with vkunmapping( vk.mapMemory2D(self.device, 
                                         self.readback_image_mem, 
                                         0, 0, np.dtype('ubyte').num, 
                                         self.read_back_host_array.shape[1], 
                                         self.read_back_host_array.shape[0], 
                                         layout.rowPitch ) ) as mapped_array:
            assert(mapped_array.mem.strides[0] == layout.rowPitch)
            np.copyto(self.read_back_host_array, mapped_array.mem)

    def save_readback_image(self,filename):
        currshape = self.read_back_host_array.shape
        reshaped_host_array = np.reshape(self.read_back_host_array,newshape=(currshape[0],currshape[1]/4,4))
        im = Image.fromarray(reshaped_host_array,mode='RGBA')
        im.save(filename)
           
    # Init stages
    VKC_INIT_INSTANCE = 1
    VKC_INIT_DEVICE = 2
    VKC_INIT_SWAP_CHAIN_EXT = 3
    VKC_INIT_COMMAND_BUFFER = 4
    VKC_INIT_SWAP_CHAIN = 5
    VKC_INIT_DEPTH_BUFFER = 6
    VKC_INIT_TEXTURE = 7
    VKC_INIT_UNIFORM_BUFFER = 8
    VKC_INIT_DESCRIPTOR_AND_PIPELINE_LAYOUTS = 9
    VKC_INIT_RENDERPASS = 10
    VKC_INIT_SHADERS = 11
    VKC_INIT_FRAMEBUFFER = 12
    VKC_INIT_VERTEX_BUFFER = 13
    VKC_INIT_DESCRIPTORS = 14
    VKC_INIT_PIPELINE = 15
    VKC_INIT_ALL = 9999

    # Surface Type to use
    VKC_OFFSCREEN = 0
    VKC_WIN32 = 1

    def __del__(self):
        self.stack.close()

    def __init__(self, init_stages = VKC_INIT_PIPELINE, surface_type = VKC_OFFSCREEN, widget = None, vertex_data = None, texture_file_path = None):
        self.output_size = (512,512)
        self.init_stages = init_stages
        self.surface_type = surface_type
        self.widget = widget
        self.vertex_data = vertex_data        
        if vertex_data is None:
            self.vertex_data = get_xyzw_uv_cube_coords()
        self.texture_file_path = texture_file_path

    def __enter__(self):
        self.stack = ExitStack()
        try:
            if self.init_stages >= VkContextManager.VKC_INIT_INSTANCE:
                self.init_global_layer_properties()
                self.init_instance()
                self.init_enumerate_device()                
            if self.init_stages >= VkContextManager.VKC_INIT_SWAP_CHAIN_EXT:
                if self.surface_type == VkContextManager.VKC_WIN32:
                    if self.widget is None:
                        self.init_window()
                    self.init_win32_swap_chain_ext()
                else:
                    assert(self.widget is None)
                    self.init_without_surface()
            if self.init_stages >= VkContextManager.VKC_INIT_DEVICE:
                self.init_device()                    
            if self.init_stages >= VkContextManager.VKC_INIT_COMMAND_BUFFER:
                self.init_command_buffers()
                self.init_device_queue()
            if self.init_stages >= VkContextManager.VKC_INIT_SWAP_CHAIN:
                if self.surface_type == VkContextManager.VKC_OFFSCREEN:
                    self.init_ouput_images()
                    self.init_readback_image()
                else:
                    self.init_swap_chain()
                    self.present_complete_semaphore = self.ESP( vk.createSemaphore(self.device, vk.SemaphoreCreateInfo(0)) )
            if self.init_stages >= VkContextManager.VKC_INIT_DEPTH_BUFFER:
                self.init_depth_buffer()
            if self.init_stages >= VkContextManager.VKC_INIT_TEXTURE:
                self.init_image(self.texture_file_path)
                self.init_sampler()
            if self.init_stages >= VkContextManager.VKC_INIT_UNIFORM_BUFFER:
                self.init_uniform_buffer()
            if self.init_stages >= VkContextManager.VKC_INIT_DESCRIPTOR_AND_PIPELINE_LAYOUTS:
                self.init_descriptor_and_pipeline_layouts()
            if self.init_stages >= VkContextManager.VKC_INIT_RENDERPASS:
                self.init_render_pass(True)
            if self.init_stages >= VkContextManager.VKC_INIT_SHADERS:
                with open('vertex_shader.glsl','r') as vs_in:
                    vs_txt = vs_in.read()
                with open('fragment_shader.glsl','r') as fs_in:
                    fs_txt = fs_in.read()                    
                self.init_shaders(vs_txt, fs_txt)
            if self.init_stages >= VkContextManager.VKC_INIT_FRAMEBUFFER:
                self.init_framebuffer()
            if self.init_stages >= VkContextManager.VKC_INIT_VERTEX_BUFFER:                
                self.init_vertex_buffer(self.vertex_data)
            if self.init_stages >= VkContextManager.VKC_INIT_DESCRIPTORS:
                self.init_descriptor_pool()
                self.init_descriptor_set()
            if self.init_stages >= VkContextManager.VKC_INIT_PIPELINE:
                self.init_pipeline_cache()
                self.init_pipeline(self.vertex_data[0].nbytes)                

        except:
            self.stack.close()
            raise

        return self

    def __exit__(self, *exc_details):
        self.stack.close()
