# Spinning texture cube in Win32 window
# Copyright (C) 2016 by VLAM3D Software inc. https://www.vlam3d.com
# This code is licensed under the MIT license (MIT) (http://opensource.org/licenses/MIT)

import sys
import vulkanmitts as vk
import numpy as np
from cube_data import *
from winapp import win32_vk_main
from vkcontextmanager import vkreleasing, vkunmapping
from transforms import *

def animate_cube(vkc, frame_no):
    P = perspective(45.0, 1.0, 0.1, 100.0)
    V = look_at( np.array([5, 3, 10]), np.array([0, 0, 0]), np.array([0, -1, 0]) )
    M = np.eye(4)
    yrotate(M, float(frame_no[0] % 7200) / 20.0 )
    MVP = M.dot(V.dot(P)).astype(np.single)

    with vkunmapping( vk.mapMemory(vkc.device, vkc.uniform_buffer_mem , 0, MVP.nbytes, 0) ) as mapped_array:
        np.copyto(np.frombuffer(mapped_array.mem, dtype=np.single, count=len(MVP.flat)), MVP.flat)

def render_textured_cube(vkc, cube_coords, frame_no):
    vkc.init_presentable_image()
    rp_begin = vkc.make_render_pass_begin_info()
    vk.resetCommandBuffer(vkc.command_buffers[0],0)
    vk.beginCommandBuffer(vkc.command_buffers[0],vk.CommandBufferBeginInfo(0,None))
    vk.cmdBeginRenderPass(vkc.command_buffers[0], rp_begin, vk.VK_SUBPASS_CONTENTS_INLINE)
    vk.cmdBindPipeline(vkc.command_buffers[0], vk.VK_PIPELINE_BIND_POINT_GRAPHICS, vkc.pipeline[0])
    vk.cmdBindDescriptorSets(vkc.command_buffers[0], vk.VK_PIPELINE_BIND_POINT_GRAPHICS, vkc.pipeline_layout, 0, vkc.descriptor_set,  [])
    vk.cmdBindVertexBuffers(vkc.command_buffers[0], 0, vk.VkBufferVector(1,vkc.vertex_buffer), vk.VkDeviceSizeVector(1,0))

    vkc.init_viewports()
    vkc.init_scissors()
    vk.cmdDraw(vkc.command_buffers[0], cube_coords.shape[0], 1, 0, 0)
    vk.cmdEndRenderPass(vkc.command_buffers[0])
    vk.endCommandBuffer(vkc.command_buffers[0])

    with vkreleasing( vk.createFence(vkc.device, vk.FenceCreateInfo(0)) ) as draw_fence:
        submit_info_vec = vk.VkSubmitInfoVector()
        submit_info_vec.append( vk.SubmitInfo( vk.VkSemaphoreVector(1,vkc.present_complete_semaphore), vk.VkFlagVector(1,vk.VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT), vkc.command_buffers, vk.VkSemaphoreVector()) )
        vk.queueSubmit(vkc.device_queue, submit_info_vec, draw_fence)
        command_buffer_finished = False
        cmd_fences = vk.VkFenceVector(1,draw_fence)
        present_info = vk.PresentInfoKHR(vk.VkSemaphoreVector(), vk.VkSwapchainKHRVector(1, vkc.swap_chain), [vkc.current_buffer], vk.VkResultVector())
        while not command_buffer_finished:
            try:
                vk.waitForFences(vkc.device, cmd_fences, True, 100000000)
                command_buffer_finished = True
            except RuntimeError:
                pass

        vk.queuePresentKHR(vkc.device_queue, present_info)
        frame_no[0] = frame_no[0] + 1

        animate_cube(vkc, frame_no)

if __name__ == '__main__':
    cube_coords = get_xyzw_uv_cube_coords()
    frame_no = [0] # using a list in the closure because Int is immutable
    def render_textured_cube_closure(vkc):
        render_textured_cube(vkc, cube_coords, frame_no)
    win32_vk_main(render_textured_cube_closure, 16)