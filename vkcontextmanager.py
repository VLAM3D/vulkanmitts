import os
import pyvulkan as vk
import pyglslang
from PIL import Image
import numpy as np
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from contextlib import ExitStack, contextmanager
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

# ported from the Lunar SDK
def set_image_layout(cmd_buffer, image, aspectMask, old_image_layout, new_image_layout):
    src_access_mask = 0
    dst_access_mask = 0

    if old_image_layout == vk.VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL:
        src_access_mask = vk.VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT
    
    if new_image_layout == vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL:
        dst_access_mask = vk.VK_ACCESS_MEMORY_READ_BIT

    if new_image_layout == vk.VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL:
        src_access_mask = vk.VK_ACCESS_HOST_WRITE_BIT | vk.VK_ACCESS_TRANSFER_WRITE_BIT;
        dst_access_mask = vk.VK_ACCESS_SHADER_READ_BIT

    if new_image_layout == vk.VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL:
        dst_access_mask = vk.VK_ACCESS_COLOR_ATTACHMENT_READ_BIT

    if new_image_layout == vk.VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL:
        dst_access_mask = vk.VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_READ_BIT

    subresource_range = vk.ImageSubresourceRange(aspectMask, 0, 1, 0, 1)
    img_mem_barrier = vk.ImageMemoryBarrier(src_access_mask, dst_access_mask, old_image_layout, new_image_layout, 0, 0, image, subresource_range)

    vk.cmdPipelineBarrier(cmd_buffer, 
                          vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 
                          vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, 0, 
                          vk.VkMemoryBarrierVector(), 
                          vk.VkBufferMemoryBarrierVector(),
                          vk.VkImageMemoryBarrierVector(1,img_mem_barrier))

def delete_this(obj):
    del obj.this

class VkContextManager:
    # Acronym for ExitStack Push to reduce the clutter
    # push a destructor for the refcounted handle wrapper on the ExitStack that will be called in unwinding order in __exit__
    def ESP(self, obj):
        self.stack.callback(delete_this, obj)
        return obj

    def init_instance(self):
        self.instance_ext_names = [vk.VK_KHR_SURFACE_EXTENSION_NAME, vk.VK_KHR_WIN32_SURFACE_EXTENSION_NAME]        
        app = vk.ApplicationInfo("foo", 1, "bar", 1, vk.makeVersion(1,0,3))
        assert(app is not None)
        instance_create_info = vk.InstanceCreateInfo(0, app, [], self.instance_ext_names)
        self.instance = self.ESP( vk.createInstance(instance_create_info) )
        assert(self.instance is not None)

    def init_device(self):
        self.device_extension_names = [vk.VK_KHR_SWAPCHAIN_EXTENSION_NAME]
        self.physical_devices = vk.enumeratePhysicalDevices(self.instance)
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
        self.widget = QWidget()
        self.widget.resize(640, 480)
        self.stack.callback(self.delete_window)   
        
    def init_win32_swap_chain_ext(self):
        surface_ci = vk.Win32SurfaceCreateInfoKHR(0, vk.GetThisEXEModuleHandle(), self.widget.winId())       
        self.surface = self.ESP( vk.createWin32SurfaceKHR(self.instance, surface_ci) )
        assert(self.surface is not None)

        # test that we can find a queue with the graphics bit and that can present
        queue_props = vk.getPhysicalDeviceQueueFamilyProperties(self.physical_devices[0])
        support_present = []
        for i in range(0,len(queue_props)):
            support_present.append( vk.getPhysicalDeviceSurfaceSupportKHR(self.physical_devices[0], i, self.surface) != 0)

        graphic_queues_indices = [ i for i,qp in enumerate(queue_props) if qp.queueFlags & vk.VK_QUEUE_GRAPHICS_BIT and support_present[i] ]
        assert(len(graphic_queues_indices)>=1)
        self.graphics_queue_family_index = graphic_queues_indices[0]
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

    def end_command_buffer(self):
        self.command_buffers[0]

    def init_command_buffers(self):
        self.command_pool = self.ESP( vk.createCommandPool(self.device, vk.CommandPoolCreateInfo(vk.VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, self.graphics_queue_family_index)) )
        cbai = vk.CommandBufferAllocateInfo(self.command_pool, vk.VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1)
        self.command_buffers = self.ESP( vk.allocateCommandBuffers(self.device, cbai) )
        assert(self.command_buffers is not None)
        vk.beginCommandBuffer(self.command_buffers[0], vk.CommandBufferBeginInfo(0,None))        
        self.stack.callback(self.end_command_buffer)

    def init_device_queue(self):
        self.device_queue = vk.getDeviceQueue(self.device, self.graphics_queue_family_index, 0)

    def init_swap_chain(self):
        present_modes = vk.getPhysicalDeviceSurfacePresentModesKHR(self.physical_devices[0], self.surface)
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
                                           vk.VK_SHARING_MODE_EXCLUSIVE, # image sharing mode, 
                                           [], 
                                           pre_transform, 
                                           vk.VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR, # composite  alpha, 
                                           present_modes[0], # present mode
                                           True, # clipped
                                           None) # old_swp_chain
        
        self.swap_chain = self.ESP( vk.createSwapchainKHR(self.device, swp_ci) )
        self.images = vk.getSwapchainImagesKHR(self.device, self.swap_chain)
        components = vk.ComponentMapping(vk.VK_COMPONENT_SWIZZLE_R, vk.VK_COMPONENT_SWIZZLE_G, vk.VK_COMPONENT_SWIZZLE_B, vk.VK_COMPONENT_SWIZZLE_A)
        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
        self.image_views = []
        for img in self.images:
            ivci = vk.ImageViewCreateInfo(0, img, vk.VK_IMAGE_VIEW_TYPE_2D, self.format, components, subresource_range)
            set_image_layout(self.command_buffers[0], img, vk.VK_IMAGE_ASPECT_COLOR_BIT, vk.VK_IMAGE_LAYOUT_UNDEFINED, vk.VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL)
            self.image_views.append( self.ESP(vk.createImageView(self.device, ivci)) )

    def get_surface_extent(self):    
        surface_caps = vk.getPhysicalDeviceSurfaceCapabilitiesKHR(self.physical_devices[0], self.surface)
        return surface_caps.currentExtent.width, surface_caps.currentExtent.height

    def init_depth_buffer(self):
        self.depth_format = vk.VK_FORMAT_D24_UNORM_S8_UINT
        fp = vk.getPhysicalDeviceFormatProperties(self.physical_devices[0], self.depth_format)        
        tiling = 0        
        if fp.optimalTilingFeatures & vk.VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT:
            tiling = vk.VK_IMAGE_TILING_OPTIMAL
        elif fp.linearTilingFeatures & vk.VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT:
            tiling = vk.VK_IMAGE_TILING_LINEAR
        else:
            raise RuntimeError('VK_FORMAT_D24_UNORM_S8_UINT not supported on this physical device')
        
        w,h = self.get_surface_extent()
        ici = vk.ImageCreateInfo(   0, 
                                    vk.VK_IMAGE_TYPE_2D, 
                                    self.depth_format,
                                    vk.Extent3D(w,h,1),
                                    1, 
                                    1, 
                                    vk.VK_SAMPLE_COUNT_1_BIT, 
                                    tiling, 
                                    vk.VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT | vk.VK_IMAGE_USAGE_TRANSFER_SRC_BIT,
                                    vk.VK_SHARING_MODE_EXCLUSIVE, 
                                    [], 
                                    vk.VK_IMAGE_LAYOUT_UNDEFINED)

        self.depth_image =  self.ESP( vk.createImage(self.device, ici) )
        mem_reqs = vk.getImageMemoryRequirements(self.device, self.depth_image);
        
        mem_type_index = memory_type_from_properties(self.physical_devices[0], mem_reqs.memoryTypeBits, 0)
        assert(mem_type_index is not None)

        self.depth_mem = self.ESP( vk.allocateMemory(self.device, vk.MemoryAllocateInfo(mem_reqs.size, mem_type_index) ) )
        vk.bindImageMemory(self.device, self.depth_image, self.depth_mem, 0)

        set_image_layout(self.command_buffers[0], self.depth_image, vk.VK_IMAGE_ASPECT_DEPTH_BIT, vk.VK_IMAGE_LAYOUT_UNDEFINED, vk.VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL)

        components = vk.ComponentMapping(vk.VK_COMPONENT_SWIZZLE_R, vk.VK_COMPONENT_SWIZZLE_G, vk.VK_COMPONENT_SWIZZLE_B, vk.VK_COMPONENT_SWIZZLE_A)
        subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_DEPTH_BIT, 0, 1, 0, 1)
        self.depth_view = self.ESP( vk.createImageView(self.device, vk.ImageViewCreateInfo(0, self.depth_image, vk.VK_IMAGE_VIEW_TYPE_2D, self.depth_format, components, subresource_range)) )

    def init_image(self, texture_file_path = None):
        if texture_file_path is None or texture_file_path.empty() or not os.path.exists(texture_file_path):
            texture_file_path = 'lena_std.png'

        if not os.path.exists(texture_file_path):
            img_size = (640,480)
            img_array = check(img_size[0],img_size[1],0,255,32).astype(np.uint8)
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
                    img_array = flat_array.reshape( (pil_img.height, pil_img.width*4) )
                    
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

        set_image_layout(self.command_buffers[0], self.depth_image, vk.VK_IMAGE_ASPECT_COLOR_BIT, vk.VK_IMAGE_LAYOUT_UNDEFINED, vk.VK_IMAGE_LAYOUT_GENERAL)

        vk.endCommandBuffer(self.command_buffers[0])

        with vkreleasing( vk.createFence(self.device, vk.FenceCreateInfo(0)) ) as cmd_fence:
            submit_info_vec = vk.VkSubmitInfoVector()
            cmd_buf = vk.VkCommandBufferVector(1, self.command_buffers[0])        
            submit_info_vec.append( vk.SubmitInfo(vk.VkSemaphoreVector(), vk.VkPipelineStageFlagsVector(), cmd_buf, vk.VkSemaphoreVector()) ) 
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
        with vkunmapping( vk.mapMemory2D(self.device, self.tex_mem, 0, 0, np.dtype('ubyte').num, img_array.shape[0], img_array.shape[1], layout.rowPitch ) ) as mapped_array:
            assert(mapped_array.mem.strides[0] == layout.rowPitch)
            np.copyto(mapped_array.mem, img_array)

        vk.resetCommandBuffer(self.command_buffers[0], 0);
        vk.beginCommandBuffer(self.command_buffers[0], vk.CommandBufferBeginInfo(0,None))

        if not need_staging:
            set_image_layout(self.command_buffers[0], self.tex_image, vk.VK_IMAGE_ASPECT_COLOR_BIT, vk.VK_IMAGE_LAYOUT_GENERAL, vk.VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL)
            self.dst_img = self.tex_image
        else:
            ici.tiling = vk.VK_IMAGE_TILING_OPTIMAL
            ici.usage =  vk.VK_IMAGE_USAGE_TRANSFER_DST_BIT | vk.VK_IMAGE_USAGE_SAMPLED_BIT
            self.dst_img = self.ESP( vk.createImage(self.device, ici) )

            mem_reqs = vk.getImageMemoryRequirements(self.device, self.dst_img);
            mem_type_index = memory_type_from_properties(self.physical_devices[0], mem_reqs.memoryTypeBits, vk.VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)
            assert(mem_type_index is not None)

            self.dst_mem = self.ESP( vk.allocateMemory(self.device, vk.MemoryAllocateInfo(mem_reqs.size, mem_type_index) ) )
            vk.bindImageMemory(self.device, self.dst_img, self.dst_mem, 0)

            set_image_layout(self.command_buffers[0], self.tex_image, vk.VK_IMAGE_ASPECT_COLOR_BIT, vk.VK_IMAGE_LAYOUT_GENERAL, vk.VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL)
            set_image_layout(self.command_buffers[0], self.dst_img, vk.VK_IMAGE_ASPECT_COLOR_BIT, vk.VK_IMAGE_LAYOUT_UNDEFINED, vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL)
            
            copy_regions = vk.VkImageCopyVector(1,vk.ImageCopy(vk.ImageSubresourceLayers(vk.VK_IMAGE_ASPECT_COLOR_BIT,0,0,1),vk.Offset3D(0,0,0), 
                                                               vk.ImageSubresourceLayers(vk.VK_IMAGE_ASPECT_COLOR_BIT,0,0,1),vk.Offset3D(0,0,0), vk.Extent3D(img_size[0],img_size[1],1)))
            vk.cmdCopyImage(self.command_buffers[0], self.tex_image, vk.VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, self.dst_img, vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, copy_regions)

            set_image_layout(self.command_buffers[0], self.dst_img, vk.VK_IMAGE_ASPECT_COLOR_BIT, vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, vk.VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL)

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
        MVP = (P * V * M).astype(np.single)

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
        attachments = vk.VkAttachmentDescriptionVector()        
        attachments.append( vk.AttachmentDescription(0, self.format, 
                                                        vk.VK_SAMPLE_COUNT_1_BIT, 
                                                        loadOp,  
                                                        vk.VK_ATTACHMENT_STORE_OP_STORE, 
                                                        vk.VK_ATTACHMENT_LOAD_OP_DONT_CARE, 
                                                        vk.VK_ATTACHMENT_STORE_OP_DONT_CARE, 
                                                        vk.VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
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
        depth_attachment = vk.AttachmentReference(0,vk.VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL)
        
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
        self.descriptor_set = self.ESP( vk.allocateDescriptorSets(self.device, vk.DescriptorSetAllocateInfo(self.descriptor_pool, vk.VkDescriptorSetLayoutVector(1,self.desc_layout))) )
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
        self.pipeline_cache = self.ESP( vk.createPipelineCache( self.device, vk.PipelineCacheCreateInfo(0, 0) ) )
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
        prsci = vk.PipelineRasterizationStateCreateInfo(0, True, False, vk.VK_POLYGON_MODE_FILL, vk.VK_CULL_MODE_BACK_BIT, vk.VK_FRONT_FACE_CLOCKWISE, False, 0, 0, 0, 0)
        pcbsci = vk.PipelineColorBlendStateCreateInfo(0, False, vk.VK_LOGIC_OP_NO_OP, 
                                                      vk.VkPipelineColorBlendAttachmentStateVector(1, vk.PipelineColorBlendAttachmentState(False, 
                                                                                                                                           vk.VK_BLEND_FACTOR_ZERO,  
                                                                                                                                           vk.VK_BLEND_FACTOR_ZERO,
                                                                                                                                           vk.VK_BLEND_OP_ADD,
                                                                                                                                           vk.VK_BLEND_FACTOR_ZERO,
                                                                                                                                           vk.VK_BLEND_FACTOR_ZERO,
                                                                                                                                           vk.VK_BLEND_OP_ADD,
                                                                                                                                           0)),
                                                      [1.0,1.0,1.0,1.0])

        pvsci = vk.PipelineViewportStateCreateInfo(0, vk.VkViewportVector(), vk.VkRect2DVector())
        op = vk.StencilOpState(vk.VK_STENCIL_OP_KEEP,vk.VK_STENCIL_OP_KEEP,vk.VK_STENCIL_OP_KEEP,vk.VK_COMPARE_OP_ALWAYS,0,0,0)
        pdssci = vk.PipelineDepthStencilStateCreateInfo(0, True, True, vk.VK_COMPARE_OP_LESS_OR_EQUAL, False, False, op, op, 0, 0)
        pmsci = vk.PipelineMultisampleStateCreateInfo(0, vk.VK_SAMPLE_COUNT_1_BIT, False, 0, None, False, False)

        pipeline_cis = vk.VkGraphicsPipelineCreateInfoVector()
        pipeline_cis.append( vk.GraphicsPipelineCreateInfo(0, psscis, pvisci, piasci, None, pvsci, prsci, pmsci, pdssci, pcbsci, pdsci, self.pipeline_layout, self.render_pass, 0, None, 0) )
        self.pipeline = self.ESP( vk.createGraphicsPipelines(self.device, self.pipeline_cache, pipeline_cis) )
        
    def init_presentable_image(self):        
        self.current_buffer = vk.acquireNextImageKHR(self.device, self.swap_chain, 0xffffffff, self.present_complete_semaphore, None)
               
    def make_render_pass_begin_info(self):
        w,h = self.get_surface_extent()
        
        clear_color_val = vk.VkClearColorValue()
        clear_color_val.float32[0] = 1.0
        clear_color_val.float32[1] = 0.0
        clear_color_val.float32[2] = 0.0

        clear_depth_val = vk.VkClearDepthStencilValue()
        clear_depth_val.depth = 1.0
        clear_depth_val.stencil = 0

        clear_values = vk.VkClearValueVector()
        clear_values.append( vk.ClearValue(clear_color_val, vk.VkClearDepthStencilValue()) )
        clear_values.append( vk.ClearValue(vk.VkClearColorValue(), clear_depth_val) )

        return vk.RenderPassBeginInfo(self.render_pass, self.framebuffers[self.current_buffer], vk.Rect2D(vk.Offset2D(0,0), vk.Extent2D(w,h)), clear_values) 

    def init_viewports(self):
        w,h = self.get_surface_extent()
        vk.cmdSetViewport(self.command_buffers[0], 0, vk.VkViewportVector(1, vk.Viewport(0, 0, w, h, 0.0, 1.0)))

    def init_scissors(self):
        w,h = self.get_surface_extent()
        vk.cmdSetScissor(self.command_buffers[0], 0, vk.VkRect2DVector(1, vk.Rect2D(vk.Offset2D(0,0), vk.Extent2D(w,h))))

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
    VKC_INIT_TEST_SINGLE_RENDER_PASS = 16
    VKC_INIT_ALL = 9999

    def __del__(self):
        self.stack.close()

    def __init__(self, init_stages = VKC_INIT_PIPELINE, widget = None):
        self.init_stages = init_stages
        self.widget = widget

    def __enter__(self):
        self.stack = ExitStack()
        try:
            cube_coords = get_xyzw_uv_cube_coords()

            if self.init_stages >= VkContextManager.VKC_INIT_INSTANCE:
                self.init_instance()
            if self.init_stages >= VkContextManager.VKC_INIT_DEVICE:
                self.init_device()        
            if self.init_stages >= VkContextManager.VKC_INIT_SWAP_CHAIN_EXT:
                if self.widget is None:
                    self.init_window()
                self.init_win32_swap_chain_ext()
            if self.init_stages >= VkContextManager.VKC_INIT_COMMAND_BUFFER:
                self.init_command_buffers()
                self.init_device_queue()
            if self.init_stages >= VkContextManager.VKC_INIT_SWAP_CHAIN:
                self.init_swap_chain()
            if self.init_stages >= VkContextManager.VKC_INIT_DEPTH_BUFFER:
                self.init_depth_buffer()
            if self.init_stages >= VkContextManager.VKC_INIT_TEXTURE:
                self.init_image()
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
                self.init_vertex_buffer(cube_coords)
            if self.init_stages >= VkContextManager.VKC_INIT_DESCRIPTORS:
                self.init_descriptor_pool()
                self.init_descriptor_set()
            if self.init_stages >= VkContextManager.VKC_INIT_PIPELINE:
                self.init_pipeline_cache()
                self.init_pipeline(cube_coords[0].nbytes)
                self.present_complete_semaphore = self.ESP( vk.createSemaphore(self.device, vk.SemaphoreCreateInfo(0)) )
                
            if self.init_stages >= VkContextManager.VKC_INIT_TEST_SINGLE_RENDER_PASS:                
                self.init_presentable_image()       
                rp_begin = self.make_render_pass_begin_info() 
                vk.cmdBeginRenderPass(self.command_buffers[0], rp_begin, vk.VK_SUBPASS_CONTENTS_INLINE) 
                vk.cmdBindPipeline(self.command_buffers[0], vk.VK_PIPELINE_BIND_POINT_GRAPHICS, self.pipeline[0])
                vk.cmdBindDescriptorSets(self.command_buffers[0], vk.VK_PIPELINE_BIND_POINT_GRAPHICS, self.pipeline_layout, 0, self.descriptor_set,  [])
                vk.cmdBindVertexBuffers(self.command_buffers[0], 0, vk.VkBufferVector(1,self.vertex_buffer), vk.VkDeviceSizeVector(1,0))                                
                
                self.init_viewports()
                self.init_scissors()
                vk.cmdDraw(self.command_buffers[0], cube_coords.shape[0], 1, 0, 0)
                vk.cmdEndRenderPass(self.command_buffers[0])
                vk.endCommandBuffer(self.command_buffers[0])
                self.execute_pre_present_barrier()
                self.draw_fence = self.ESP(vk.createFence(self.device, vk.FenceCreateInfo(0)))
                submit_info = vk.SubmitInfo( vk.VkSemaphoreVector(1,self.present_complete_semaphore), vk.VkPipelineStageFlagsVector(1,vk.VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT), self.command_buffers, vk.VkSemaphoreVector())                
                vk.queueSubmit(self.device_queue, vk.VkSubmitInfoVector(1,submit_info), self.draw_fence)
                command_buffer_finished = False
                cmd_fences = vk.VkFenceVector(1,self.draw_fence)
                while not command_buffer_finished:
                    try:
                        vk.waitForFences(self.device, cmd_fences, True, 1000000)
                        command_buffer_finished = True
                    except RuntimeError:
                        pass
                
                present_info = vk.PresentInfoKHR(vk.VkSemaphoreVector(), vk.VkSwapchainKHRVector(1, self.swap_chain), [self.current_buffer], vk.VkResultVector())
                vk.queuePresentKHR(self.device_queue, present_info)

        except:
            self.stack.close()
            raise

        return self

    def __exit__(self, *exc_details):
        self.stack.close()
