import sys
import pyvulkan as vk
from cube_data import *
from winapp import win32_vk_main
from vkcontextmanager import vkreleasing

def render_textured_cube(vkc, cube_coords):
    vkc.init_presentable_image()       
    rp_begin = vkc.make_render_pass_begin_info() 
    vk.cmdBeginRenderPass(vkc.command_buffers[0], rp_begin, vk.VK_SUBPASS_CONTENTS_INLINE) 
    vk.cmdBindPipeline(vkc.command_buffers[0], vk.VK_PIPELINE_BIND_POINT_GRAPHICS, vkc.pipeline[0])
    vk.cmdBindDescriptorSets(vkc.command_buffers[0], vk.VK_PIPELINE_BIND_POINT_GRAPHICS, vkc.pipeline_layout, 0, vkc.descriptor_set,  [])
    vk.cmdBindVertexBuffers(vkc.command_buffers[0], 0, vk.VkBufferVector(1,vkc.vertex_buffer), vk.VkDeviceSizeVector(1,0))                                
                
    vkc.init_viewports()
    vkc.init_scissors()
    vk.cmdDraw(vkc.command_buffers[0], cube_coords.shape[0], 1, 0, 0)
    vk.cmdEndRenderPass(vkc.command_buffers[0])
    vkc.execute_pre_present_barrier()
    vk.endCommandBuffer(vkc.command_buffers[0])
            
    with vkreleasing( vk.createFence(vkc.device, vk.FenceCreateInfo(0)) ) as draw_fence:
        submit_info = vk.SubmitInfo( vk.VkSemaphoreVector(1,vkc.present_complete_semaphore), vk.VkPipelineStageFlagsVector(1,vk.VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT), vkc.command_buffers, vk.VkSemaphoreVector())                
        vk.queueSubmit(vkc.device_queue, vk.VkSubmitInfoVector(1,submit_info), draw_fence)
        command_buffer_finished = False
        cmd_fences = vk.VkFenceVector(1,draw_fence)
        present_info = vk.PresentInfoKHR(vk.VkSemaphoreVector(), vk.VkSwapchainKHRVector(1, vkc.swap_chain), [vkc.current_buffer], vk.VkResultVector())        
        while not command_buffer_finished:
            try:
                vk.waitForFences(vkc.device, cmd_fences, True, 1000000)
                command_buffer_finished = True
            except RuntimeError:
                pass
                
        vk.queuePresentKHR(vkc.device_queue, present_info)        
        
if __name__ == '__main__':
    cube_coords = get_xyzw_uv_cube_coords()
    def render_textured_cube_closure(vkc):
        render_textured_cube(vkc, cube_coords)
    win32_vk_main(render_textured_cube_closure)