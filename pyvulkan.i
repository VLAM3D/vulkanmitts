/* -*- C -*-  (not really, but good for syntax highlighting) */
/*
* pyvulkan SWIG interface description file
*
* Copyright (C) 2016 by VLAM3D Software inc. https://www.vlam3d.com
*
* This code is licensed under the MIT license (MIT) (http://opensource.org/licenses/MIT)
*/  

%define DOCSTRING
"PYVULKAN Automatically generated documentation

The source of this text is in pyvulkan.i the main SWIG_ interface file.
Use %feature(\"autodoc\") in the interface file to improve the documentation.
Please read SWIG_DOC_ 

.. _SWIG: http://www.swig.org/
.. _SWIG_DOC: http://www.swig.org/Doc1.3/Python.html#Python_nn65
"
%enddef 
 
%module(docstring=DOCSTRING) pyvulkan

%feature("autodoc", "3");

%{ 
#define SWIG_FILE_WITH_INIT  
%}

%include <numpy.i>
%{
#undef _DEBUG
#define _DEBUG 1

#include <exception>
#include <memory>
#include <vector>
#include <numpy/arrayobject.h>
#include <vulkan/vk_platform.h>
#include <vulkan/vulkan.h> 

%}
%init 
%{ 
    import_array();
%}

%define %ref_counted_handle(HANDLETYPE...)
    %typemap(in) HANDLETYPE
    (void *argp, int res = 0)
    {
        res = SWIG_ConvertPtr($input, &argp, $descriptor(HANDLETYPE##_T*), 0 | 0);
        if (!SWIG_IsOK(res)) 
        {
            int newmem = 0;
            res = SWIG_ConvertPtrAndOwn($input, &argp, $descriptor(std::shared_ptr<HANDLETYPE##_T> *), %convertptr_flags, &newmem);
            if (!SWIG_IsOK(res)) {
                %argument_fail(res, "$type", $symname, $argnum);
            }
            if (!argp) {
                %argument_nullref("$type", $symname, $argnum);
            }
            else {
                $1 = (%reinterpret_cast(argp, std::shared_ptr<HANDLETYPE##_T> *)->get());
                if (newmem & SWIG_CAST_NEW_MEMORY) delete %reinterpret_cast(argp, std::shared_ptr<HANDLETYPE##_T> *);
            }
        }
        else
        {
            $1 = %reinterpret_cast(argp, HANDLETYPE);
        }
    }

    %typemap(typecheck) HANDLETYPE
    {
        int res = SWIG_ConvertPtr($input, 0, $descriptor(HANDLETYPE##_T*), 0);
        if (!SWIG_IsOK(res))
        {
            res = SWIG_ConvertPtr($input, 0, $descriptor(std::shared_ptr<HANDLETYPE##_T> *), 0);
        }
        $1 = SWIG_CheckState(res);
    }

    // need to inform swig that HANDLETYPE is the same as HANDLETYPE_T*     
    %apply HANDLETYPE { HANDLETYPE##_T* };

    %template (HANDLETYPE##RefCounted)std::shared_ptr<HANDLETYPE##_T>;
%enddef

%define %carray_of_struct(TYPE...)
    %typemap(out) TYPE[ANY]
    {
        $result = PyList_New($1_dim0);
        for (int i = 0; i < $1_dim0; i++) {        
            auto p_obj = SWIG_NewPointerObj(SWIG_as_voidptr(&$1[i]), $descriptor(TYPE*), 0 | 0);
            PyList_SetItem($result, i, p_obj);
        }
    }
%enddef

%define in_array_typemap_macro(TYPE, CONVERT_API_FCT)
    %typemap(in) TYPE[ANY] (TYPE temp[$1_dim0]) {
        int i;
        if (!PySequence_Check($input)) {
            PyErr_SetString(PyExc_ValueError,"Expected a sequence");
            return NULL;
        }
        if (PySequence_Length($input) != $1_dim0) {
            PyErr_SetString(PyExc_ValueError,"Size mismatch. Expected $1_dim0 elements");
            return NULL;
        }
        for (i = 0; i < $1_dim0; i++) {
            PyObject *o = PySequence_GetItem($input,i);
            if (PyNumber_Check(o)) {
                temp[i] = static_cast<TYPE>(CONVERT_API_FCT(o));
            } else {
                PyErr_SetString(PyExc_ValueError,"Sequence elements must be numbers");      
                return NULL;
            }
        }
        $1 = temp;
    }

    %typemap(memberin) TYPE[ANY] {
        for (int i = 0; i < $1_dim0; i++) {
            $1[i] = $input[i];
        }
    }
%enddef

%define out_array_typemap_macro(TYPE, CPYTHON_API_TYPE, CONVERT_API_FCT)
    %typemap(out) TYPE[ANY]
    {
        $result = PyList_New($1_dim0);
        for (int i = 0; i < $1_dim0; i++) {        
            auto p_obj = CONVERT_API_FCT(static_cast<CPYTHON_API_TYPE>($1[i]));
            PyList_SetItem($result, i, p_obj);
        }
    }
%enddef

%define %carray_of_float(TYPE...)
    in_array_typemap_macro(TYPE, PyFloat_AsDouble)
    out_array_typemap_macro(TYPE, double, PyFloat_FromDouble)
%enddef

%define %carray_of_size_t(TYPE...)
    in_array_typemap_macro(TYPE, PyInt_AsLong)
    out_array_typemap_macro(TYPE, size_t, PyInt_FromSize_t)
%enddef

%define %carray_of_long(TYPE...)
    in_array_typemap_macro(TYPE, PyInt_AsLong)
    out_array_typemap_macro(TYPE, long, PyInt_FromLong)
%enddef

%define %raii_struct(TYPE...)
    %typemap(in) const TYPE &
    (void *argp, int res = 0)
    {
        int newmem = 0;
        res = SWIG_ConvertPtrAndOwn($input, &argp, $descriptor(std::shared_ptr<TYPE##RAII> *), %convertptr_flags, &newmem);
        if (!SWIG_IsOK(res)) {
            %argument_fail(res, "$type", $symname, $argnum);
        }
        if (!argp) {
            %argument_nullref("$type", $symname, $argnum);
        }
        else {
            std::shared_ptr<TYPE##RAII> &ptr = *%reinterpret_cast(argp, std::shared_ptr<TYPE##RAII> *);
            $1 = &(ptr->nonRaiiObj);
        }
    }

    %typemap(in) TYPE 
    (void *argp, int res = 0)
    {
        int newmem = 0;
        res = SWIG_ConvertPtrAndOwn($input, &argp, $descriptor(std::shared_ptr<TYPE##RAII> *), %convertptr_flags, &newmem);
        if (!SWIG_IsOK(res)) {
            %argument_fail(res, "$type", $symname, $argnum);
        }
        if (!argp) {
            %argument_nullref("$type", $symname, $argnum);
        }
        else {
            std::shared_ptr<TYPE##RAII> &ptr = *%reinterpret_cast(argp, std::shared_ptr<TYPE##RAII> *);
            $1 = ptr->nonRaiiObj;
        }
    }

    %typemap(in) const std::vector<TYPE> &
    (void *argp, int res = 0, std::vector<TYPE> temp_vec)
    {
        int newmem = 0;
        res = SWIG_ConvertPtrAndOwn($input, &argp, $descriptor(std::vector< std::shared_ptr<TYPE##RAII> > *), %convertptr_flags, &newmem);
        if (!SWIG_IsOK(res)) {
            %argument_fail(res, "$type", $symname, $argnum);
        }
        if (!argp) {
            %argument_nullref("$type", $symname, $argnum);
        }
        else {
            std::vector< std::shared_ptr<TYPE##RAII> > &vec = *%reinterpret_cast(argp, std::vector< std::shared_ptr<TYPE##RAII> > *);
            temp_vec.resize(vec.size());
            std::transform(vec.begin(), vec.end(), temp_vec.begin(), [](const std::shared_ptr<TYPE##RAII> &ptr)->TYPE {return ptr->nonRaiiObj; });
            $1 = &temp_vec;
        }
    }      

    %typemap(in) const std::shared_ptr<TYPE##RAII> &
    (void *argp, int res = 0, std::shared_ptr<TYPE##RAII> null_shared_ptr)
    {
        int newmem = 0;
        res = SWIG_ConvertPtrAndOwn($input, &argp, $descriptor(std::shared_ptr<TYPE##RAII> *), %convertptr_flags, &newmem);
        if (!SWIG_IsOK(res)) {
            %argument_fail(res, "$type", $symname, $argnum);
        }
        if (!argp) {
            $1 = &null_shared_ptr;
        }
        else {
            $1 = %reinterpret_cast(argp, std::shared_ptr<TYPE##RAII> *);
        }
    }
%enddef

%include <std_shared_ptr.i>; 

// !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
// shared_ptr section : all wrapped std::shared_ptr<T>
// must be declared here first

%shared_ptr(std::vector<VkCommandBuffer>)
%shared_ptr(std::vector<VkDescriptorSet>)
%include "shared_ptrs.ixx"
%apply(int DIM1, unsigned int* IN_ARRAY1) { (size_t codeSize, const uint32_t* pCode) };

//
// !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

%include stl.i
%include "exception.i"
%include "std_pair.i"
%include "std_vector.i"
%include "std_map.i"
%include "std_string.i"
%include "std_wstring.i"   
%include "std_ios.i"
%include "typemaps.i"
%include "cpointer.i" 
 
%exception   
{ 
    try  
    {
        $action
    }
    catch (std::out_of_range& e) 
    {
        SWIG_exception(SWIG_IndexError,const_cast<char*>(e.what()));
    }
    catch (const std::exception& e) 
    {
        SWIG_exception(SWIG_RuntimeError, e.what());
    }
} 

// from William S. Fulton answer in http://swig.10945.n7.nabble.com/Properly-wrapping-quot-static-const-char-quot-td11479.html
// we disable the const char * warning but we put a typemap to trigger a run-time error when trying to set it
#pragma SWIG nowarn=-451
%typemap(varin) const char * 
{
   SWIG_Error(SWIG_AttributeError,"Variable $symname is read-only.");
   SWIG_fail;
}  
   
%{     
    void ThrowOnVkError(VkResult res, char* statement, char* file, long line);

    #define V(x) do{   \
        auto res = x;\
        ThrowOnVkError(res, #x, __FILE__, __LINE__);\
    }while(0)
%} 
 

%template (StringVector) std::vector<std::string>;
 
#define VKAPI_PTR
typedef unsigned int uint32_t;
typedef int int32_t;
typedef unsigned long long uint64_t;

struct HWND__
{
private:
    HWND__();
};

struct HINSTANCE__
{
private:
    HINSTANCE__();
};

typedef HWND__* HWND;
typedef HINSTANCE__* HINSTANCE;

%typemap(in) HWND
{
#if PY_MAJOR_VERSION > 2
	auto long_obj = PyNumber_Long($input);
#else
	auto long_obj = PyNumber_Int($input);
#endif
	if (!long_obj)
	{
		$1 = reinterpret_cast<HWND>(PyLong_AsVoidPtr($input));				
	}
	else
	{
		$1 = reinterpret_cast<HWND>(PyLong_AsVoidPtr(long_obj));
	}

	if (!IsWindow($1))
	{
		%argument_fail(-1, "HWND is not a valid Win32 Windows Handle", $symname, $argnum);
	}
}

%typemap(in) HINSTANCE
(void *argp = 0, int res = 0)
{
    res = SWIG_ConvertPtr($input, &argp, $descriptor, $disown | %convertptr_flags);
    if (!argp || !SWIG_IsOK(res))
    {
        auto long_obj = PyNumber_Long($input);
        if (!long_obj)
        {
            %argument_fail(-1, "HINSTANCE/HMODULE can't extract the handle from the argument", $symname, $argnum);
        }

        $1 = reinterpret_cast<HINSTANCE>(PyLong_AsVoidPtr(long_obj));
        TCHAR filename[255];
        if (!GetModuleFileName($1, filename, 255))
        {
            %argument_fail(-1, "HINSTANCE/HMODULE is not a valid Win32 module handle", $symname, $argnum);
        }
    }
    else
    {
        $1 = %reinterpret_cast(argp, $ltype);
    }
}

%inline 
%{
    HINSTANCE GetThisEXEModuleHandle()
    {
        return GetModuleHandle(nullptr);
    }
%}

%include "vulkan.ixx"

uint32_t makeVersion(uint32_t major, uint32_t minor, uint32_t patch);

%{
    void ThrowOnVkError(VkResult res, char* statement, char* file, long line)
    {
        if (res != VK_SUCCESS)
        {
            std::stringstream err_message;
            auto err_str = vkGetErrorString(res);
            if (err_str)
            {
                err_message << err_str << "; Error returned by command " << statement << " in source file " << file << " line " << line ;
            }
            else
            {
                err_message << "Unknown error VkResult code " << res << " ; Error returned by command " << statement << " in source file " << file << " line " << line;
            }
            throw std::runtime_error(err_message.str());
        }
    }

    uint32_t makeVersion(uint32_t major, uint32_t minor, uint32_t patch)
    {
        return (((major) << 22) | ((minor) << 12) | (patch));
    } 
%}

std::shared_ptr< std::vector<VkDescriptorSet> > allocateDescriptorSets(VkDevice device, const VkDescriptorSetAllocateInfo& allocateInfo, bool freeDescriptorSetAllowed);

%{
    struct VkDescriptorSet_T;
    typedef VkDescriptorSet_T* VkDescriptorSet;

    namespace swig
    {
        template <>  struct traits< VkDescriptorSet_T >
        {
            typedef pointer_category category;
            static const char* type_name() { return"VkDescriptorSet_T"; }
        };
    }

    std::shared_ptr< std::vector<VkDescriptorSet> > allocateDescriptorSets(VkDevice device, const VkDescriptorSetAllocateInfo& allocateInfo, bool freeDescriptorSetAllowed)
    {
		// freeDescriptorSetAllowed must be true only when VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT is set
		// in this case we call must call vkFreeDescriptorSets 
		if (freeDescriptorSetAllowed)
		{
			VkDescriptorPool descriptorPool = allocateInfo.descriptorPool;
			std::shared_ptr< std::vector<VkDescriptorSet> > descriptor_sets(new std::vector<VkDescriptorSet>(allocateInfo.descriptorSetCount, nullptr), 
				[device, descriptorPool](std::vector<VkDescriptorSet> *p_to_delete)
				{
					assert(p_to_delete != nullptr);
					auto retval = vkFreeDescriptorSets(device, descriptorPool, static_cast<uint32_t>(p_to_delete->size()), &p_to_delete->front());
					assert(retval == VK_SUCCESS);
					if (retval != VK_SUCCESS)
					{
						// can't throw an error in a dtor so we just report the error in release, in debug we assert
						std::cerr << vkGetErrorString(retval);
					}
					delete p_to_delete;
				});
			V(vkAllocateDescriptorSets(device, &allocateInfo, &descriptor_sets->front() ));
			return descriptor_sets;
		}

		// if VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT is NOT SET then the descriptor set is owned byt the descriptor pool 
		// it will be freed by vkResetDescriptorPool, so we don't need a custom deleter
		auto descriptor_sets = std::make_shared< std::vector<VkDescriptorSet> >(allocateInfo.descriptorSetCount, nullptr);
		V(vkAllocateDescriptorSets(device, &allocateInfo, &descriptor_sets->front() ));
		return descriptor_sets;
    } 
%}

%template (VkDescriptorSetVector)std::vector<VkDescriptorSet>;

std::shared_ptr< std::vector<VkCommandBuffer> > allocateCommandBuffers(VkDevice device, const VkCommandBufferAllocateInfo& allocateInfo);
%{
    struct VkCommandBuffer_T;
    typedef VkCommandBuffer_T* VkCommandBuffer;

    namespace swig
    {
        template <>  struct traits< VkCommandBuffer_T >
        {
            typedef pointer_category category;
            static const char* type_name() { return"VkCommandBuffer_T"; }
        };
    }

    std::shared_ptr< std::vector<VkCommandBuffer> > allocateCommandBuffers(VkDevice device, const VkCommandBufferAllocateInfo& allocateInfo)
    {
        VkCommandPool commandPool = allocateInfo.commandPool;
        std::shared_ptr< std::vector<VkCommandBuffer> > command_buffers(new std::vector<VkCommandBuffer>(allocateInfo.commandBufferCount, nullptr),
            [device, commandPool](std::vector<VkCommandBuffer> *p_to_delete)
        {
            assert(p_to_delete != nullptr);
            vkFreeCommandBuffers(device, commandPool, static_cast<uint32_t>(p_to_delete->size()), &p_to_delete->front());
            delete p_to_delete;
        });
        V(vkAllocateCommandBuffers(device, &allocateInfo, &command_buffers->front()));
        return command_buffers;
    }
%}

%template (VkCommandBufferVector)std::vector<VkCommandBuffer>;

// --  Typemap suite only for vkMapMemory --
// Note that the following typemaps are only applicable to vkMapMemory and won't produce working code on any other interface
// That's why they are defined at the end to reduce the chance that they will match some other signature
%fragment("pyvulkan_mapmemory", "header")
{
    %#define PYVULKAN_MAPPEDMEMORY_CAPSULE_NAME "pyvulkan_mapped_memory_capsule"

    struct VkMapMemoryCapsule
    {
        VkDevice m_device;
        VkDeviceMemory m_memory;
    };

    void free_vkmapmemory_cap(PyObject * cap)
    {
        auto *p_capsule = reinterpret_cast<VkMapMemoryCapsule*>(PyCapsule_GetPointer(cap, PYVULKAN_MAPPEDMEMORY_CAPSULE_NAME));
        if (p_capsule != nullptr)
        {
            vkUnmapMemory(p_capsule->m_device, p_capsule->m_memory);
            delete p_capsule;
        }
    }
}

// Type map for contiguous buffer interface - e.g. uniform buffer
%typemap(in, numinputs = 0)
(void** ppData_contiguous, VkDeviceSize* buffer_size)
(void*  data_temp = nullptr, VkDeviceSize  dim_temp)
{
    $1 = &data_temp;
    $2 = &dim_temp;
}

%typemap(argout, fragment = "NumPy_Backward_Compatibility,NumPy_Utilities,pyvulkan_mapmemory")
(void** ppData_contiguous, VkDeviceSize* buffer_size)
{
    npy_intp dims[1] = { static_cast<npy_intp>(*$2) };
    PyObject* obj = PyArray_SimpleNewFromData(1, dims, NPY_UBYTE, (void*)(*$1));
    PyArrayObject* array = (PyArrayObject*)obj;

    if (!array) 
        SWIG_fail;

    VkMapMemoryCapsule *p_cap = new VkMapMemoryCapsule;
    p_cap->m_device = arg1;
    p_cap->m_memory = arg2;

    PyObject* cap = PyCapsule_New((void*)p_cap, PYVULKAN_MAPPEDMEMORY_CAPSULE_NAME, free_vkmapmemory_cap);
    PyArray_SetBaseObject(array, cap);

    $result = SWIG_Python_AppendOutput($result, obj);
}

%inline %{
    void mapMemory(
        VkDevice                                    device,
        VkDeviceMemory                              memory,
        VkDeviceSize                                offset,
        VkDeviceSize                                size,
        VkMemoryMapFlags                            flags,
        void**                                      ppData_contiguous,
        VkDeviceSize*                               buffer_size)
    {
        if (size == VK_WHOLE_SIZE)
        {
            throw std::runtime_error("VK_WHOLE_SIZE not supported; Please compute the size");
        }
        
        V(vkMapMemory(device, memory, offset, size, flags, ppData_contiguous));
        *buffer_size = size;
    }
%}



// Type map for strided image buffer - e.g. texture image staging buffer
%typemap(in, numinputs = 0)
(void** ppData_strided_2D)
(void*  data_temp = nullptr)
{
    $1 = &data_temp;
}

// the arg# correspond to the argument order in the mapMemory2D function below (1-based) e.g. arg1 is device, ... arg9 is ppData_strided_2D
// this only works because this is the only function that matches this typemap
%typemap(argout, fragment = "NumPy_Backward_Compatibility,NumPy_Utilities,pyvulkan_mapmemory")
(void** ppData_strided_2D)
{
    auto pyarray_descr = PyArray_DescrFromType(arg5);
    npy_intp dims[2] = { arg7, arg6 };
    npy_intp strides[2] = { arg8, pyarray_descr->elsize };
    PyObject* obj = PyArray_NewFromDescr(&PyArray_Type, pyarray_descr, 2, dims, strides, (void*)(*arg9), NPY_ARRAY_BEHAVED, NULL);
    PyArrayObject* array = (PyArrayObject*)obj;

    if (!array)
        SWIG_fail;

    VkMapMemoryCapsule *p_cap = new VkMapMemoryCapsule;
    p_cap->m_device = arg1;
    p_cap->m_memory = arg2;

    PyObject* cap = PyCapsule_New((void*)p_cap, PYVULKAN_MAPPEDMEMORY_CAPSULE_NAME, free_vkmapmemory_cap);
    PyArray_SetBaseObject(array, cap);

    $result = SWIG_Python_AppendOutput($result, obj);
} 

%inline %{
    void mapMemory2D(
        VkDevice                                    device,
        VkDeviceMemory                              memory,
        VkDeviceSize                                offset,
        VkMemoryMapFlags                            flags,
        int                                         numpy_typenum,
        unsigned int                                width,
        unsigned int                                height,
        unsigned int                                row_pitch_bytes,        
        void**                                      ppData_strided_2D)
    {
        V(vkMapMemory(device, memory, offset, static_cast<VkDeviceSize>(height)*static_cast<VkDeviceSize>(row_pitch_bytes), flags, ppData_strided_2D));
    }
%}

%include "message_callback.ixx"

%inline 
%{
	std::shared_ptr<VkDebugReportCallbackEXT_T> install_stdout_error_reporting(VkInstance instance, VkDebugReportFlagsEXT flags)
	{
		VkDebugReportCallbackCreateInfoEXT dbgCreateInfo = {};
		dbgCreateInfo.sType = VK_STRUCTURE_TYPE_DEBUG_REPORT_CREATE_INFO_EXT;
		dbgCreateInfo.pfnCallback = (PFN_vkDebugReportCallbackEXT)message_callback;
		dbgCreateInfo.flags = flags;

		return createDebugReportCallbackEXT(instance, dbgCreateInfo);
	}
%}

