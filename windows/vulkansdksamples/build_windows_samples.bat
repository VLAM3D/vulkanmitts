echo off

:: Specify UTF-8 for character encoding
chcp 65001

:: Check that cmake is configured
where cmake.exe > nul 2>&1
if not %errorlevel% equ 0 (
    echo ERROR: CMake was not found. Please install CMake or put cmake.exe in your PATH.
    exit /b 1
)

set version_string=Visual Studio 15 2017

set START_DIR=%CD%
cd %VULKAN_SDK%

:: Build glslang
cd glslang
md build
cd build
cmake -G "%version_string%" -A x64 -DPYTHON_EXECUTABLE=%CONDA_PREFIX%/python.exe ..
cmake --build . --config Release --target ALL_BUILD -- -m:%NUMBER_OF_PROCESSORS% 
cmake --build . --config Debug --target ALL_BUILD -- -m:%NUMBER_OF_PROCESSORS% 
cd ..\..

:: Build spirv-tools
cd spirv-tools
md build
cd build
cmake -G "%version_string%" -A x64 -DPYTHON_EXECUTABLE=%CONDA_PREFIX%/python.exe ..
cmake --build . --config Release --target ALL_BUILD -- -m:%NUMBER_OF_PROCESSORS% 
cmake --build . --config Debug --target ALL_BUILD -- -m:%NUMBER_OF_PROCESSORS% 
cd ..\..

:: Build samples
cd samples
md build
cd build
cmake -G "%version_string%" -A x64 -DPYTHON_EXECUTABLE=%CONDA_PREFIX%/python.exe ..
cmake --build . --config Release --target ALL_BUILD -- -m:%NUMBER_OF_PROCESSORS% 
cmake --build . --config Debug --target ALL_BUILD -- -m:%NUMBER_OF_PROCESSORS% 

cd %START_DIR%
