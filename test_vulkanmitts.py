# vulkanmitts unit test
# Copyright (C) 2016 by VLAM3D Software inc. https://www.vlam3d.com
# This code is licensed under the MIT license (MIT) (http://opensource.org/licenses/MIT)
import sys
import unittest
import vulkanmitts as vk
from PyQt5.QtWidgets import QApplication, QWidget
from vkcontextmanager import VkContextManager, memory_type_from_properties
from contextlib import contextmanager, ExitStack
from hello_vulkanmitts import render_textured_cube
from cube_data import *
from test_vulkanmitts_no_window import *

class SwapChainTestCase(unittest.TestCase):
    def setUp(self):
        self.instance_ext_names = [vk.VK_KHR_SURFACE_EXTENSION_NAME, vk.VK_KHR_WIN32_SURFACE_EXTENSION_NAME]
        self.device_extension_names = [vk.VK_KHR_SWAPCHAIN_EXTENSION_NAME]
        self.app = vk.ApplicationInfo("foo", 1, "bar", 1, vk.makeVersion(1,0,3))
        self.assertIsNotNone(self.app)
        instance_create_info = vk.InstanceCreateInfo(0, self.app, [], self.instance_ext_names)
        self.instance = vk.createInstance(instance_create_info)
        vk.load_vulkan_fct_ptrs(self.instance)
        self.physical_devices = vk.enumeratePhysicalDevices(self.instance)
        queue_props = vk.getPhysicalDeviceQueueFamilyProperties(self.physical_devices[0])
        graphic_queues_indices = [ i for i,qp in enumerate(queue_props) if qp.queueFlags & vk.VK_QUEUE_GRAPHICS_BIT]
        dev_queue_ci = vk.DeviceQueueCreateInfo(0, graphic_queues_indices[0], vk.floatVector(1,0.0))
        vec_dev_queue_ci = vk.VkDeviceQueueCreateInfoVector(1,dev_queue_ci) # like std::vector ctor (size, default_value)
        device_ci = vk.DeviceCreateInfo(0, vec_dev_queue_ci, [], self.device_extension_names, None)
        self.device = vk.createDevice(self.physical_devices[0], device_ci)
        self.assertIsNotNone(self.device)

    def __del__(self):
        self.device = None

    def test_create_win32_swap_chain(self):
        # vulkanmitts object are refcounted but python doesn't garantee the order of destruction of objects
        # so a ExitStack is used to control the order of destruction in reverse order of creation
        with ExitStack() as stack:
            def delete_this(obj):
                if hasattr(obj,'this'):
                    del obj.this
            # Acronym for ExitStack Push to reduce the clutter
            # push a destructor for the refcounted handle wrapper on the ExitStack that will be called in unwinding order in __exit__
            def ESP(obj):
                try:
                    stack.callback(delete_this, obj)
                except IndexError as e:
                    print(e.message)
                except:
                    pass
                return obj

            widget = QWidget()
            widget.resize(640, 480)
            surface_ci = vk.Win32SurfaceCreateInfoKHR(0, vk.GetThisEXEModuleHandle(), widget.winId())
            self.assertIsNotNone(surface_ci)
            surface = ESP(vk.createWin32SurfaceKHR(self.instance, surface_ci))
            self.assertIsNotNone(surface)

            # test that we can find a queue with the graphics bit and that can present
            queue_props = vk.getPhysicalDeviceQueueFamilyProperties(self.physical_devices[0])
            support_present = []
            for i in range(0,len(queue_props)):
                support_present.append( vk.getPhysicalDeviceSurfaceSupportKHR(self.physical_devices[0], i, surface) != 0)

            graphic_queues_indices = [ i for i,qp in enumerate(queue_props) if qp.queueFlags & vk.VK_QUEUE_GRAPHICS_BIT and support_present[i] ]
            self.assertTrue(len(graphic_queues_indices)>=1)

            surface_formats = vk.getPhysicalDeviceSurfaceFormatsKHR(self.physical_devices[0], surface)
            self.assertIsNotNone(surface_formats)
            B8G8R8A8_format_found = False
            format = None
            color_space = None
            for f in surface_formats:
                self.assertIsNotNone(f.format)
                self.assertIsNotNone(f.colorSpace)
                # from LunarSDK samples and Sascha Willems samples this format seems to be a good default
                if f.format == vk.VK_FORMAT_B8G8R8A8_UNORM:
                    B8G8R8A8_format_found = True
                    format = f.format
                    color_space = f.colorSpace

            self.assertTrue(B8G8R8A8_format_found)

            present_modes = vk.getPhysicalDeviceSurfacePresentModesKHR(self.physical_devices[0], surface)
            self.assertIsNotNone(present_modes)
            present_mode_lut = {vk.VK_PRESENT_MODE_MAILBOX_KHR : 'VK_PRESENT_MODE_MAILBOX_KHR',
                                vk.VK_PRESENT_MODE_FIFO_KHR : 'VK_PRESENT_MODE_FIFO_KHR',
                                vk.VK_PRESENT_MODE_IMMEDIATE_KHR : 'VK_PRESENT_MODE_IMMEDIATE_KHR',
                                vk.VK_PRESENT_MODE_FIFO_RELAXED_KHR : 'VK_PRESENT_MODE_FIFO_RELAXED_KHR'}
            for p in present_modes:
                self.assertTrue( p in present_mode_lut.keys() )

            surface_caps = vk.getPhysicalDeviceSurfaceCapabilitiesKHR(self.physical_devices[0], surface)
            self.assertIsNotNone(surface_caps)
            req_image_count = surface_caps.minImageCount + 1
            if surface_caps.maxImageCount > 0 and req_image_count > surface_caps.maxImageCount:
                req_image_count = surface_caps.maxImageCount

            pre_transform = surface_caps.currentTransform
            if surface_caps.supportedTransforms & vk.VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR:
                pre_transform = vk.VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR

            swp_ci = vk.SwapchainCreateInfoKHR(0,
                                            surface,
                                            req_image_count,
                                            format,
                                            color_space,
                                            surface_caps.currentExtent, # image extent
                                            1, # image array layers
                                            vk.VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT, # image usage
                                            vk.VK_SHARING_MODE_EXCLUSIVE, # image sharing mode,
                                            [],
                                            pre_transform,
                                            vk.VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR, # composite  alpha,
                                            present_modes[0], # present mode
                                            True, # clipped
                                            None) # old_swp_chain
            self.assertIsNotNone(swp_ci)
            swap_chain = ESP(vk.createSwapchainKHR(self.device, swp_ci))
            self.assertIsNotNone(swap_chain)

            images = vk.getSwapchainImagesKHR(self.device, swap_chain)
            self.assertIsNotNone(images)
            components = vk.ComponentMapping(vk.VK_COMPONENT_SWIZZLE_R, vk.VK_COMPONENT_SWIZZLE_G, vk.VK_COMPONENT_SWIZZLE_B, vk.VK_COMPONENT_SWIZZLE_A)
            subresource_range = vk.ImageSubresourceRange(vk.VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1)
            image_views = []
            for img in images:
                ivci = vk.ImageViewCreateInfo(0, img, vk.VK_IMAGE_VIEW_TYPE_2D, format, components, subresource_range)
                iv = ESP(vk.createImageView(self.device, ivci))
                self.assertIsNotNone(iv)
                image_views.append(iv)

class TestRenderCube(unittest.TestCase):
    def test_render_colored_cube(self):
        cube_coords = get_xyzw_uv_cube_coords()
        with VkContextManager(vertex_data = cube_coords, surface_type = VkContextManager.VKC_WIN32) as vkc:
            self.assertIsNotNone(vkc)
            render_textured_cube(vkc,cube_coords,[1])

if __name__ == '__main__':
    app = QApplication(sys.argv) # the QApplication must be at this scope to avoid a crash in QT when some test case fails
    # set defaultTest to invoke a specific test case
    unittest.main(verbosity=2)
