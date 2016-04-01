import sys
import unittest
import pyglslang
from glsl_to_spv import *

class TestInit(unittest.TestCase):
    def test_init_glslang(self):        
        pyglslang.InitializeProcess()
        pyglslang.FinalizeProcess()

    def test_program(self):        
        pyglslang.InitializeProcess()        
        program = pyglslang.TProgram()       
        self.assertIsNotNone(program)
        pyglslang.FinalizeProcess()

    def test_glsl_version_string(self):
        version_string = pyglslang.GetGlslVersionString()
        self.assertIsNotNone(version_string)
        self.assertTrue(len(version_string) > 0)

    def test_essl_version_string(self):
        version_string = pyglslang.GetEsslVersionString()
        self.assertIsNotNone(version_string)
        self.assertTrue(len(version_string) > 0)

    def test_khronos_tool_id(self):
        tool_id = pyglslang.GetKhronosToolId()
        self.assertIsNotNone(tool_id)
        self.assertTrue(tool_id > 0)        

class TestShadersCtor(unittest.TestCase):
    def setUp(self):
        pyglslang.InitializeProcess()        
        return super().setUp()

    def test_vertex_shader(self):                
        shader = pyglslang.TShader(pyglslang.EShLangVertex) 
        self.assertIsNotNone(shader)       

    def test_tess_ctrl_shader(self):                
        shader = pyglslang.TShader(pyglslang.EShLangTessControl) 
        self.assertIsNotNone(shader)       

    def test_tess_eval_shader(self):                
        shader = pyglslang.TShader(pyglslang.EShLangTessEvaluation) 
        self.assertIsNotNone(shader)       

    def test_geo_shader(self):                
        shader = pyglslang.TShader(pyglslang.EShLangGeometry) 
        self.assertIsNotNone(shader)       

    def test_frag_shader(self):                
        shader = pyglslang.TShader(pyglslang.EShLangFragment) 
        self.assertIsNotNone(shader)       

    def test_compute_shader(self):                
        shader = pyglslang.TShader(pyglslang.EShLangCompute) 
        self.assertIsNotNone(shader)       

    def tearDown(self):
        pyglslang.FinalizeProcess()
        return super().tearDown()    
    
class TestGLSLToSPV(unittest.TestCase):
    def setUp(self):
        with open('vertex_shader.glsl','r') as  vs_in:
            self.vs_txt = vs_in.read()

        with open('fragment_shader.glsl','r') as  fs_in:
            self.fs_txt = fs_in.read()

    def test_vertex_shader_to_spv(self):        
        spv = glsl_to_spv(pyglslang.EShLangVertex, self.vs_txt)

    def test_vertex_shader_to_spv(self):        
        spv = glsl_to_spv(pyglslang.EShLangFragment, self.fs_txt)
        
    def tearDown(self):
        return super().tearDown()

if __name__ == '__main__':
    # set defaultTest to invoke a specific test case
    unittest.main()