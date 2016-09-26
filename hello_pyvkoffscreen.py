# Copyright (C) 2016 by VLAM3D Software inc. https://www.vlam3d.com
# This code is licensed under the MIT license (MIT) (http://opensource.org/licenses/MIT)
from __future__ import print_function
import argparse
import pyvulkan as vk
import numpy as np
from cube_data import *
from vkcontextmanager import vkreleasing, VkContextManager
from transforms import *

def render_textured_cube(vkc, cube_coords):
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
    vkc.stage_readback_copy()  
    vk.endCommandBuffer(vkc.command_buffers[0])
            
    with vkreleasing( vk.createFence(vkc.device, vk.FenceCreateInfo(0)) ) as draw_fence:
        submit_info_vec = vk.VkSubmitInfoVector()
        submit_info_vec.append( vk.SubmitInfo( vk.VkSemaphoreVector(), vk.VkPipelineStageFlagsVector(1,vk.VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT), vkc.command_buffers, vk.VkSemaphoreVector()) )
        vk.queueSubmit(vkc.device_queue, submit_info_vec, draw_fence)
        command_buffer_finished = False
        cmd_fences = vk.VkFenceVector(1,draw_fence)
        while not command_buffer_finished:
            try:
                vk.waitForFences(vkc.device, cmd_fences, True, 100000000)
                command_buffer_finished = True
            except RuntimeError:
                pass  
            
    vkc.readback_map_copy()      
    vkc.save_readback_image('textured_cube.png')

def hello_pyvk(texture_file, output_img_file):
    cube_coords = get_xyzw_uv_cube_coords()
    print('Creating Vulkan Context')
    with VkContextManager(VkContextManager.VKC_INIT_PIPELINE, VkContextManager.VKC_OFFSCREEN) as vkc: 
        render_textured_cube(vkc,cube_coords)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Renders a textured cube to an image file.')
    parser.add_argument('--texture',type=str,default='lena_std.png',help='Path to image file for texture map')
    parser.add_argument('--outimg',type=str,default='hello_pyvk.png',help='Path to output image')

    args = parser.parse_args()

    hello_pyvk(args.texture, args.outimg)