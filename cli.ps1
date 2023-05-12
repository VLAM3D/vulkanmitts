param(
[string]$pythonversion="3.10"
)
$ErrorActionPreference = "Stop "
$minicondaPath = "$env:USERPROFILE\miniconda3"
if (-Not (Test-Path $minicondaPath))
{
    $minicondaPath = "$env:USERPROFILE\mambaforge"
}
if (-Not (Test-Path $minicondaPath))
{
    $minicondaPath = "$env:LOCALAPPDATA\Continuum\miniconda3"
}
$condahook = $minicondaPath + "\shell\condabin\conda-hook.ps1"
$envname = "vk_" + $pythonversion
$envpath = $minicondaPath + "\envs\" + $envname
&$condahook
$env:VULKAN_SDK = "C:\VulkanSDK\1.3.246.0"
$env:Path = $env:Path + ";" + $env:VULKAN_SDK + "\Bin;C:\Program Files\CMake\bin"
$env:VK_LAYER_PATH = $env:VULKAN_SDK + "\Bin"
$env:VK_INSTANCE_LAYERS = "VK_LAYER_KHRONOS_validation"
if (Test-Path $envpath)
{
    conda activate $envname
}
else
{
    conda activate base
    conda update conda -c conda-forge -y
    conda config --add channels conda-forge
    conda config --set channel_priority strict
    conda install mamba -n base -c conda-forge -y
    mamba create -n $envname python=$pythonversion -c conda-forge -y
    conda activate $envname
}
if (Test-Path $envpath)
{
    mamba install -y numpy pillow pyqt contextlib2 swig -c conda-forge
}
else
{
    throw "Environment Issue"
}