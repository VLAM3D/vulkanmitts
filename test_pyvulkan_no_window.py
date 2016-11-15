# pyvulkan unit test
# Copyright (C) 2016 by VLAM3D Software inc. https://www.vlam3d.com
# This code is licensed under the MIT license (MIT) (http://opensource.org/licenses/MIT)
import sys
import unittest
import pyvulkan as vk
from vkcontextmanager import VkContextManager, memory_type_from_properties
from contextlib import contextmanager
from cube_data import *

# SWIG generates thin Python class wrappers around an opaque PyObject stored in the 'this' member of the wrapper
# deleting this makes sure the resources are released, the wrapper remains as an empty shell in Python dictionaries 
# Using:
# with vkreleasing( some allocation Vulkan fct ) as thing:
#   use thing
# will make sure that thing releases its resources 
@contextmanager
def vkreleasing(vkcreatedobj):
    try:
        yield vkcreatedobj
    finally:
        del vkcreatedobj.this
    
class GlobalLayersTestCase(unittest.TestCase):
    def test_enumerate_layer_properties(self):
        layer_properties = vk.enumerateInstanceLayerProperties()
        self.assertIsNotNone(layer_properties)
        for lp in layer_properties:
            self.assertIsNotNone(lp.layerName)
            self.assertIsNotNone(lp.specVersion)
            self.assertIsNotNone(lp.implementationVersion)
            self.assertIsNotNone(lp.description)
            ext_props = vk.enumerateInstanceExtensionProperties(lp.layerName)
            self.assertIsNotNone(ext_props)
            for ext in ext_props:
                self.assertIsNotNone(ext)
                self.assertIsNotNone(ext.extensionName)
                self.assertIsNotNone(ext.specVersion)

class CreateInstanceTestCase(unittest.TestCase):
    def setUp(self):
        self.instance_ext_names = [vk.VK_KHR_SURFACE_EXTENSION_NAME]
        self.device_extension_names = [vk.VK_KHR_SWAPCHAIN_EXTENSION_NAME]

    def test_application_info(self):
        app = vk.ApplicationInfo("foo", 1, "bar", 1, 0)
        self.assertIsNotNone(app)

    def test_create_instance(self):
        app = vk.ApplicationInfo("foo", 1, "bar", 1, vk.makeVersion(1,0,3))
        self.assertIsNotNone(app)

        instance_create_info = vk.InstanceCreateInfo(0, app, [], self.instance_ext_names)
        self.assertIsNotNone(instance_create_info)

        with vkreleasing( vk.createInstance(instance_create_info) ) as instance:
            self.assertIsNotNone(instance)
        
class PhysicalDeviceTestCase(unittest.TestCase):
    def setUp(self):
        self.instance_ext_names = [vk.VK_KHR_SURFACE_EXTENSION_NAME]
        self.device_extension_names = [vk.VK_KHR_SWAPCHAIN_EXTENSION_NAME]
        self.app = vk.ApplicationInfo("foo", 1, "bar", 1, vk.makeVersion(1,0,3))
        self.assertIsNotNone(self.app)
        instance_create_info = vk.InstanceCreateInfo(0, self.app, [], self.instance_ext_names)
        self.instance = vk.createInstance(instance_create_info)
        vk.load_vulkan_fct_ptrs(self.instance)
        self.assertIsNotNone(self.instance)
        self.physical_devices = vk.enumeratePhysicalDevices(self.instance)

    def test_enumerate_physical_device(self):        
        self.assertIsNotNone(self.physical_devices)
        self.assertTrue(len(self.physical_devices)>0) 

    def test_physical_device_properties(self):
        phydev_props = vk.getPhysicalDeviceProperties(self.physical_devices[0])
        self.assertIsNotNone(phydev_props)
        self.assertTrue(phydev_props.apiVersion != 0)
        self.assertTrue(phydev_props.driverVersion != 0)
        self.assertTrue(phydev_props.vendorID != 0)
        self.assertTrue(phydev_props.deviceID != 0)
        self.assertTrue(len(phydev_props.deviceName) > 0)
        self.assertIsNotNone(phydev_props.pipelineCacheUUID) # still opaque in python
        self.assertIsNotNone(phydev_props.limits) # still opaque in python
        self.assertIsNotNone(phydev_props.sparseProperties) # still opaque in python

    def test_physical_device_features(self):
        phydev_features = vk.getPhysicalDeviceFeatures(self.physical_devices[0])
        self.assertIsNotNone(phydev_features)
        self.assertIsNotNone(phydev_features.robustBufferAccess)
            
    def test_physical_device_queue_family_properties(self):
        queue_props = vk.getPhysicalDeviceQueueFamilyProperties(self.physical_devices[0])
        self.assertIsNotNone(queue_props)
        self.assertTrue(len(queue_props)>=1)
        some_graphics_queue = False
        for qp in queue_props:
            self.assertTrue(qp.queueCount>=1)
            self.assertIsNotNone(qp.timestampValidBits)
            self.assertIsNotNone(qp.minImageTransferGranularity)
            some_graphics_queue = some_graphics_queue or (qp.queueFlags & vk.VK_QUEUE_GRAPHICS_BIT)
        self.assertTrue(some_graphics_queue)

    def test_create_device(self):
        queue_props = vk.getPhysicalDeviceQueueFamilyProperties(self.physical_devices[0])
        graphic_queues_indices = [ i for i,qp in enumerate(queue_props) if qp.queueFlags & vk.VK_QUEUE_GRAPHICS_BIT]
        dev_queue_ci = vk.DeviceQueueCreateInfo(0, graphic_queues_indices[0], [0.0])
        vec_dev_queue_ci = vk.VkDeviceQueueCreateInfoVector()
        vec_dev_queue_ci.append(dev_queue_ci)
        dev_features = vk.getPhysicalDeviceFeatures(self.physical_devices[0])
        device_ci = vk.DeviceCreateInfo(0, vec_dev_queue_ci, [], self.device_extension_names, dev_features)
        self.assertIsNotNone(device_ci)
        device = vk.createDevice(self.physical_devices[0], device_ci)
        self.assertIsNotNone(device)
        vk.deviceWaitIdle(device) # would throw an error if device is not good
        queue = vk.getDeviceQueue(device, graphic_queues_indices[0], 0)
        self.assertIsNotNone(queue)
        vk.queueWaitIdle(queue)

    def test_physical_device_format(self):
        # from Sascha Willems vulkantools.cpp
        # test that one of these formats can used as z-buffer
        depth_formats_to_try = [vk.VK_FORMAT_D32_SFLOAT_S8_UINT, 
			                    vk.VK_FORMAT_D32_SFLOAT,
			                    vk.VK_FORMAT_D24_UNORM_S8_UINT, 
			                    vk.VK_FORMAT_D16_UNORM_S8_UINT, 
			                    vk.VK_FORMAT_D16_UNORM ]

        format_can_be_used_as_depth = False
        for f in depth_formats_to_try:
            format_properties = vk.getPhysicalDeviceFormatProperties(self.physical_devices[0], f)
            self.assertIsNotNone(format_properties)
            self.assertIsNotNone(format_properties.linearTilingFeatures)
            self.assertIsNotNone(format_properties.optimalTilingFeatures)
            self.assertIsNotNone(format_properties.bufferFeatures)
            format_can_be_used_as_depth = format_can_be_used_as_depth or (format_properties.optimalTilingFeatures & vk.VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT)

        self.assertTrue(format_can_be_used_as_depth)

class TestCommandBuffers(unittest.TestCase):
    def test_create_command_pool(self):
        with VkContextManager(VkContextManager.VKC_INIT_SWAP_CHAIN_EXT) as vkc:
            with vkreleasing(vk.createCommandPool(vkc.device, vk.CommandPoolCreateInfo(vk.VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, vkc.graphics_queue_family_index))) as command_pool:
                self.assertIsNotNone(command_pool)

    def test_allocate_command_buffers(self):
        with VkContextManager(VkContextManager.VKC_INIT_SWAP_CHAIN_EXT) as vkc:
            with vkreleasing(vk.createCommandPool(vkc.device, vk.CommandPoolCreateInfo(vk.VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, vkc.graphics_queue_family_index))) as command_pool:
                cbai = vk.CommandBufferAllocateInfo(command_pool, vk.VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1)
                self.assertIsNotNone(cbai)
                with vkreleasing(vk.allocateCommandBuffers(vkc.device, cbai)) as command_buffers:
                    self.assertIsNotNone(command_buffers)
                    vk.beginCommandBuffer(command_buffers[0], vk.CommandBufferBeginInfo(0,None))
                    vk.endCommandBuffer(command_buffers[0])

class TestDepthStencil(unittest.TestCase):
    def test_setup_depth_stencil(self):        
        with VkContextManager(VkContextManager.VKC_INIT_COMMAND_BUFFER) as vkc: 
            ici = vk.ImageCreateInfo(0, 
                                     vk.VK_IMAGE_TYPE_2D, 
                                     vk.VK_FORMAT_D24_UNORM_S8_UINT, 
                                     vk.Extent3D(640,480,1),
                                     1, 
                                     1, 
                                     vk.VK_SAMPLE_COUNT_1_BIT, 
                                     vk.VK_IMAGE_TILING_OPTIMAL, 
                                     vk.VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT | vk.VK_IMAGE_USAGE_TRANSFER_SRC_BIT,
                                     vk.VK_SHARING_MODE_EXCLUSIVE, 
                                     [], 
                                     vk.VK_IMAGE_LAYOUT_UNDEFINED)

            with vkreleasing( vk.createImage(vkc.device, ici) ) as image:
                self.assertIsNotNone(image)
                memory_requirements = vk.getImageMemoryRequirements(vkc.device, image)
                self.assertIsNotNone(memory_requirements)
                mem_type_index = memory_type_from_properties(vkc.physical_devices[0], memory_requirements.memoryTypeBits, vk.VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)       
                self.assertIsNotNone(mem_type_index)

                with vkreleasing( vk.allocateMemory(vkc.device, vk.MemoryAllocateInfo(memory_requirements.size, mem_type_index)) ) as memory:
                    vk.bindImageMemory(vkc.device, image, memory, 0)
                    image_memory_barrier = vk.ImageMemoryBarrier(0, 
                                                                 vk.VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT, 
                                                                 vk.VK_IMAGE_LAYOUT_UNDEFINED, 
                                                                 vk.VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL,
                                                                 0,
                                                                 0,
                                                                 image, 
                                                                 vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_DEPTH_BIT|vk.VK_IMAGE_ASPECT_STENCIL_BIT,0,1,0,1))

                    vk.cmdPipelineBarrier(vkc.command_buffers[0], 
                                          vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                                          vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                                          0,
                                          vk.VkMemoryBarrierVector(), 
                                          vk.VkBufferMemoryBarrierVector(), 
                                          vk.VkImageMemoryBarrierVector(1,image_memory_barrier))

class TestRenderCube(unittest.TestCase):
    def test_render_colored_cube(self): 
        from hello_pyvkoffscreen import render_textured_cube       
        cube_coords = get_xyzw_uv_cube_coords()
        with VkContextManager(vertex_data = cube_coords, surface_type = VkContextManager.VKC_OFFSCREEN) as vkc: 
            self.assertIsNotNone(vkc)            
            render_textured_cube(vkc,cube_coords)
      
if __name__ == '__main__':
    # set defaultTest to invoke a specific test case
    unittest.main(verbosity=2)
