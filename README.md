# Vulkan Python Bindings

## How to install

I didn't try to do a manylinux build so binaries will only work on the same distribution of linux that they were build with.
The only binary version available are wheel files for Ubuntu 18.04 for a few python version.
They are available as gitlab pipeline artefacts.

## How to build the WHL

### Linux

Check this [dockerfile](docker/ubuntu-dev/Dockerfile) for an example how to setup the environment to build.

```
PYTHONPATH=/usr/share/vulkan/registry python genswigi.py /usr/share/vulkan/registry/vk.xml .
python setup.py bdist_wheel
```

### Windows

* Install the VulkanSDK.
* Do the manual hack detailed in [How To Update VulkanSDK](HowToUpdateVulkanSDK.md)
* Install CMake
* Clone [Vulkan-Docs](https://github.com/KhronosGroup/Vulkan-Docs)
* Install a tool chain like Visual Studio

Do something like this:

```
set PYTHONPATH=.\Vulkan-Docs\scripts
python genswigi.py .\Vulkan-Docs\xml\vk.xml .
python setup.py bdist_wheel
```

The current setup.py looks for Visual Studio 2017, you can hack this.

### Tests

Coverage is very limited. Currently we have the equivalent of the "template" sample in the Lunar SDK. It's a textured cube.

More test cases are welcome.

The unit tests depends on the following packages:

* contextlib2
* pillow

After cloning this repository:

```
python test_vulkanmitts_no_window.py
python hello_vulkanmittsoffscreen.py
```

If you are running on a Linux headless server with NVIDIA cards you still need to install Xorg and set this environment variable:
```
export DISPLAY=:0
```

## Developer Overview

These python bindings are for the most part generated from vk.xml in [Vulkan-Docs](https://github.com/KhronosGroup/Vulkan-Docs) using a script derived from [generator.py](https://github.com/KhronosGroup/Vulkan-Docs/blob/1.0/src/spec/generator.py).

* genswigi.py generates two SWIG interfaces files vulkan.ixx and shared_ptr.ixx;
* swig.exe generates the actual bindings from vulkanmitts.i which includes these generated interface files.

Because of they are generated from the spec, the bindings are complete, excluding some extensions, but not tested.

Also included is pyglslang, Python binding for the glslang library that implements GLSL to SPIR-V compilation.

