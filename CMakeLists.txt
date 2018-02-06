cmake_minimum_required (VERSION 3.1)
project (pyvulkan)
set (CMAKE_CXX_STANDARD 11)
#set (CMAKE_VERBOSE_MAKEFILE 1)

set (pyvulkan_VERSION_MAJOR 0)
set (pyvulkan_VERSION_MINOR 1)

find_package(Threads REQUIRED)
find_package(SWIG REQUIRED)
include(${SWIG_USE_FILE})

find_package(PythonInterp REQUIRED)
message (STATUS "Using this Python interpreter: " ${PYTHON_EXECUTABLE})

find_package(PythonLibs REQUIRED)
include_directories(${PYTHON_INCLUDE_PATH})
include_directories(${CMAKE_CURRENT_SOURCE_DIR})

if (WIN32)
	STRING(REGEX REPLACE "\\\\" "/" VULKAN_SDK ${VULKAN_SDK}) 
    set(VULKAN_SDK_SOURCE ${VULKAN_SDK})
    include_directories(${VULKAN_SDK}/Include)    
else()
    if (NOT DEFINED VULKAN_SDK)    
        # setup-env.sh in Lunar Vulkan SDK for Linux sets VULKAN_SDK to the x86_64 folder
        # we must back track
        set(VULKAN_SDK $ENV{VULKAN_SDK}/../)
    endif()
    set(VULKAN_SDK_SOURCE ${VULKAN_SDK}/source)
    include_directories(${VULKAN_SDK}/x86_64/include)
endif()

include_directories(${VULKAN_SDK_SOURCE}/glslang/glslang/Include)
include_directories(${VULKAN_SDK_SOURCE}/glslang/glslang/Public)
include_directories(${VULKAN_SDK_SOURCE}/glslang/SPIRV)
include_directories(${VULKAN_SDK_SOURCE}/spirv-tools/include/spirv-tools)

message (STATUS "Using this Python Lib: " ${PYTHON_LIBRARIES})

set(CMAKE_SWIG_FLAGS "")

# external python call to get its site_package path
# the python command must execute the desired python interpreter 
# mus replace the backslash by forward slash otherwise there's an error in swig_link_libraries
execute_process ( COMMAND python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib().replace('\\\\', '/'))" OUTPUT_VARIABLE PYTHON_SITE_PACKAGES OUTPUT_STRIP_TRAILING_WHITESPACE)

set(NUMPY_INCLUDE_DIR ${PYTHON_SITE_PACKAGES}/numpy/core/include)
find_library(NUMPY_LIB NAMES npymath HINTS ${PYTHON_SITE_PACKAGES}/numpy/core/lib)
message (STATUS "Numpy include path: " ${NUMPY_INCLUDE_DIR} )
message (STATUS "Numpy lib: " ${NUMPY_LIB} )

find_library(VULKAN_LIB NAMES vulkan vulkan-1 HINTS ${VULKAN_SDK}/Bin ${VULKAN_SDK}/x86_64/lib ${VULKAN_SDK}/Lib)
message (STATUS "Vulkan lib: " ${VULKAN_LIB} )

####
# GLSLANG DEPENDENCIES 

if (WIN32)
    set(GLSLANG_DIR ${VULKAN_SDK}/glslang/build)
    set(SPIRVTOOLS_DIR ${VULKAN_SDK}/spirv-tools/build)
    set (GLSLANG_SEARCH_PATH "${GLSLANG_DIR}/glslang/Release"
                             "${GLSLANG_DIR}/glslang/OSDependent/Windows/Release"
                             "${GLSLANG_DIR}/OGLCompilersDLL/Release"
                             "${GLSLANG_DIR}/SPIRV/Release"
							 "${GLSLANG_DIR}/HLSL/Release" )
    set (SPIRV_TOOLS_SEARCH_PATH "${SPIRVTOOLS_DIR}/source/Release")
    set (SPIRV_TOOLS_OPT_SEARCH_PATH "${SPIRVTOOLS_DIR}/source/opt/Release")
else()
    set (GLSLANG_SEARCH_PATH "${VULKAN_SDK}/install/lib" "${VULKAN_SDK}/x86_64/lib/glslang" )
    set (SPIRV_TOOLS_SEARCH_PATH "${VULKAN_SDK}" "${VULKAN_SDK}/x86_64/lib/spirv-tools" )
    set (SPIRV_TOOLS_OPT_SEARCH_PATH ${SPIRV_TOOLS_SEARCH_PATH} )
endif()

find_library(GLSLANG_LIB NAMES glslang HINTS ${GLSLANG_SEARCH_PATH} )
find_library(OGLCompiler_LIB NAMES OGLCompiler HINTS ${GLSLANG_SEARCH_PATH} )
find_library(OSDependent_LIB NAMES OSDependent HINTS ${GLSLANG_SEARCH_PATH} )
find_library(SPIRV_LIB NAMES SPIRV HINTS ${GLSLANG_SEARCH_PATH} )
find_library(SPVREMAPPER_LIB NAMES SPVRemapper HINTS ${GLSLANG_SEARCH_PATH} )
find_library(HLSL_LIB NAMES HLSL HINTS ${GLSLANG_SEARCH_PATH} )
find_library(SPIRV_TOOLS_LIB NAMES SPIRV-Tools HINTS ${SPIRV_TOOLS_SEARCH_PATH} )
find_library(SPIRV_TOOLS_OPT_LIB NAMES SPIRV-Tools-opt HINTS ${SPIRV_TOOLS_OPT_SEARCH_PATH} )

# On Windows, we must pair Debug and Release appropriately
if (WIN32)
    set (GLSLANG_DEBUG_SEARCH_PATH "${GLSLANG_DIR}/glslang/Debug"
                                   "${GLSLANG_DIR}/glslang/OSDependent/Windows/Debug"
                                   "${GLSLANG_DIR}/OGLCompilersDLL/Debug"
                                   "${GLSLANG_DIR}/SPIRV/Debug"
								   "${GLSLANG_DIR}/HLSL/Debug")
    set (SPIRV_TOOLS_DEBUG_SEARCH_PATH "${SPIRVTOOLS_DIR}/source/Debug")

    add_library(glslang     STATIC IMPORTED)
    add_library(OGLCompiler STATIC IMPORTED)
    add_library(OSDependent STATIC IMPORTED)
    add_library(SPIRV       STATIC IMPORTED)
    add_library(SPVRemapper STATIC IMPORTED)
    add_library(HLSL        STATIC IMPORTED)
    add_library(SPIRV-Tools STATIC IMPORTED)
    add_library(SPIRV-Tools-opt STATIC IMPORTED)
	
    find_library(GLSLANG_DLIB NAMES glslangd HINTS ${GLSLANG_DEBUG_SEARCH_PATH} )
    find_library(OGLCompiler_DLIB NAMES OGLCompilerd HINTS ${GLSLANG_DEBUG_SEARCH_PATH} )
    find_library(OSDependent_DLIB NAMES OSDependentd HINTS ${GLSLANG_DEBUG_SEARCH_PATH} )
    find_library(SPIRV_DLIB NAMES SPIRVd HINTS ${GLSLANG_DEBUG_SEARCH_PATH} )
    find_library(SPVREMAPPER_DLIB NAMES SPVRemapperd HINTS ${GLSLANG_SEARCH_PATH} )
    find_library(HLSL_DLIB NAMES HLSLd HINTS ${GLSLANG_DEBUG_SEARCH_PATH} )
    find_library(SPIRV_TOOLS_DLIB NAMES SPIRV-Tools HINTS ${SPIRV_TOOLS_DEBUG_SEARCH_PATH} )
    find_library(SPIRV_TOOLS_OPT_DLIB NAMES SPIRV-Tools-opt HINTS "${SPIRVTOOLS_DIR}/source/opt/Debug" )

    set_target_properties(glslang PROPERTIES
                         IMPORTED_LOCATION       "${GLSLANG_LIB}"
                         IMPORTED_LOCATION_DEBUG "${GLSLANG_DLIB}")
    set_target_properties(OGLCompiler PROPERTIES
                         IMPORTED_LOCATION       "${OGLCompiler_LIB}"
                         IMPORTED_LOCATION_DEBUG "${OGLCompiler_DLIB}")
    set_target_properties(OSDependent PROPERTIES
                         IMPORTED_LOCATION       "${OSDependent_LIB}"
                         IMPORTED_LOCATION_DEBUG "${OSDependent_DLIB}")
    set_target_properties(SPIRV PROPERTIES
                         IMPORTED_LOCATION       "${SPIRV_LIB}"
                         IMPORTED_LOCATION_DEBUG "${SPIRV_DLIB}")
    set_target_properties(SPVRemapper PROPERTIES
                         IMPORTED_LOCATION       "${SPVREMAPPER_LIB}"
                         IMPORTED_LOCATION_DEBUG "${SPVREMAPPER_DLIB}")                    
	set_target_properties(HLSL PROPERTIES
                         IMPORTED_LOCATION       "${HLSL_LIB}"
                         IMPORTED_LOCATION_DEBUG "${HLSL_DLIB}")
    set_target_properties(SPIRV-Tools PROPERTIES
                         IMPORTED_LOCATION       "${SPIRV_TOOLS_LIB}"
                         IMPORTED_LOCATION_DEBUG "${SPIRV_TOOLS_DLIB}")
    set_target_properties(SPIRV-Tools-opt PROPERTIES
                         IMPORTED_LOCATION       "${SPIRV_TOOLS_OPT_LIB}"
                         IMPORTED_LOCATION_DEBUG "${SPIRV_TOOLS_OPT_DLIB}")                        

    set (GLSLANG_LIBRARIES glslang OGLCompiler OSDependent SPIRV SPVRemapper HLSL)
    set (SPIRV_TOOLS_LIBRARIES SPIRV-Tools SPIRV-Tools-opt)

    message (STATUS "GLSLANG_LIBRARIES: " "${GLSLANG_DLIB} ${OGLCompiler_DLIB} ${OSDependent_DLIB} ${SPIRV_DLIB} ${SPVREMAPPER_LIB} ${HLSL_DLIB}" )
    message (STATUS "SPIRV_TOOLS_LIBRARIES: " ${SPIRV_TOOLS_LIBRARIES})

else ()
    set (GLSLANG_LIBRARIES ${GLSLANG_LIB} ${OGLCompiler_LIB} ${OSDependent_LIB} ${SPIRV_LIB} ${SPVREMAPPER_LIB} ${HLSL_LIB})
    set (SPIRV_TOOLS_LIBRARIES ${SPIRV_TOOLS_OPT_LIB} ${SPIRV_TOOLS_LIB})
endif()

###

include_directories(${NUMPY_INCLUDE_DIR})
include_directories(${NUMPY_SWIG_DIR})
set_source_files_properties(SOURCE pyvulkan.i PROPERTIES CPLUSPLUS ON)
set_source_files_properties(SOURCE pyglslang.i PROPERTIES CPLUSPLUS ON)

# On windows the _WIN64 is autodefined by the compiler cl.exe when using the Win64 toolchain
if (WIN32)
	if (${CMAKE_SIZEOF_VOID_P} EQUAL 8)
		set_source_files_properties(SOURCE pyvulkan.i PROPERTIES SWIG_FLAGS "-D_WIN32;-D_WIN64;-DVK_USE_PLATFORM_WIN32_KHR")
		set_source_files_properties(SOURCE pyglslang.i PROPERTIES SWIG_FLAGS "-D_WIN32;-D_WIN64")
    endif()
    set(LINK_FLAGS "/ignore:4099 /ignore:4098")
else()
    set_source_files_properties(SOURCE pyvulkan.i PROPERTIES SWIG_FLAGS "-D__LP64__;-DSWIGWORDSIZE64")
    set_source_files_properties(SOURCE pyglslang.i PROPERTIES SWIG_FLAGS "-D__LP64__;-DSWIGWORDSIZE64")
    set(LINK_FLAGS "-Wl,--no-undefined")
endif()

# This preprocessor variable disables the automatic linking of pythonXY_d.lib to use the release version of python.lib
add_definitions(-DSWIG_PYTHON_INTERPRETER_NO_DEBUG)
add_definitions(-DVK_PROTOTYPES)
if(WIN32)
	add_definitions(-DVK_USE_PLATFORM_WIN32_KHR)
endif()

# With Visual Studio we need to turn off iterator debugging because we are linking against the release version of pythonXY.lib
if(MSVC)
	add_definitions(-D_ITERATOR_DEBUG_LEVEL=0)
endif()

set(SWIG_MODULE_pyvulkan_EXTRA_DEPS vulkan.ixx shared_ptrs.ixx)
swig_add_library(pyvulkan LANGUAGE python SOURCES pyvulkan.i)
swig_link_libraries(pyvulkan ${PYTHON_LIBRARIES} ${NUMPY_LIB} ${VULKAN_LIB})
set_target_properties(${SWIG_MODULE_pyvulkan_REAL_NAME} PROPERTIES LINK_FLAGS ${LINK_FLAGS})

install(TARGETS ${SWIG_MODULE_pyvulkan_REAL_NAME} DESTINATION bin)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/pyvulkan.py DESTINATION bin)
install(FILES test_pyvulkan.py DESTINATION bin)
install(FILES lena_std.png DESTINATION bin)

if(MSVC)
    set_target_properties(${SWIG_MODULE_pyvulkan_REAL_NAME} PROPERTIES COMPILE_FLAGS "/bigobj")
endif()

swig_add_library(pyglslang LANGUAGE python SOURCES pyglslang.i)
swig_link_libraries(pyglslang ${PYTHON_LIBRARIES} ${NUMPY_LIB} ${GLSLANG_LIBRARIES} ${SPIRV_TOOLS_LIBRARIES} Threads::Threads)
set_target_properties(${SWIG_MODULE_pyglslang_REAL_NAME} PROPERTIES LINK_FLAGS ${LINK_FLAGS})

install(TARGETS ${SWIG_MODULE_pyglslang_REAL_NAME} DESTINATION bin)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/pyglslang.py DESTINATION bin)


