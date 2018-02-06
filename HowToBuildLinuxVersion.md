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

## Manual build 

```
mkdir build
cd build
mkdir py27
cd py27 
cmake ../.. -DVULKAN_SDK=~/VulkanSDK/1.0.65.0 -DCMAKE_INSTALL_PREFIX=~/dev/pyvulkan/build/py27 -DNUMPY_SWIG_DIR=~/dev/pyvulkan/numpy_swig
make -j$(nproc) install
```
# Running tests with manual build and Lunar validation layers 

```
cd ~/VulkanSDK/1.0.65.0
source setup-env.sh
export PYTHONPATH=~/dev/pyvulkan/build/py27/bin
cd ~/dev/pyvulkan
python test_pyvulkan_no_window.py
```

Every test should be ok and no warning from Lunar SDK.

Note that setup-env.sh exports VK_LAYER_PATH that enables the validation layers on Linux.

## Installation of Lunar Vulkan SDK

Here's one way to install the latest Vulkan runtime and validation layers for every applications on Ubuntu.

```
sudo rsync --links *.* /usr/local/lib
sudo ldconfig -v
```