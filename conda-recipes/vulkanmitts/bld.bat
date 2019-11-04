if "%PY_VER%"=="2.7" (
   echo "Python 2.7 not supported"
   exit /b -1
)

git clone https://github.com/KhronosGroup/Vulkan-Docs.git
pushd Vulkan-Docs
git checkout v1.1.121
popd
set PYTHONPATH=.\Vulkan-Docs\scripts
python genswigi.py .\Vulkan-Docs\xml\vk.xml .

mkdir -p build
cd build
set CMAKE_GENERATOR="Visual Studio 15 2017 Win64"
set CMAKE_FLAGS=-DCMAKE_INSTALL_PREFIX=%PREFIX%
set CMAKE_FLAGS=%CMAKE_FLAGS% -DCMAKE_BUILD_TYPE=Release

cmake -G %CMAKE_GENERATOR% %CMAKE_FLAGS% .. -Wno-dev

set CMAKE_CONFIG="Release"
cmake --build . --config %CMAKE_CONFIG% --target _vulkanmitts

xcopy "Release\_vulkanmitts.pyd" "%SP_DIR%"
xcopy "vulkanmitts.py" "%SP_DIR%"

if errorlevel 1 exit 1

:: Add more build steps here, if they are necessary.

:: See
:: http://docs.continuum.io/conda/build.html
:: for a list of environment variables that are set during the build process.
