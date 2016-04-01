/* -*- C -*-  (not really, but good for syntax highlighting) */
/*
* pyglslang SWIG interface description file
*
* Copyright (C) 2016 by VLAM3D Software inc. https://www.vlam3d.com
*
* This code is licensed under the MIT license (MIT) (http://opensource.org/licenses/MIT)
*/

%define DOCSTRING
"PYGLSLANG Automatically generated documentation

The source of this text is in pyglslang.i the main SWIG_ interface file.
Use %feature(\"autodoc\") in the interface file to improve the documentation.
Please read SWIG_DOC_ 

.. _SWIG: http://www.swig.org/
.. _SWIG_DOC: http://www.swig.org/Doc1.3/Python.html#Python_nn65
"
%enddef 
 
%module(docstring=DOCSTRING) pyglslang
 
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
#include <string>
#include <ShaderLang.h>
#include <GlslangToSpv.h>
%}

%init
%{
    import_array();
%}

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
        SWIG_exception(SWIG_IndexError, const_cast<char*>(e.what()));
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


%include <ResourceLimits.h>

typedef enum {
    EShLangVertex,
    EShLangTessControl,
    EShLangTessEvaluation,
    EShLangGeometry,
    EShLangFragment,
    EShLangCompute,
    EShLangCount,
} EShLanguage;

typedef enum {
    EShLangVertexMask = (1 << EShLangVertex),
    EShLangTessControlMask = (1 << EShLangTessControl),
    EShLangTessEvaluationMask = (1 << EShLangTessEvaluation),
    EShLangGeometryMask = (1 << EShLangGeometry),
    EShLangFragmentMask = (1 << EShLangFragment),
    EShLangComputeMask = (1 << EShLangCompute),
} EShLanguageMask;

typedef enum {
    EShExVertexFragment,
    EShExFragment
} EShExecutable;

typedef enum {
    EShOptNoGeneration,
    EShOptNone,
    EShOptSimple,       // Optimizations that can be done quickly
    EShOptFull,         // Optimizations that will take more time
} EShOptimizationLevel;

enum EShMessages {
    EShMsgDefault = 0,         // default is to give all required errors and extra warnings
    EShMsgRelaxedErrors = (1 << 0),  // be liberal in accepting input
    EShMsgSuppressWarnings = (1 << 1),  // suppress all warnings, except those required by the specification
    EShMsgAST = (1 << 2),  // print the AST intermediate representation
    EShMsgSpvRules = (1 << 3),  // issue messages for SPIR-V generation
    EShMsgVulkanRules = (1 << 4),  // issue messages for Vulkan-requirements of GLSL for SPIR-V
    EShMsgOnlyPreprocessor = (1 << 5),  // only print out errors produced by the preprocessor
};

namespace glslang 
{
    const char* StageName(EShLanguage);
    const char* GetEsslVersionString();
    const char* GetGlslVersionString();
    int GetKhronosToolId();    
    bool InitializeProcess();
    void FinalizeProcess();

    class TShader
    {
    public:
        explicit TShader(EShLanguage);
        virtual ~TShader();

        const char* getInfoLog();
        const char* getInfoDebugLog();

        EShLanguage getStage() const;

        %extend
        {
            bool parse( const std::string &code,
                        const TBuiltInResource* res,
                        int defaultVersion,
                        EProfile defaultProfile,
                        bool forceDefaultVersionAndProfile,
                        bool forwardCompatible,
                        EShMessages messages)
            {
                const char* ptr_array[1] = { code.c_str() };
                $self->setStrings(&ptr_array[0], 1);
                return $self->parse(res, defaultVersion, defaultProfile, forceDefaultVersionAndProfile, forwardCompatible, messages);
            }

            // Equivalent to parse() without a default profile and without forcing defaults.
            // Provided for backwards compatibility.
            bool parse(const std::string &code, const TBuiltInResource *res, int defaultVersion, bool forwardCompatible, EShMessages messages)
            {
                const char* ptr_array[1] = { code.c_str() };
                $self->setStrings(&ptr_array[0], 1);
                return $self->parse(res, defaultVersion, forwardCompatible, messages);
            }
        }
    };

    class TProgram
    {
    public:
        TProgram();
        virtual ~TProgram();
        void addShader(TShader* shader);

        // Link Validation interface
        bool link(EShMessages);
        const char* getInfoLog();
        const char* getInfoDebugLog();

        // Reflection Interface
        bool buildReflection();                          
        int getNumLiveUniformVariables();                
        int getNumLiveUniformBlocks();                   
        const char* getUniformName(int index);           
        const char* getUniformBlockName(int blockIndex); 
        int getUniformBlockSize(int blockIndex);         
        int getUniformIndex(const char* name);           
        int getUniformBlockIndex(int index);             
        int getUniformType(int index);                   
        int getUniformBufferOffset(int index);           
        int getUniformArraySize(int index);              
        void dumpReflection();

        %extend
        {
            std::vector<unsigned int> getSpv(EShLanguage stage)
            {
                std::vector<unsigned int> spirv;
                glslang::GlslangToSpv(*$self->getIntermediate(stage), spirv);
                return spirv;
            }
        }
    };
}

%template (UnsignedIntVector) std::vector<unsigned int>;