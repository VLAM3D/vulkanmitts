mkdir build
cd build

if "%PY_VER%"=="2.7" (
   echo "Python 2.7 not supported"
   exit /b -1
)
set MSVC_VER=15.0
set VS_VERSION="15.0"
set VS_MAJOR="15"
set VS_YEAR="2017"
set CMAKE_GENERATOR="Visual Studio 15 2017 Win64"
set CMAKE_FLAGS=-DCMAKE_INSTALL_PREFIX=%PREFIX%
set CMAKE_FLAGS=%CMAKE_FLAGS% -DCMAKE_BUILD_TYPE=Release

cmake -G %CMAKE_GENERATOR% %CMAKE_FLAGS% .. -Wno-dev

set CMAKE_CONFIG="Release"
cmake --build . --config %CMAKE_CONFIG% --target _pyglslang

xcopy "Release\_pyglslang.pyd" "%SP_DIR%"
xcopy "pyglslang.py" "%SP_DIR%"

if errorlevel 1 exit 1

:: Add more build steps here, if they are necessary.

:: See
:: http://docs.continuum.io/conda/build.html
:: for a list of environment variables that are set during the build process.
