# How to build the Linux version

* apt install swig (currently 3.0.8 which is enough)
* apt install packages necessary to build CMake
* Download source and build the latest version of CMake
* Download and install Lunar Vulkan SDK of appropriate version (.run file)
* Undefine ENABLE_OPT in all scripts and makefile
* Run ./build_samples.sh
* Create and activate a conda environment with the desired Python version and numpy
* Manual build with CMake & make command similar to the one below
* To create wheel files use setup.py bdist_wheel

```
mkdir build
cd build
mkdir py27
cd py27 
cmake ../.. -DVULKAN_SDK=~/VulkanSDK/1.0.65.0 -DCMAKE_INSTALL_PREFIX=~/dev/pyvulkan/build/py27 -DNUMPY_SWIG_DIR=~/dev/pyvulkan/numpy_swig
make -j$(nproc) install
```