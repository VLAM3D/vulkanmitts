#!/bin/bash
mkdir build
cd build

cmake .. -DCMAKE_INSTALL_PREFIX=$PREFIX -DCMAKE_BUILD_TYPE=Release

cmake --build . --config Release --target _pyglslang -- -j$(nproc)

cp "$SRC_DIR/build/_pyglslang.so" "$SP_DIR"
cp "$SRC_DIR/build/pyglslang.py" "$SP_DIR"