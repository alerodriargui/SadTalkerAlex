$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Run-Python {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Error ejecutando $Executable" }
}
Run-Python 'python' @('-c', 'import sys; assert sys.version_info[:2] == (3, 10)')
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw 'Instala FFmpeg y añádelo al PATH antes de continuar.' }
if (-not (Test-Path '.venv/Scripts/python.exe')) { Run-Python 'python' @('-m', 'venv', '.venv') }
Run-Python '.venv/Scripts/python.exe' @('-m', 'pip', 'install', '-r', 'requirements.txt')
if (-not (Test-Path 'vendor/SadTalker/inference.py')) {
    git clone --depth 1 https://github.com/OpenTalker/SadTalker.git vendor/SadTalker
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo descargar SadTalker.' }
}
if (-not (Test-Path '.engine/Scripts/python.exe')) { Run-Python 'python' @('-m', 'venv', '.engine') }
Run-Python '.engine/Scripts/python.exe' @('-m', 'pip', 'install', 'pip<25', 'setuptools<70', 'wheel')
Run-Python '.engine/Scripts/python.exe' @('-m', 'pip', 'install', 'torch==1.13.1+cu117', 'torchvision==0.14.1+cu117', 'torchaudio==0.13.1+cu117', '--extra-index-url', 'https://download.pytorch.org/whl/cu117')
Run-Python '.engine/Scripts/python.exe' @('-m', 'pip', 'install', '-r', 'requirements-engine.txt')
$checkpointPath = Join-Path $PSScriptRoot 'vendor/SadTalker/checkpoints'
New-Item -ItemType Directory -Force -Path $checkpointPath | Out-Null
foreach ($modelName in @('mapping_00109-model.pth.tar', 'SadTalker_V0.0.2_256.safetensors')) {
    $modelPath = Join-Path $checkpointPath $modelName
    if (-not (Test-Path $modelPath)) {
        Write-Host "Descargando $modelName..."
        Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/$modelName" -OutFile "$modelPath.part"
        Move-Item -LiteralPath "$modelPath.part" -Destination $modelPath
    }
}
$weightsPath = Join-Path $PSScriptRoot 'vendor/SadTalker/gfpgan/weights'
New-Item -ItemType Directory -Force -Path $weightsPath | Out-Null
foreach ($weightName in @('alignment_WFLW_4HG.pth', 'detection_Resnet50_Final.pth')) {
    $weightPath = Join-Path $weightsPath $weightName
    if (-not (Test-Path $weightPath)) {
        Write-Host "Descargando $weightName..."
        Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/xinntao/facexlib/releases/download/v0.1.0/$weightName" -OutFile "$weightPath.part"
        Move-Item -LiteralPath "$weightPath.part" -Destination $weightPath
    }
}
Run-Python '.engine/Scripts/python.exe' @('-c', 'import torch, face_alignment, safetensors; print(torch.cuda.is_available())')
Push-Location 'vendor/SadTalker'
try {
    Run-Python (Join-Path $PSScriptRoot '.engine/Scripts/python.exe') @('inference.py', '--help')
} finally {
    Pop-Location
}
Set-Content -LiteralPath '.engine/ready' -Value 'ok'
Write-Host 'Instalación terminada. Abre iniciar.bat.'
