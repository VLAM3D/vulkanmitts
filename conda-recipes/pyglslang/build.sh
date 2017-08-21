#!/bin/bash
mkdir build
cd build

cmake .. -DCMAKE_INSTALL_PREFIX=$PREFIX -DNUMPY_SWIG_DIR=/home/mathieu/dev/pyvulkan/numpy_swig -DCMAKE_BUILD_TYPE=Release -DVULKAN_SDK=/home/mathieu/vulkan/VulkanSDK/1.0.57.0

cmake --build . --config Release --target _pyglslang

cp "$SRC_DIR/build/_pyglslang.so" "$SP_DIR"
cp "$SRC_DIR/build/pyglslang.py" "$SP_DIR"