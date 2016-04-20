import sys
import pyvulkan as vk
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from vkcontextmanager import VkContextManager, memory_type_from_properties, vkreleasing
from contextlib import contextmanager
from cube_data import *

class VkWidget(QWidget):
    def __init__(self, parent=None):
        super(VkWidget, self).__init__(parent)        
        self.cube_coords = get_xyzw_uv_cube_coords()
        self.vk_context = None
    
    def resizeEvent(self, event):
        super(VkWidget, self).resizeEvent(event)
        if self.vk_context is not None:
            self.vk_context.stack.close()
        
        self.vk_context = VkContextManager(VkContextManager.VKC_INIT_PIPELINE, self)
        self.vk_context.__enter__()

    def paintEvent(self, event):
        super(VkWidget, self).paintEvent(event)
        if self.vk_context is not None:
            self.paintVK()

    def stopVulkan(self):
        print('Closing Vulkan Context Stack')        
        self.vk_context.stack.close()
        self.vk_context = None

    def paintVK(self):
        if not self.isActiveWindow():
            return

        # any uncaught exception will crash python.exe because of the arbitrary order of wrapped objects destruction
        try:
            vk.beginCommandBuffer(self.vk_context.command_buffers[0],vk.CommandBufferBeginInfo(vk.VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT, None))
            self.vk_context.init_presentable_image()       
            self.vk_context.init_clear_color_and_depth()
            rp_begin = self.vk_context.make_render_pass_begin_info() 
            vk.cmdBeginRenderPass(self.vk_context.command_buffers[0], rp_begin, vk.VK_SUBPASS_CONTENTS_INLINE) 
            vk.cmdBindPipeline(self.vk_context.command_buffers[0], vk.VK_PIPELINE_BIND_POINT_GRAPHICS, self.vk_context.pipeline[0])
            vk.cmdBindDescriptorSets(self.vk_context.command_buffers[0], vk.VK_PIPELINE_BIND_POINT_GRAPHICS, self.vk_context.pipeline_layout, 0, self.vk_context.descriptor_set,  [])
            vk.cmdBindVertexBuffers(self.vk_context.command_buffers[0], 0, vk.VkBufferVector(1,self.vk_context.vertex_buffer), vk.VkDeviceSizeVector(1,0))                                
                
            self.vk_context.init_viewports()
            self.vk_context.init_scissors()
            vk.cmdDraw(self.vk_context.command_buffers[0], self.cube_coords.shape[0], 1, 0, 0)
            vk.cmdEndRenderPass(self.vk_context.command_buffers[0])
            vk.endCommandBuffer(self.vk_context.command_buffers[0])
            self.vk_context.execute_pre_present_barrier()
        
            with vkreleasing( vk.createFence(self.vk_context.device, vk.FenceCreateInfo(0)) ) as draw_fence:
                submit_info = vk.SubmitInfo( vk.VkSemaphoreVector(1,self.vk_context.present_complete_semaphore), vk.VkPipelineStageFlagsVector(1,vk.VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT), self.vk_context.command_buffers, vk.VkSemaphoreVector())                
                vk.queueSubmit(self.vk_context.device_queue, vk.VkSubmitInfoVector(1,submit_info), draw_fence)
                command_buffer_finished = False
                cmd_fences = vk.VkFenceVector(1,draw_fence)
                while not command_buffer_finished:
                    try:
                        vk.waitForFences(self.vk_context.device, cmd_fences, True, 1000000)
                        command_buffer_finished = True
                    except RuntimeError:
                        pass
                
                present_info = vk.PresentInfoKHR(vk.VkSemaphoreVector(), vk.VkSwapchainKHRVector(1, self.vk_context.swap_chain), [self.vk_context.current_buffer], vk.VkResultVector())
                vk.queuePresentKHR(self.vk_context.device_queue, present_info)        
        except:
            self.stopVulkan()
            raise

    def minimumSizeHint(self):
        return QSize(50, 50)

    def sizeHint(self):
        return QSize(640, 480)     

class Window(QWidget):
    def __init__(self):
        super(Window, self).__init__()
        self.setWindowTitle("Hello Vulkan")   
        self.vk_widget = VkWidget()
        main_layout = QHBoxLayout()
        main_layout.addWidget(self.vk_widget)
        self.setLayout(main_layout)

    def closeEvent(self, event):        
        self.vk_widget.stopVulkan()
        super(Window, self).closeEvent(event)
        
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())