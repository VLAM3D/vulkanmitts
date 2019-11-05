# Update Vulkan SDK on Windows

* Download and install latest Vulkan SDK release
* Change four CMakeLists.txt : glslang, spirv-tools, Samples and Samples/Sample-Programs/Hologram
* Add the line add_definitions(-D_ITERATOR_DEBUG_LEVEL=0) in the win32 section for each of these file
* Just do a file compare with previously patched SDK folder with a tool like BeyondCompare
* Overwrite C:\VulkanSDK\x.y.z.w\Samples\build_windows_samples.bat with [this version](windows/vulkansdksamples/build_windows_samples.bat)
* Run this batch file
* Find the corresponding release tag in the following GitHub project https://github.com/KhronosGroup/Vulkan-Docs/releases and checkout the release

