#!/usr/bin/env python
# 
# Generate the SWIG interface file to generate pythonic bindings for the Vulkan API
# 
# Copyright (C) 2016 by VLAM3D Software inc. https://www.vlam3d.com
# 
# This code is licensed under the MIT license (MIT) (http://opensource.org/licenses/MIT)
# 
import sys
import re
import os
from reg import *
from generator import *

array_size_re = re.compile('\[(\w+)\]')

# assume param is lxml element
def get_param_name(param):
    param_name = param.find('name')    
    return noneStr(param_name.text)

def get_param_type(param):
    param_type = param.find('type')    
    return noneStr(param_type.text)

def is_param_pointer(param):
    ispointer = False
    paramtype = param.find('type')
    ptr_depth = 0 # const char* pAppName => 1, const char* const * ppEnabledLayerNames => 2
    if paramtype.tail is not None and '*' in paramtype.tail:
        ispointer = True
        ptr_depth = paramtype.tail.count('*')
    
    is_const_ptr = False
    if noneStr(param.text).find('const') != -1:
        is_const_ptr = True

    return ispointer, is_const_ptr, ptr_depth

def is_param_c_array(param):
    iscarray = False
    num_elem = -1
    paramtype = param.find('name')
    if paramtype.tail is not None:
        m = array_size_re.search(paramtype.tail)
        if m:
            iscarray = True
            num_elem = m.group(1)
        elif '[' in paramtype.tail:
            enum = param.find('enum')
            if enum is not None and enum.text is not None:
                iscarray = True
                num_elem =  enum.text
    
    return iscarray, num_elem


def remove_vk_prefix(identifier):
    return identifier[2].lower() + identifier[3:]

def maker_name(struct_identifier):
    return struct_identifier[2:]

def p_name_to_str(identifier):
    return 'str' + identifier[1:]

def p_name_to_handle(identifier):
    return 'h' + identifier[1:]

def p_name_to_vec(identifier):
    if identifier[0:2] == 'pp':
        return 'vec' + identifier[2:]
    return 'vec' + identifier[1:]

def p_name_to_vec_ptr(identifier):
    if identifier[0:2] == 'pp':
        return 'vecPtr' + identifier[2:]
    return 'vecPtr' + identifier[1:]

def p_name_to_val(identifier):
    return identifier[1].lower() + identifier[2:]

def is_param_const(param):
    if param.text is not None:
        return 'const' in param.text
    return False

# this works for V1.0 - we could parse the comment field in vk.xml  - don't know which will be more robust to change
def struct_typename_to_VkStructureType_enum(struct_typename):
    enum_string = "VK_STRUCTURE_TYPE"
    for i,c in enumerate(struct_typename[2:]):
        if i < len(struct_typename)-1:
            if c.isupper() and (struct_typename[i+1].islower() or struct_typename[i+1].isdigit()) :
                enum_string += '_'
                enum_string += c
            else:
                enum_string += c.upper()
        else:
            enum_string += c.upper()

    return enum_string

def findAllocatedPtrType(is_alloc, params):
    allocated_ptr_type = None
    if not is_alloc:
        return allocated_ptr_type

    return_ptr_index = -1
    param_to_const_referentize = set() # to switch the interface from const T * to const T&
    for i,p in enumerate(params):
        is_ptr, is_const, ptr_depth = is_param_pointer(p)
        if is_ptr and not is_const:
            allocated_ptr_type = get_param_type(p)
            return_ptr_index = i
        elif is_ptr and is_const and get_param_type(p) != 'char':
            param_to_const_referentize.add(i)

    assert(allocated_ptr_type is not None and return_ptr_index != -1)   
    return allocated_ptr_type      

# CSWIGOutputGenerator - subclass of OutputGenerator.
# Generates a SWIG interface file
#
# ---- methods ----
# CSWIGOutputGenerator(errFile, warnFile, diagFile) - args as for
#   OutputGenerator. Defines additional internal state.
# ---- methods overriding base class ----
# beginFile(genOpts)
# endFile()
# beginFeature(interface, emit)
# endFeature()
# genType(typeinfo,name)
# genStruct(typeinfo,name)
# genGroup(groupinfo,name)
# genEnum(enuminfo, name)
# genCmd(cmdinfo)
class CSWIGOutputGenerator(COutputGenerator):
    def __init__(self,
                 errFile = sys.stderr,
                 warnFile = sys.stderr,
                 diagFile = sys.stdout):
        COutputGenerator.__init__(self, errFile, warnFile, diagFile)
        self.shared_ptr_types = set()
        self.std_vector_types = set()
        self.swigImpl = []
        self.fctPtrDecl = []
        self.skippedCommands = []
        self.handleTypes = set()
        self.vectorOfHandleTypes = set()
        # types that must not be in the generated interface file because their SWIG generate wrappers are not what we want
        # they are handle arrays where all handles are allocated and deallocated in batch
        # via SWIG standard library typemaps we can either have an array of dumb handles or an array of shared_ptr, so we have to make some customization
        self.hideFromSWIGTypes = set(['VkCommandBuffer', 'VkDescriptorSet'])
        # here we map the base type for a x64 architecture to match numpy.i typemaps
        self.arrayBaseTypes = {'size_t':'unsigned long long', 'uint32_t' : 'unsigned int', 'float' : 'float', 'int32_t': 'int' }
        # the base types that we can encounter in the interface, not the list of a C/C++ base types
        # they are augmented using the registry info, these types are known to be cheap to copy, so passed and returned by value 
        self.copyableBaseTypes = set(self.arrayBaseTypes.keys())
        self.applyARRAY1types = set()
        self.structTypes = set()
        self.structCArrayTypes = set()
        self.nonRAIIStruct = set()

        # list the functions ptrs not loaded by the Lunar Vulkan SDK on Windows
        self.notLoadedBySDK = [ 'vkGetPhysicalDeviceDisplayPropertiesKHR',
                                'vkGetPhysicalDeviceDisplayPlanePropertiesKHR',
                                'vkGetDisplayPlaneSupportedDisplaysKHR',
                                'vkGetDisplayModePropertiesKHR',
                                'vkCreateDisplayModeKHR',
                                'vkGetDisplayPlaneCapabilitiesKHR',
                                'vkCreateDisplayPlaneSurfaceKHR',
                                'vkCreateSharedSwapchainsKHR', 
                                'vkCreateDebugReportCallbackEXT',
                                'vkDestroyDebugReportCallbackEXT',
                                'vkDebugReportMessageEXT']        
        self.loadPtrs = """
    void load_vulkan_fct_ptrs()
    {
        VkApplicationInfo appInfo = {};
	    appInfo.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
	    appInfo.pApplicationName = "genswigi";
	    appInfo.pEngineName = "genswigi";
	    appInfo.apiVersion = VK_MAKE_VERSION(1, 0, 3);

	    VkInstanceCreateInfo instanceCreateInfo = {};
	    instanceCreateInfo.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
	    instanceCreateInfo.pNext = NULL;
	    instanceCreateInfo.pApplicationInfo = &appInfo;
	
        VkInstance instance;
        vkCreateInstance(&instanceCreateInfo, nullptr, &instance);
"""
        for command_name in self.notLoadedBySDK:
            self.loadPtrs += '	    pf%(command_name)s = reinterpret_cast<PFN_%(command_name)s>(vkGetInstanceProcAddr(instance, "%(command_name)s"));\n' % locals()

        self.loadPtrs += "  }\n"
        self.loadPtrs += "%}\n"
    
    def findBaseTypes(self):
        all_types = self.registry.findall("types/type")
        for type in all_types:
            if 'category' in type.keys() and 'basetype' in type.get('category'):
                for child in type:
                    if child.tag == 'name':
                        self.copyableBaseTypes.add(child.text)

    def findHandleTypes(self):
        all_types = self.registry.findall("types/type")
        for type in all_types:
            if 'category' in type.keys() and 'handle' in type.get('category'):
                for child in type:
                    if child.tag == 'name':
                        if child.text not in self.hideFromSWIGTypes:
                            self.handleTypes.add(child.text)

    def findStructTypes(self):
        all_types = self.registry.findall("types/type")
        for type in all_types:
            if 'category' in type.keys() and 'struct' in type.get('category'):
                typename = type.get('name')
                if typename not in self.hideFromSWIGTypes:
                    self.structTypes.add(typename)
    
    def findParamsAndMembersCArray(self):
        all_params = self.registry.findall("commands/command/param")
        all_params.extend(self.registry.findall("types/type/member"))
        for param in all_params:
            is_c_array, num_element = is_param_c_array(param)
            if is_c_array:
                type = get_param_type(param)
                name = get_param_name(param)
                if type in self.structTypes:
                    self.structCArrayTypes.add(type)

    def findNonRAIIStruct(self):
        all_types = self.registry.findall("types/type")
        for type in all_types: 
            if 'category' in type.keys() and 'struct' in type.get('category'):
                typename = type.get('name')
                if typename not in self.hideFromSWIGTypes:
                    members = type.findall('.//member')
                    members_name_type = [ (get_param_name(m),get_param_type(m)) for m in members]
                    for m in members:
                        if 'len' in m.keys():
                            if 'null-terminated' in m.get('len'):
                                self.nonRAIIStruct.add(typename)
                                break
                            else:
                                len_members = m.get('len').split(',')
                                for len_member in len_members:
                                    nt_pair = (len_member, 'uint32_t')
                                    if nt_pair in members_name_type:  
                                        self.nonRAIIStruct.add(typename)
                                        break
                        else:
                            member_type_name = get_param_type(m)
                            is_ptr, is_const, ptr_depth = is_param_pointer(m) 
                            if  is_ptr and is_const and member_type_name != 'void':
                                self.nonRAIIStruct.add(typename)
                                break       

    def beginFile(self, genOpts):
        self.outdir = os.path.dirname(genOpts.filename)
        OutputGenerator.beginFile(self, genOpts)
        if (genOpts.prefixText):
            for s in genOpts.prefixText:
                write(s, file=self.outFile)
        write('// Begin content generated by genswigi.py', file=self.outFile)    
        write('const char* vkGetErrorString(VkResult retval);', file=self.outFile)                
        self.newline()
        self.findStructTypes()
        self.findHandleTypes()
        self.findBaseTypes()
        self.getVkStructureTypes()        
        self.findParamsAndMembersCArray()
        self.findNonRAIIStruct()

    def getVkStructureTypes(self):
        self.structure_type_enum_strings = set()
        all_enums = self.registry.findall("enums")
        vk_error_code_comments = []
        for enum in all_enums:
            if 'VkStructureType' in enum.get('name'):
                for e in enum:
                    enum_string = e.get('name')
                    if enum_string is not None:
                        self.structure_type_enum_strings.add(enum_string)                        

    def writeVkErrorStringImpl(self):
        all_enums = self.registry.findall("enums")
        vk_error_code_comments = []
        for enum in all_enums:
            if 'VkResult' in enum.get('name'):
                for e in enum:
                    # this is from generator.py it removes the extension enum that won't be in the default vulkan.h header
                    if (e.get('extname') is None or re.match(self.genOpts.addExtensions, e.get('extname')) is not None 
                                                 or self.genOpts.defaultExtensions == e.get('supported')) and e.get('name') is not None:
                        
                        if e.get('comment') is not None:
                            vk_error_code_comments.append( (e.get('name'), ("Vulkan error (%s) : " % e.get('name'))  + e.get('comment') ) )
                        else:
                            vk_error_code_comments.append( (e.get('name'), "Vulkan error: " + e.get('name') ) )

        max_str_len = max([len(c) for n,c in vk_error_code_comments])
        write('     const char* vkGetErrorString(VkResult retval)', file=self.outFile)
        write('     {', file=self.outFile)
        write('         static const char vk_err_messages[%d][%d] = {' % (len(vk_error_code_comments),max_str_len+1) , file=self.outFile)
        for n,c in vk_error_code_comments:
            write('             "%s",' % c , file=self.outFile)
        write('         };', file=self.outFile)
        write('         switch (retval) {', file=self.outFile)
        for i, nc in enumerate(vk_error_code_comments):
            write('             case %s : return vk_err_messages[%d];' % (nc[0],i) , file=self.outFile)
        write('         }', file=self.outFile)
        write('         return nullptr;', file=self.outFile)
        write('     }', file=self.outFile)

    def endFile(self):        
        write("%{\n", file=self.outFile)
        self.writeVkErrorStringImpl()
        write(' \n'.join(self.fctPtrDecl), end='', file=self.outFile)
        write(self.loadPtrs, file=self.outFile)
        write('%{\n', file=self.outFile)
        write('\n'.join(self.swigImpl), end='', file=self.outFile)
        write('%}\n', file=self.outFile)
       
        for type_name in self.nonRAIIStruct:
            write('%%template (%(type_name)sPtr) std::shared_ptr<%(type_name)sRAII>;\n' % locals(), file=self.outFile)
            
        for type_name in self.std_vector_types:
            if not type_name in ['void','uint32_t','char']:
                if type_name not in self.nonRAIIStruct:
                    write('%%template (%(type_name)sVector) std::vector<%(type_name)s>;\n' % locals(), file=self.outFile)
                else:                    
                    write('%%template (%(type_name)sVector) std::vector< std::shared_ptr<%(type_name)sRAII> >;\n' % locals(), file=self.outFile)

        for type_name in self.vectorOfHandleTypes:
                write("%%template (%(type_name)sHandleVector) std::vector< std::shared_ptr< %(type_name)s_T > >;\n" % locals(), file=self.outFile)

        write('// Skipped commands that must be manually wrapped', file=self.outFile)        
        write('//' + '\n//'.join(self.skippedCommands), end='\n', file=self.outFile)
        write('// End content generated by genswigi.py', file=self.outFile)        
        # Finish processing in superclass
        OutputGenerator.endFile(self)        
        shared_ptrs_ixx_file = os.path.join(self.outdir, 'shared_ptrs.ixx')
        with open(shared_ptrs_ixx_file,'w') as file_out:
            file_out.write("%carray_of_float(float)\n")
            file_out.write("%carray_of_long(int32_t)\n")
            file_out.write("%carray_of_long(uint32_t)\n")
            for t in self.structCArrayTypes:
                file_out.write("%%carray_of_struct(%s)\n" % t)
            
            for t in self.handleTypes:
                file_out.write("%%ref_counted_handle(%s)\n" % t)            

            for t in self.shared_ptr_types:
                if t != 'void':
                    file_out.write("%%shared_ptr(%s)\n" % t)

            for t in self.nonRAIIStruct:
                file_out.write("%%raii_struct(%s)\n" % t)

            file_out.write("\n")
            for t in self.applyARRAY1types:
                base_type = t[0]
                typename = t[1]
                file_out.write("%%apply (%(base_type)s* IN_ARRAY1, int DIM1) {(%(base_type)s* %(typename)s_in_array1, int %(typename)s_dim1)};\n" % locals())
                
    
    def beginFeature(self, interface, emit):
        # Start processing in superclass
        COutputGenerator.beginFeature(self, interface, emit)   
        self.swigFeatureImpl = []     

    def endFeature(self):
        # Finish processing in superclass
        if (self.genOpts.protectFeature):
            self.swigImpl.append('#ifdef ' + self.featureName)
        
        if (self.featureExtraProtect != None):
            self.swigImpl.append('#ifdef ' + self.featureExtraProtect)
        
        self.swigImpl += self.swigFeatureImpl

        if self.featureExtraProtect != None:
            self.swigImpl.append('#endif /* '+ self.featureExtraProtect + '*/')
                
        if (self.genOpts.protectFeature):
            self.swigImpl.append('#endif /* '+ self.featureName + '*/')

        COutputGenerator.endFeature(self)
                        
        
    def genType(self, typeinfo, name):
        if name not in self.hideFromSWIGTypes:
            COutputGenerator.genType(self, typeinfo, name)

    def genStruct(self, typeinfo, typeName):
        COutputGenerator.genStruct(self, typeinfo, typeName)

        members = typeinfo.elem.findall('.//member')
        n = len(members)

        members_name_type = [ (get_param_name(m),get_param_type(m)) for m in members]
        members_to_remove = set()
        members_to_vectorize = set()
        members_to_shared_ptrize = set()
        count_member_to_vector_member = {}
        structure_type_member_index = -1
        for i,m in enumerate(members):            
            if 'len' in m.keys():                
                len_members = m.get('len').split(',')
                for len_member in len_members:
                    nt_pair = (len_member, 'uint32_t')
                    if nt_pair in members_name_type:  
                        l_pair = (i, members_name_type.index(nt_pair))                  
                        if typeName not in ['VkWriteDescriptorSet','VkDescriptorSetLayoutBinding']:
                            members_to_remove.add(l_pair[1])                       
                            if l_pair[1] not in count_member_to_vector_member:                            
                                count_member_to_vector_member[ l_pair[1] ] = l_pair[0]
                            else:                            
                                print(typeName, ' member', members_name_type[i][0], ' size is not used ' )

                        members_to_vectorize.add(l_pair[0])

                        if members_name_type[i][1] != 'void' and members_name_type[i][1] not in self.hideFromSWIGTypes:
                            self.std_vector_types.add( members_name_type[i][1] )
            else:
                member_name,member_type_name = members_name_type[i]
                is_ptr, is_const, ptr_depth = is_param_pointer(m) 
                if  is_ptr and is_const and member_type_name != 'char':
                    members_to_shared_ptrize.add(i)

        for i,member in enumerate(members):
            member_type_name = get_param_type(member)         
            if member_type_name == 'void':  
                members_to_remove.add(i)
            elif member_type_name == 'VkStructureType':
                structure_type_member_index = i
                members_to_remove.add(i)

        vkstructureenumstring = "VK_STRUCTURE_TYPE_MAX_ENUM" # invalid value
        if structure_type_member_index != -1:
            enum_string = struct_typename_to_VkStructureType_enum(typeName)
            if enum_string in self.structure_type_enum_strings:
                vkstructureenumstring = enum_string
            else:
                print('Warning: %s not found in the VkStructure enum elements' % enum_string)
        
        kept_members = len(members) - len(members_to_remove)

        swig_maker_name = maker_name(typeName)
        raii_type_name = typeName + 'RAII'
        raii_struct_body = typeinfo.elem.get('category') + ' ' + raii_type_name + ' {\n'
        raii_struct_body += "   %(typeName)s nonRaiiObj;\n" % locals()        
        raii_struct_req = False
        written_cnt = 0
        if n > 0:
            indentdecl = '(\n'
            for i in range(0,n):    
                member_name, member_type_name = members_name_type[i]
                is_ptr, is_const, ptr_depth = is_param_pointer(members[i])
                assert(ptr_depth <= 2) # hopefully
                if i in members_to_remove:
                    continue
                elif i in members_to_vectorize:
                    vec_ele_type_name = member_type_name
                    if member_type_name == 'char':
                        vec_ele_type_name = 'std::string'
                    
                    if member_type_name in self.arrayBaseTypes:
                        numpy_array_type = self.arrayBaseTypes[member_type_name]
                        self.applyARRAY1types.add((numpy_array_type,member_name))
                        paramdecl = '    %(numpy_array_type)s* %(member_name)s_in_array1, int %(member_name)s_dim1' % locals()
                    else:
                        paramdecl = '    const std::vector<%(vec_ele_type_name)s> &' % locals()
                        paramdecl = paramdecl.rstrip()
                        paramdecl = paramdecl.ljust(48)
                        paramdecl += p_name_to_vec(member_name)

                    memberdecl = '    std::vector<%(vec_ele_type_name)s>'  % locals()
                    memberdecl = memberdecl.rstrip()
                    memberdecl = memberdecl.ljust(48)
                    memberdecl += p_name_to_vec(member_name)
                    raii_struct_body += memberdecl + ';\n'
                    if is_ptr and ptr_depth == 2:
                        memberdecl = '    std::vector<const %(member_type_name)s *>'  % locals()
                        memberdecl = memberdecl.rstrip()
                        memberdecl = memberdecl.ljust(48)
                        memberdecl += p_name_to_vec_ptr(member_name)
                        raii_struct_body += memberdecl + ';\n'

                    raii_struct_req = True
                    written_cnt += 1
                elif i in members_to_shared_ptrize:
                    if member_type_name in self.nonRAIIStruct:
                        paramdecl = '    const std::shared_ptr<%(member_type_name)sRAII> &' % locals()
                    else:
                        paramdecl = '    const %(member_type_name)s *' % locals()
                    paramdecl = paramdecl.rstrip()
                    paramdecl = paramdecl.ljust(48)                    
                    paramdecl += member_name
                    if member_type_name in self.nonRAIIStruct:                        
                        memberdecl = '    std::shared_ptr<%(member_type_name)sRAII>'  % locals()
                    else:
                        memberdecl = '    std::shared_ptr<%(member_type_name)s>'  % locals()
                    memberdecl = memberdecl.rstrip()
                    memberdecl = memberdecl.ljust(48)
                    memberdecl += member_name
                    raii_struct_body += memberdecl + ';\n'
                    raii_struct_req = True
                    written_cnt += 1
                elif member_type_name == "char" and is_ptr :
                    paramdecl = '    const std::string &'
                    paramdecl = paramdecl.rstrip()
                    paramdecl = paramdecl.ljust(48)
                    paramdecl += p_name_to_str(member_name)
                    memberdecl = '    std::string'
                    memberdecl = memberdecl.rstrip()
                    memberdecl = memberdecl.ljust(48)
                    memberdecl += p_name_to_str(member_name)
                    raii_struct_body += memberdecl + ';\n'
                    raii_struct_req = True
                    written_cnt += 1
                else:
                    paramdecl = self.makeCParamDecl(members[i], self.genOpts.alignFuncParam)                    
                    written_cnt += 1

                if (written_cnt < kept_members):
                    paramdecl += ',\n'
                else:
                    paramdecl += ')'

                indentdecl += paramdecl
        else:
            indentdecl = '(void)'

        raii_struct_body += '};\n'

        if raii_struct_req:
            assert( typeName in self.nonRAIIStruct )
            indentdecl = "std::shared_ptr<%(raii_type_name)s> %(swig_maker_name)s" % locals() + indentdecl;
            self.appendSection('struct', raii_struct_body)
        else:
            assert(typeName not in self.nonRAIIStruct)
            indentdecl = "%(typeName)s %(swig_maker_name)s" % locals() + indentdecl;
            self.copyableBaseTypes.add(typeName)

        fct_decl = indentdecl + ';\n'
        swig_impl = indentdecl + '\n'
        swig_impl += '   {\n'
        if raii_struct_req:
            swig_impl += '      std::shared_ptr<%(raii_type_name)s> raii_obj(new %(raii_type_name)s);\n' % locals()
            for i,member in enumerate(members):
                member_name, member_type_name = members_name_type[i]   
                is_ptr, is_const, ptr_depth = is_param_pointer(member)             
                if i in members_to_remove:
                    if i in count_member_to_vector_member:
                        vector_member_index = count_member_to_vector_member[i]
                        vector_member_name_type = members_name_type[vector_member_index]
                        param_name = vector_member_name_type[0]
                        vector_member_name = p_name_to_vec(vector_member_name_type[0])
                        if vector_member_name_type[1] in self.arrayBaseTypes:
                            swig_impl += '      raii_obj->nonRaiiObj.%(member_name)s = static_cast<uint32_t>(%(param_name)s_dim1);\n' % locals()
                        else:
                            swig_impl += '      raii_obj->nonRaiiObj.%(member_name)s = static_cast<uint32_t>(%(vector_member_name)s.size());\n' % locals()
                    elif i == structure_type_member_index:
                        swig_impl += '      raii_obj->nonRaiiObj.%(member_name)s = %(vkstructureenumstring)s;\n' % locals()
                    else:
                        swig_impl += '      raii_obj->nonRaiiObj.%(member_name)s = nullptr;\n' % locals()
                elif i in members_to_vectorize:
                    vec_name = p_name_to_vec(member_name)                    
                    if member_type_name in self.arrayBaseTypes:
                        swig_impl += '      raii_obj->%(vec_name)s.assign(%(member_name)s_in_array1, %(member_name)s_in_array1 + %(member_name)s_dim1);\n' % locals()
                    else:
                        swig_impl += '      raii_obj->%(vec_name)s = %(vec_name)s;\n' % locals()
                    if ptr_depth == 2 and member_type_name == 'char':
                        vec_ptr_name = p_name_to_vec_ptr(member_name)
                        swig_impl += '      raii_obj->%(vec_ptr_name)s.resize(%(vec_name)s.size());\n' % locals()
                        swig_impl += '      for (size_t i=0; i<%(vec_name)s.size(); ++i) \n' % locals()
                        swig_impl += '           raii_obj->%(vec_ptr_name)s[i] = raii_obj->%(vec_name)s[i].c_str();\n' % locals()
                        swig_impl += '      raii_obj->nonRaiiObj.%(member_name)s = &raii_obj->%(vec_ptr_name)s[0];\n' % locals()
                    else:
                        swig_impl += '      if ( raii_obj->%(vec_name)s.size() > 0)\n' % locals()
                        swig_impl += '      {\n'
                        swig_impl += '          raii_obj->nonRaiiObj.%(member_name)s = &raii_obj->%(vec_name)s[0];\n' % locals()
                        swig_impl += '      }\n'
                        swig_impl += '      else\n'
                        swig_impl += '      {\n'
                        swig_impl += '          raii_obj->nonRaiiObj.%(member_name)s = nullptr;\n' % locals()
                        swig_impl += '      }\n'
                elif i in members_to_shared_ptrize:                    
                    if member_type_name in self.nonRAIIStruct:
                        swig_impl += '      raii_obj->%(member_name)s = %(member_name)s;\n' % locals()
                        swig_impl += '      if ( %(member_name)s ) \n' % locals()
                        swig_impl += '      {\n'
                        swig_impl += '          raii_obj->nonRaiiObj.%(member_name)s = &(%(member_name)s->nonRaiiObj);\n' % locals()
                        swig_impl += '      }\n'
                        swig_impl += '      else\n'
                        swig_impl += '      {\n'
                        swig_impl += '          raii_obj->nonRaiiObj.%(member_name)s = nullptr;\n' % locals()
                        swig_impl += '      }\n'
                    else:
                        swig_impl += '      raii_obj->nonRaiiObj.%(member_name)s = nullptr;\n' % locals()
                        swig_impl += '      if ( %(member_name)s ) \n' % locals()
                        swig_impl += '      { \n' % locals()
                        swig_impl += '          raii_obj->%(member_name)s.reset( new %(member_type_name)s );\n' % locals()
                        swig_impl += '          *raii_obj->%(member_name)s = *%(member_name)s;\n' % locals()
                        swig_impl += '          raii_obj->nonRaiiObj.%(member_name)s = raii_obj->%(member_name)s.get();\n' % locals()
                        swig_impl += '      } \n' % locals()
                elif member_type_name == "char" and is_ptr :
                    std_string_name = p_name_to_str(member_name)
                    swig_impl += '      raii_obj->%(std_string_name)s = %(std_string_name)s;\n' % locals()
                    swig_impl += '      raii_obj->nonRaiiObj.%(member_name)s = &raii_obj->%(std_string_name)s[0];\n' % locals()
                else:
                    is_c_array, num_elem = is_param_c_array(member)
                    if is_c_array:
                        swig_impl += '      std::copy(%(member_name)s, %(member_name)s + %(num_elem)s, raii_obj->nonRaiiObj.%(member_name)s);\n' % locals()
                    else:
                        swig_impl += '      raii_obj->nonRaiiObj.%(member_name)s = %(member_name)s;\n' % locals()
        
            swig_impl += '      return raii_obj;\n'
        else:
            swig_impl += '      %(typeName)s obj;\n' % locals()
            for member in members:
                member_type_name = get_param_type(member)
                is_ptr, is_const, ptr_depth = is_param_pointer(member)
                assert(ptr_depth <= 1)
                is_c_array, num_elem = is_param_c_array(member)
                member_name = get_param_name(member)
                if member_type_name == "void":
                    swig_impl += '      obj.%(member_name)s = nullptr;\n' % locals()
                elif member_type_name == "VkStructureType":
                    swig_impl += '      obj.%(member_name)s = %(vkstructureenumstring)s;\n' % locals()
                elif is_c_array:
                    swig_impl += '      std::copy(%(member_name)s, %(member_name)s + %(num_elem)s, obj.%(member_name)s);\n' % locals()
                # this seems absurd in VkShaderModuleCreateInfo "pCode" is an unsigned int pointer but "codeSize" must still be specified in bytes
                # the workaround is implemented here because we still need the ctor to be generated 
                elif member_name == 'codeSize':
                    swig_impl += '      obj.%(member_name)s = %(member_name)s * sizeof(unsigned int);\n' % locals()
                else:
                    swig_impl += '      obj.%(member_name)s = %(member_name)s;\n' % locals()
            swig_impl += '      return obj;\n'
        swig_impl += '   }\n'
        self.appendSection('command', fct_decl + '\n')
        
        if raii_struct_req:
            self.swigFeatureImpl.append(raii_struct_body)

        self.swigFeatureImpl.append(swig_impl)        

    def genGroup(self, groupinfo, groupName):
        COutputGenerator.genGroup(self, groupinfo, groupName)

    def genEnum(self, enuminfo, name):
        COutputGenerator.genEnum(self, enuminfo, name)

    def genNoArgoutCommand(self, return_type_str, command_name, params):
        swig_command_name = remove_vk_prefix(command_name)

    def findFreeCommand(self, is_alloc, command_name):      
        if not is_alloc:
            return None, None

        if command_name == 'vkCreateGraphicsPipelines' or command_name == 'vkCreateComputePipelines' :
            free_command_name = 'vkDestroyPipeline'
        else:
            free_command_name = command_name.replace('Create','Destroy')
            free_command_name = free_command_name.replace('Allocate','Free')

        # find the destroy or free command associated with this create or allocate command
        all_commands = self.registry.findall("commands/command")
        free_command_elem = None
        for cmd in all_commands:
            proto = cmd.find('proto')
            inner_command_name = proto[1].text
            if inner_command_name == free_command_name:
                free_command_elem = cmd
                break

        free_command_params_name_type = []
        if free_command_elem is not None:
            free_command_params = free_command_elem.findall('param')
            free_command_params_name_type = [ (get_param_name(p),get_param_type(p)) for p in free_command_params]
        else:
            return None,None
            
        return free_command_name, free_command_params_name_type  

    def genCommand(self,
                   return_type_str, 
                   command_name, 
                   is_allocation_cmd,
                   params, 
                   params_name_type, 
                   params_to_remove, 
                   input_params_to_vectorize, 
                   argout_params_to_vectorize, 
                   params_to_const_refitize, 
                   params_to_shared_ptrize, 
                   params_to_return_as_handle, # in this methods handles are all expected to behave like accessor that don't require special cleanup
                   param_to_return_as_vector_of_handle,
                   params_to_return_by_value,
                   count_to_vector_param_map  ):

        # don't create explicit bindings for deallocation commands, they are triggered automatically by the wrapper's dtor (RAII)
        if command_name.find('Destroy') != -1 or command_name.find('Free') != -1:
            return 

        n = len(params)
        n_passed_params = n - len(params_to_remove) - len(argout_params_to_vectorize) - len(params_to_shared_ptrize) - len(params_to_return_by_value) - len(params_to_return_as_handle) - len(param_to_return_as_vector_of_handle)
        n_argout_params = len(argout_params_to_vectorize) + len(params_to_shared_ptrize) + len(params_to_return_by_value) + len(params_to_return_as_handle) + len(param_to_return_as_vector_of_handle)

        free_command_name, free_command_params_name_type = self.findFreeCommand(is_allocation_cmd, command_name)

        swig_command_name = remove_vk_prefix(command_name)
        tuple_decl = ""
        
        # RETURN TYPE
        if n_argout_params == 0:
            indentdecl = "void " 
        elif n_argout_params == 1:
            if len(argout_params_to_vectorize) == 1:
                argout_type = params_name_type[ list(argout_params_to_vectorize)[0] ][1]
                indentdecl = "std::vector< %(argout_type)s >" % locals()
            elif len(params_to_shared_ptrize) == 1:
                argout_type = params_name_type[ list(params_to_shared_ptrize)[0] ][1]
                indentdecl = "std::shared_ptr< %(argout_type)s >" % locals()
            elif not is_allocation_cmd and len(params_to_return_as_handle) == 1:
                argout_type = params_name_type[ list(params_to_return_as_handle)[0] ][1]
                indentdecl = "%(argout_type)s" % locals()
            elif is_allocation_cmd :
                if len(params_to_return_as_handle) == 1:
                    argout_type = params_name_type[ list(params_to_return_as_handle)[0] ][1]
                    indentdecl = "std::shared_ptr<%(argout_type)s_T>" % locals()
                else:
                    assert(len(param_to_return_as_vector_of_handle) == 1)
                    argout_type = params_name_type[ list(param_to_return_as_vector_of_handle)[0] ][1]
                    indentdecl = "std::vector< std::shared_ptr<%(argout_type)s_T> >" % locals()
            else: 
                argout_type = params_name_type[ list(params_to_return_by_value)[0] ][1]
                indentdecl = "%(argout_type)s" % locals()
        else:
            assert(False) # tuple return not yet needed

        indentdecl += ' %(swig_command_name)s' % locals()
        freeparams = ""

        # C++ FUNCTION PROTOTYPE 
        if n_passed_params == 0:
            indentdecl += '(void)'
        else:
            written_cnt = 0
            indentdecl += '(\n'
            for i in range(0,n):
                input_param_name, input_param_type = params_name_type[i]
                is_ptr, is_const, ptr_depth = is_param_pointer(params[i]) 
                is_c_array, num_elem = is_param_c_array(params[i]) 
                if i in params_to_remove or i in argout_params_to_vectorize or i in params_to_shared_ptrize or i in params_to_return_by_value or i in params_to_return_as_handle  or i in param_to_return_as_vector_of_handle :
                    continue
                elif i in input_params_to_vectorize:
                    if input_param_type != 'void':
                        if not input_param_type in self.arrayBaseTypes:
                            indentdecl += '        const std::vector<%(input_param_type)s> & %(input_param_name)s' % locals()
                        else:
                            numpy_array_type = self.arrayBaseTypes[input_param_type]
                            indentdecl += '        %(numpy_array_type)s* %(input_param_name)s_in_array1, int %(input_param_name)s_dim1' % locals()
                            self.applyARRAY1types.add((numpy_array_type,input_param_name))
                    else:
                        indentdecl += '        const std::vector<unsigned char> & %(input_param_name)s' % locals()
                    written_cnt += 1
                elif i in params_to_const_refitize:
                    indentdecl += '        const %(input_param_type)s & %(input_param_name)s' % locals()
                    written_cnt += 1
                else:
                    if is_allocation_cmd and free_command_params_name_type is not None and (get_param_name(params[i]),get_param_type(params[i])) in free_command_params_name_type :
                        freeparams += get_param_name(params[i]) + ','

                    if is_ptr:
                        input_param_type += '*'
                    if is_const:
                        input_param_type = 'const ' + input_param_type
                    if is_c_array:
                        input_param_name += '[%(num_elem)s]' % locals()

                    indentdecl += '        %(input_param_type)s %(input_param_name)s' % locals()
                    written_cnt += 1

                if written_cnt <  n_passed_params:
                    indentdecl += ',\n'
            
            indentdecl += ')'

        fct_decl = indentdecl + ';\n'
        self.appendSection('command', fct_decl)     
        
        swig_impl = indentdecl + '\n'
        swig_impl += '   {\n'        
        
        # FUNCTION BODY : STACK VARIABLES DECLARATIONS
        for i in argout_params_to_vectorize:
            argout_param_name, argout_param_type = params_name_type[i]
            swig_impl += '      std::vector<%(argout_param_type)s> vec%(argout_param_name)s; \n'% locals()
            swig_impl += '      uint32_t %(argout_param_name)sCount; \n'% locals()

        for i in params_to_shared_ptrize:
            argout_param_name, argout_param_type = params_name_type[i]
            swig_impl += '      std::shared_ptr<%(argout_param_type)s> ptr%(argout_param_name)s(new %(argout_param_type)s); \n' % locals()
            assert(argout_param_type not in self.handleTypes)
            self.shared_ptr_types.add(argout_param_type)

        for i in params_to_return_by_value:
            argout_param_name, argout_param_type = params_name_type[i]
            swig_impl += '      %(argout_param_type)s %(argout_param_name)s; \n' % locals()

        for i in params_to_return_as_handle:
            argout_param_name, argout_param_type = params_name_type[i]
            argout_param_name = p_name_to_handle(argout_param_name)
            swig_impl += '      %(argout_param_type)s %(argout_param_name)s; \n' % locals()

        for i in param_to_return_as_vector_of_handle:
            argout_param_name, argout_param_type = params_name_type[i]
            for j in input_params_to_vectorize:
                create_info_param_name, create_info_param_type  = params_name_type[j]
                swig_impl += '      std::vector<%(argout_param_type)s> vec%(argout_param_name)s( %(create_info_param_name)s.size(), nullptr ); \n' % locals()

        cbs = ''
        cbe = ''
        if return_type_str == 'VkResult':
            cbs = 'V( '
            cbe = ')'

        pf = ''
        if command_name in self.notLoadedBySDK:
            pf = 'pf'

        if is_allocation_cmd:
            if free_command_name in self.notLoadedBySDK:
                free_command_name = 'pf' + free_command_name

        # FUNCTION BODY : Optional 1st call for functions that query elements count
        if len(argout_params_to_vectorize):
            swig_impl += '      %(cbs)s%(pf)s%(command_name)s(\n' % locals()
            for i in range(0,n):
                passed_param_name, passed_param_type = params_name_type[i]
                if i in count_to_vector_param_map:
                    vector_param_index = count_to_vector_param_map[i]
                    vector_param_name = params_name_type[vector_param_index][0]
                    swig_impl += '          &%(vector_param_name)sCount' % locals()
                elif i in argout_params_to_vectorize or i in input_params_to_vectorize:
                    swig_impl += '          nullptr'
                elif i in params_to_shared_ptrize:
                    swig_impl += '          ptr%(passed_param_name)s.get()' % locals()
                elif i in params_to_return_by_value:
                    swig_impl += '          &%(passed_param_name)s' % locals()
                elif i in params_to_return_as_handle:
                    passed_param_name = p_name_to_handle(passed_param_name)
                    swig_impl += '          &%(passed_param_name)s' % locals()
                elif i in params_to_remove:
                    swig_impl += '          nullptr'
                elif i in params_to_const_refitize:
                    swig_impl += '          &%(passed_param_name)s' % locals()
                else:
                    swig_impl += '          %(passed_param_name)s' % locals()
        
                if i <  n-1:
                    swig_impl += ',\n'
            
            swig_impl += '  )%(cbe)s;\n\n' % locals()

            # resize array to get result on next call
            for i in argout_params_to_vectorize:
                argout_param_name, argout_param_type = params_name_type[i]
                swig_impl += '      vec%(argout_param_name)s.resize(%(argout_param_name)sCount); \n\n'% locals()

        # FUNCTION BODY : call to wrapped function
        swig_impl += '      %(cbs)s%(pf)s%(command_name)s(\n' % locals()
        for i in range(0,n):
            passed_param_name, passed_param_type = params_name_type[i]
            if i in count_to_vector_param_map:
                vector_param_index = count_to_vector_param_map[i]
                vector_param_name = params_name_type[vector_param_index][0]
                if vector_param_index in input_params_to_vectorize:
                    if not params_name_type[vector_param_index][1] in self.arrayBaseTypes:
                        swig_impl += '          static_cast<uint32_t>(%(vector_param_name)s.size())' % locals()
                    else:                        
                        swig_impl += '          static_cast<uint32_t>(%(vector_param_name)s_dim1)' % locals()
                elif vector_param_index in param_to_return_as_vector_of_handle:
                    for j in input_params_to_vectorize:
                        create_info_param_name = params_name_type[j][0]
                        swig_impl += '          static_cast<uint32_t>(%(create_info_param_name)s.size())' % locals()
                else:
                    swig_impl += '          &%(vector_param_name)sCount' % locals()
            elif i in argout_params_to_vectorize:
                swig_impl += '          &vec%(passed_param_name)s[0]' % locals()
            elif i in input_params_to_vectorize:
                if passed_param_type != 'void':
                    if not passed_param_type in self.arrayBaseTypes:
                        swig_impl += '          &%(passed_param_name)s[0]' % locals()
                    else:
                        swig_impl += '          %(passed_param_name)s_in_array1' % locals()
                else:
                    swig_impl += '          reinterpret_cast<const void*>(&%(passed_param_name)s[0])' % locals()
            elif i in params_to_shared_ptrize:
                swig_impl += '          ptr%(passed_param_name)s.get()' % locals()
            elif i in params_to_return_by_value:
                swig_impl += '          &%(passed_param_name)s' % locals()
            elif i in params_to_return_as_handle:
                    passed_param_name = p_name_to_handle(passed_param_name)
                    swig_impl += '          &%(passed_param_name)s' % locals()
            elif i in param_to_return_as_vector_of_handle:
                    swig_impl += '          &vec%(passed_param_name)s[0]' % locals()
            elif i in params_to_remove:
                swig_impl += '          nullptr'
            elif i in params_to_const_refitize:
                swig_impl += '          &%(passed_param_name)s' % locals()
            else:
                swig_impl += '          %(passed_param_name)s' % locals()
        
            if i <  n-1:
                swig_impl += ',\n'
            
        swig_impl += '  )%(cbe)s;\n' % locals()

        allocated_ptr_type = findAllocatedPtrType(is_allocation_cmd, params)

        # FUNCTION BODY : Optional return statement
        if n_argout_params == 1:
            if len(argout_params_to_vectorize) == 1:
                argout_param_name = params_name_type[ list(argout_params_to_vectorize)[0] ][0]
                swig_impl += '      return vec%(argout_param_name)s; \n' % locals()
            elif len(params_to_shared_ptrize) == 1:
                argout_param_name = params_name_type[ list(params_to_shared_ptrize)[0] ][0]
                swig_impl += '      return ptr%(argout_param_name)s; \n' % locals()
            elif len(params_to_return_as_handle) == 1 and not is_allocation_cmd:
                argout_param_name = params_name_type[ list(params_to_return_as_handle)[0] ][0]
                argout_param_name = p_name_to_handle(argout_param_name)
                swig_impl += '      return %(argout_param_name)s; \n' % locals()
            elif is_allocation_cmd:
                assert(allocated_ptr_type is not None)
                if len(params_to_return_as_handle) == 1:
                    argout_param_name = params_name_type[ list(params_to_return_as_handle)[0] ][0]
                    argout_param_name = p_name_to_handle(argout_param_name)
                    if free_command_name is not None:
                        swig_impl += '      return std::shared_ptr<%(allocated_ptr_type)s_T>(%(argout_param_name)s, \n' % locals()
                        swig_impl += '              [=](%(allocated_ptr_type)s to_free) {%(free_command_name)s(%(freeparams)s to_free, nullptr);});\n' % locals();
                    else:
                        swig_impl += '      return std::shared_ptr<%(allocated_ptr_type)s_T>(%(argout_param_name)s, \n' % locals()
                        swig_impl += '              [](%(allocated_ptr_type)s) {});\n' % locals();
                else:
                    assert(len(param_to_return_as_vector_of_handle) == 1)
                    argout_param_name = params_name_type[ list(param_to_return_as_vector_of_handle)[0] ][0]
                    swig_impl += '      std::vector< std::shared_ptr<%(allocated_ptr_type)s_T> > retval; \n' % locals()
                    swig_impl += '      retval.reserve(vec%(argout_param_name)s.size()); \n' % locals()
                    swig_impl += '      for (auto allocated_handle : vec%(argout_param_name)s ) \n' % locals()
                    swig_impl += '      {\n' % locals()
                    swig_impl += '          retval.push_back(' % locals()
                    if free_command_name is not None:
                        swig_impl += 'std::shared_ptr<%(allocated_ptr_type)s_T>(allocated_handle, \n' % locals()
                        swig_impl += '              [=](%(allocated_ptr_type)s to_free) {%(free_command_name)s(%(freeparams)s to_free, nullptr);})' % locals();
                    else:
                        swig_impl += 'std::shared_ptr<%(allocated_ptr_type)s_T>(allocated_handle, \n' % locals()
                        swig_impl += '              [](%(allocated_ptr_type)s) {})' % locals();
                    swig_impl += ');\n' % locals()
                    swig_impl += '      }\n' % locals()
                    swig_impl += '      return retval; \n' % locals()
            else:
                argout_param_name = params_name_type[ list(params_to_return_by_value)[0] ][0]
                swig_impl += '      return %(argout_param_name)s; \n' % locals()
                    
        elif n_argout_params > 1:
            assert(False) # Not yet required by the vk.xml

        swig_impl += '   }\n'
        self.swigFeatureImpl.append(swig_impl)

    def genCmd(self, cmdinfo, name):
        OutputGenerator.genCmd(self, cmdinfo, name)

        cmd = cmdinfo.elem
        proto = cmd.find('proto')
        return_type_str = proto[0].text
        command_name = proto[1].text
        params = cmd.findall('param')

        for p in params:
            is_ptr, is_const, ptr_depth = is_param_pointer(p)
            if ptr_depth > 1 or return_type_str == 'PFN_vkVoidFunction':
                self.skippedCommands.append(command_name)
                return

        allocation_callback_ptr_index = None
        params_name_type = [ (get_param_name(p),get_param_type(p)) for p in params]
        params_to_remove = set()
        input_params_to_vectorize = set()
        argout_params_to_vectorize = set()
        params_to_return_by_value = set()
        params_to_const_refitize = set()
        params_to_shared_ptrize = set()
        params_to_return_as_handle = set() # some are return by allocations function as std::shared_ptr with special deleters, the others are returned like pointers
        param_to_return_as_vector_of_handle = set()
        count_to_vector_param_map = {}        
        for i,p in enumerate(params):
            if 'len' in p.keys():
                len_string = p.get('len')                
                if '->' in len_string:
                    # arrays of handle not supported
                    self.skippedCommands.append(command_name)
                    return
                len_params = len_string.split(',')
                for len_param in len_params:
                    nt_pair = (len_param, 'uint32_t')
                    if nt_pair in params_name_type:  
                        count_param_index = params_name_type.index(nt_pair)
                        if is_param_const(p):
                            input_params_to_vectorize.add(i)
                        else:                            
                            argout_params_to_vectorize.add(i)
                        count_to_vector_param_map[ count_param_index ] = i
                        if params_name_type[i][1] not in self.hideFromSWIGTypes:
                            self.std_vector_types.add( params_name_type[i][1] )
                        params_to_remove.add(count_param_index)                           
        
        for i,p in enumerate(params):
            if not i in input_params_to_vectorize and not i in argout_params_to_vectorize and not i in params_to_remove:
                param_name, param_type_name = params_name_type[i]
                is_ptr, is_const, ptr_depth = is_param_pointer(p) 
                if param_type_name == 'VkAllocationCallbacks':
                    allocation_callback_ptr_index = i
                    params_to_remove.add(i)
                elif is_ptr and is_const and param_type_name != 'char':
                    params_to_const_refitize.add(i)
                elif is_ptr and not is_const and param_type_name != 'char':
                    if param_type_name == 'void':
                        params_to_remove.add(i)
                    elif param_type_name in self.copyableBaseTypes:
                        params_to_return_by_value.add(i)
                    elif param_type_name in self.handleTypes:
                        params_to_return_as_handle.add(i)
                    else:
                        params_to_shared_ptrize.add(i)
        
        is_alloc = allocation_callback_ptr_index is not None

        # we assume that the only allocation function that have an argout vector params, only have one such param and that it's a vector of handles       
        if is_alloc and len(argout_params_to_vectorize) > 0:
            assert(len(argout_params_to_vectorize) == 1)  # only one arg out vector
            assert(len(input_params_to_vectorize) == 1) # mandatory input vector (create infos)
            for i in argout_params_to_vectorize:
                param_name, param_type_name = params_name_type[i]
                assert(param_type_name in self.handleTypes)
                param_to_return_as_vector_of_handle.add(i)   
                self.vectorOfHandleTypes.add(param_type_name)         
            argout_params_to_vectorize = set()

        self.genCommand(return_type_str, 
                        command_name, 
                        is_alloc, 
                        params, 
                        params_name_type, 
                        params_to_remove, 
                        input_params_to_vectorize, 
                        argout_params_to_vectorize, 
                        params_to_const_refitize, 
                        params_to_shared_ptrize, 
                        params_to_return_as_handle,
                        param_to_return_as_vector_of_handle, 
                        params_to_return_by_value,                         
                        count_to_vector_param_map  )

        decls = self.makeCDecls(cmdinfo.elem)
        self.appendSection('commandPointer', decls[1])
        if command_name in self.notLoadedBySDK:
            self.fctPtrDecl.append("PFN_%(command_name)s pf%(command_name)s;" % locals())

khronosPrefixStrings = [
    '/*',
    '** Copyright (c) 2015-2016 The Khronos Group Inc.',
    '**',
    '** Permission is hereby granted, free of charge, to any person obtaining a',
    '** copy of this software and/or associated documentation files (the',
    '** "Materials"), to deal in the Materials without restriction, including',
    '** without limitation the rights to use, copy, modify, merge, publish,',
    '** distribute, sublicense, and/or sell copies of the Materials, and to',
    '** permit persons to whom the Materials are furnished to do so, subject to',
    '** the following conditions:',
    '**',
    '** The above copyright notice and this permission notice shall be included',
    '** in all copies or substantial portions of the Materials.',
    '**',
    '** THE MATERIALS ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,',
    '** EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF',
    '** MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.',
    '** IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY',
    '** CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,',
    '** TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE',
    '** MATERIALS OR THE USE OR OTHER DEALINGS IN THE MATERIALS.',
    '*/',
    ''
]

vlam3dPrefixString = """
/*
* 
* THIS FILE IS GENERATED BY genswigi.py 
*
* pyvulkan SWIG interface description file
*
* Copyright (C) 2016 by VLAM3D Software inc. https://www.vlam3d.com
*
* This code is licensed under the MIT license (MIT) (http://opensource.org/licenses/MIT)
*/
"""

regFilename = 'vk.xml'
diagFilename = 'diag.txt'
   

if __name__ == '__main__':
    reg = Registry()
    tree = etree.parse(regFilename)
    reg.loadElementTree(tree)

    allVersions = allExtensions = '.*'
    noVersions = noExtensions = None

    prefix_strs = [vlam3dPrefixString]
    prefix_strs.extend(khronosPrefixStrings)

    genOpts = CGeneratorOptions(
        filename          = '../../../pyvulkan/vulkan.ixx',
        apiname           = 'vulkan',
        profile           = None,
        versions          = allVersions,
        emitversions      = allVersions,
        defaultExtensions = 'vulkan',
        addExtensions     = None,
        removeExtensions  = None,
        prefixText        = prefix_strs,
        genFuncPointers   = True,
        protectFile       = False,
        protectFeature    = False,
        protectProto      = None,
        protectProtoStr   = None,
        apicall           = 'VKAPI_ATTR ',
        apientry          = 'VKAPI_CALL ',
        apientryp         = 'VKAPI_PTR *',
        alignFuncParam    = 48)

    errWarn = sys.stderr
    with open(diagFilename, 'w') as diag:
        gen = CSWIGOutputGenerator(errFile=errWarn, warnFile=errWarn, diagFile=diag)
        reg.setGenerator(gen)
        reg.apiGen(genOpts)

