[![Anaconda-Server Badge](https://anaconda.org/mlamarre/pyvulkan/badges/installer/conda.svg)](https://conda.anaconda.org/mlamarre)

* Download and install latest Vulkan SDK release
* Change four CMakeLists.txt : glslang, spirv-tools, Samples and Samples/Sample-Programs/Hologram
* Add the line add_definitions(-D_ITERATOR_DEBUG_LEVEL=0) in the win32 section for each of these file
* Just do a file compare with previously patched SDK folder with a tool like BeyondCompare
* Using C:\VulkanSDK\1.0.65.0\Samples\build_windows_samples.bat would be nice, but we need to define PYTHON_EXECUTABLE for CMake to find the virtualenv Python interpreter
* cmake -G "Visual Studio 14 Win64" -DPYTHON_EXECUTABLE=C:/Users/mathi/Miniconda2/envs/build_pyvk36/python.exe ..
* So do the same as in build_windows_samples.bat manually
* Find the corresponding release tag in the following GitHub project https://github.com/KhronosGroup/Vulkan-Docs/releases and checkout the release
~~~~
git checkout -b v1.0.65-core v1.0.65-core
~~~~
* Add Vulkan-Docs\src\spec to PYTHONPATH 
~~~
set PYTHONPATH=c:\build\pyvulkan36\bin;C:\dev\Vulkan-Docs\src\spec
~~~
* Run genswiggi.py to generate the SWIG interface file
~~~~
python genswigi.py C:\dev\Vulkan-Docs\src\spec\vk.xml .
~~~~
* Go back to the How to build instructions - try to build and fix errors
* Update conda-recipes - do not forget to update Vulkan SDK path in the recipes

