cmake_minimum_required (VERSION 3.7)
project (vulkanmitts)
set (CMAKE_CXX_STANDARD 11)
#set (CMAKE_VERBOSE_MAKEFILE 1)

set (vulkanmitts_VERSION_MAJOR 0)
set (vulkanmitts_VERSION_MINOR 1)

find_package(Threads REQUIRED)
find_package(SWIG REQUIRED)
include(${SWIG_USE_FILE})

find_package(PythonInterp REQUIRED)
message (STATUS "Using this Python interpreter: " ${PYTHON_EXECUTABLE})

find_package(PythonLibs REQUIRED)
include_directories(${PYTHON_INCLUDE_PATH})
include_directories(${CMAKE_CURRENT_SOURCE_DIR})

find_package(Vulkan REQUIRED)
get_filename_component(VULKAN_SDK ${Vulkan_INCLUDE_DIR} DIRECTORY)
message(STATUS "Found Vulkan SDK: " ${VULKAN_SDK})
message(STATUS "Found Vulkan SDK Include Dir: " ${Vulkan_INCLUDE_DIR})

include_directories(${Vulkan_INCLUDE_DIR})
include_directories(${Vulkan_INCLUDE_DIR}/glslang/Include)
include_directories(${Vulkan_INCLUDE_DIR}/glslang/Public)
include_directories(${Vulkan_INCLUDE_DIR}/glslang/SPIRV)
include_directories(${Vulkan_INCLUDE_DIR}/spirv-tools)

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
if (NOT NUMPY_SWIG_DIR)
  set(NUMPY_SWIG_DIR ${CMAKE_CURRENT_SOURCE_DIR}/numpy_swig)
endif()
message (STATUS "Numpy SWIG file: " ${NUMPY_SWIG_DIR})

####
# GLSLANG DEPENDENCIES

if (WIN32)
    set(SPIRVTOOLS_DIR ${VULKAN_SDK}/spirv-tools/build)
    set (GLSLANG_SEARCH_PATH "${VULKAN_SDK}/Lib")
    set (SPIRV_TOOLS_SEARCH_PATH "${VULKAN_SDK}/Lib")
    set (SPIRV_TOOLS_OPT_SEARCH_PATH "${VULKAN_SDK}/Lib")
endif()

find_library(GLSLANG_LIB NAMES glslang HINTS ${GLSLANG_SEARCH_PATH} )
if(NOT GLSLANG_LIB)
  message(FATAL_ERROR "glslang library not found")
endif()

find_library(GENERICCODEGEN_LIB NAMES GenericCodeGen HINTS ${GLSLANG_SEARCH_PATH} )
if(NOT GENERICCODEGEN_LIB)
  message(FATAL_ERROR "GenericCodeGen library not found")
endif()

find_library(MACHINEINDEPENDENT_LIB NAMES MachineIndependent HINTS ${GLSLANG_SEARCH_PATH} )
if(NOT MACHINEINDEPENDENT_LIB)
  message(FATAL_ERROR "GenericCodeGen library not found")
endif()

find_library(OSDependent_LIB NAMES OSDependent HINTS ${GLSLANG_SEARCH_PATH} )
if(NOT OSDependent_LIB)
  message(FATAL_ERROR "OSDependent library not found")
endif()

find_library(SPIRV_LIB NAMES SPIRV HINTS ${GLSLANG_SEARCH_PATH} )
if(NOT SPIRV_LIB)
  message(FATAL_ERROR "SPIRV library not found")
endif()

find_library(SPVREMAPPER_LIB NAMES SPVRemapper HINTS ${GLSLANG_SEARCH_PATH} )
if(NOT SPVREMAPPER_LIB)
  message(FATAL_ERROR "SPVRemapper library not found")
endif()

find_library(SPIRV_TOOLS_LIB NAMES SPIRV-Tools HINTS ${SPIRV_TOOLS_SEARCH_PATH} )
if(NOT SPIRV_TOOLS_LIB)
  message(FATAL_ERROR "SPIRV-Tools library not found")
endif()

find_library(SPIRV_TOOLS_OPT_LIB NAMES SPIRV-Tools-opt HINTS ${SPIRV_TOOLS_OPT_SEARCH_PATH} )
if(NOT SPIRV_TOOLS_OPT_LIB)
  message(FATAL_ERROR "SPIRV_TOOLS_OPT_LIB library not found")
endif()


set (GLSLANG_LIBRARIES ${GLSLANG_LIB} ${MACHINEINDEPENDENT_LIB} ${GENERICCODEGEN_LIB} ${OSDependent_LIB} ${SPIRV_LIB} ${SPVREMAPPER_LIB} )
set (SPIRV_TOOLS_LIBRARIES ${SPIRV_TOOLS_OPT_LIB} ${SPIRV_TOOLS_LIB})
message (STATUS "GLSLANG_LIBRARIES LIBRARIES: " "${GLSLANG_LIBRARIES}" )
message (STATUS "SPIRV_TOOLS_LIBRARIES LIBRARIES: " "${SPIRV_TOOLS_LIBRARIES}" )

###

include_directories(${NUMPY_INCLUDE_DIR})
include_directories(${NUMPY_SWIG_DIR})
set_source_files_properties(SOURCE vulkanmitts.i PROPERTIES CPLUSPLUS ON)
set_source_files_properties(SOURCE pyglslang.i PROPERTIES CPLUSPLUS ON)

# On windows the _WIN64 is autodefined by the compiler cl.exe when using the Win64 toolchain
if (WIN32)
	if (${CMAKE_SIZEOF_VOID_P} EQUAL 8)
		set_source_files_properties(SOURCE vulkanmitts.i PROPERTIES SWIG_FLAGS "-D_WIN32;-D_WIN64;-DVK_USE_PLATFORM_WIN32_KHR")
		set_source_files_properties(SOURCE pyglslang.i PROPERTIES SWIG_FLAGS "-D_WIN32;-D_WIN64")
    endif()
    set(LINK_FLAGS "/ignore:4099 /ignore:4098")
else()
    set_source_files_properties(SOURCE vulkanmitts.i PROPERTIES SWIG_FLAGS "-D__LP64__;-DSWIGWORDSIZE64")
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

swig_add_library(pyglslang LANGUAGE python SOURCES pyglslang.i)
swig_link_libraries(pyglslang ${PYTHON_LIBRARIES} ${NUMPY_LIB} ${GLSLANG_LIBRARIES} ${SPIRV_TOOLS_LIBRARIES} Threads::Threads)
set_target_properties(${SWIG_MODULE_pyglslang_REAL_NAME} PROPERTIES LINK_FLAGS ${LINK_FLAGS} SWIG_USE_TARGET_INCLUDE_DIRECTORIES ON)

install(TARGETS ${SWIG_MODULE_pyglslang_REAL_NAME} DESTINATION bin)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/pyglslang.py DESTINATION bin)

set(SWIG_MODULE_vulkanmitts_EXTRA_DEPS vulkan.ixx shared_ptrs.ixx)
swig_add_library(vulkanmitts LANGUAGE python SOURCES vulkanmitts.i)
swig_link_libraries(vulkanmitts ${PYTHON_LIBRARIES} ${NUMPY_LIB} Vulkan::Vulkan)
set_target_properties(${SWIG_MODULE_vulkanmitts_REAL_NAME} PROPERTIES LINK_FLAGS ${LINK_FLAGS})

install(TARGETS ${SWIG_MODULE_vulkanmitts_REAL_NAME} DESTINATION bin)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/vulkanmitts.py DESTINATION bin)
install(FILES test_vulkanmitts.py DESTINATION bin)
install(FILES lena_std.png DESTINATION bin)

if(MSVC)
    set_target_properties(${SWIG_MODULE_vulkanmitts_REAL_NAME} PROPERTIES COMPILE_FLAGS "/bigobj")
endif()


