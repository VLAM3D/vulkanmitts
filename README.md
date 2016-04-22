# Vulkan Python Bindings

## Overview

These python bindings are for most part generated from vk.xml in [Vulkan-Docs](https://github.com/KhronosGroup/Vulkan-Docs) using a script derived from [generator.py](https://github.com/KhronosGroup/Vulkan-Docs/blob/1.0/src/spec/generator.py). 

* genswigi.py generates two SWIG interfaces files vulkan.ixx and shared_ptr.ixx;
* swig.exe generates the actual bindings from pyvulkan.i which includes these generated interface file.

Because of they are generated from the spec, the bindings are 100% complete, but not 100% tested.

Also included is pyglslang, Python binding for the glslang library that implements GLSL to SPIR-V compilation.

## How to build

The build is based on CMake but currently it only works on Windows with Python x64 3.x, other variants should be relatively easy to add, but 32bit variants will be tricky to implement because Vulkan's handle type are not uniform on 32bit architecture.

### Dependencies

* Numpy
* [Vulkan-Docs](https://github.com/KhronosGroup/Vulkan-Docs)
* SWIG 
* Lunar Vulkan SDK (tested with 1.0.5)

### Command line

Example for a cloned repo in c:\dev\pyvulkan using Visual Studio 2013, this is for an out of source CMake build, in a empty folder c:\build\pyvulkan

```
cd c:\build\pyvulkan
cmake ..\..\dev\pyvulkan -G "Visual Studio 12 2013 Win64" -DSWIG_DIR=C:\DEV\swigwin-3.0.8 -DSWIG_EXECUTABLE=C:\dev\swigwin-3.0.8\swig.exe -DNUMPY_SWIG_DIR=C:\dev\pyvulkan\numpy_swig\ -DCMAKE_INSTALL_PREFIX=c:\build\pyvulkan -DVULKAN_INCLUDE_DIR=C:\dev\Vulkan-Docs\src -DVULKAN_LIB_DIR=c:/VulkanSDK/1.0.5.0/Bin

```

### Tests

Coverage is very limited. Currently we have the equivalent of the "template" sample in the Lunar SDK. It's a textured cube. 

More tests case are welcome.



