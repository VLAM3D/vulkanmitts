#!/bin/bash
PYTHONPATH=/usr/share/vulkan/registry python genswigi.py /usr/share/vulkan/registry/vk.xml .
mkdir -p build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX=$PREFIX -DCMAKE_BUILD_TYPE=Release
cmake --build . --config Release --target _vulkanmitts -- -j$(nproc)

cp "$SRC_DIR/build/_vulkanmitts.so" "$SP_DIR"
cp "$SRC_DIR/build/vulkanmitts.py" "$SP_DIR"