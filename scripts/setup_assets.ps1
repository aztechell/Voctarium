param(
    [string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
    [string]$PythonVersion = "3.11",
    [switch]$ForceDownload,
    [switch]$SkipWarmup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Resolve-AbsolutePath {
    param([Parameter(Mandatory = $true)][string]$PathValue)

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $PathValue))
}

function Remove-DirectorySafely {
    param(
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string]$ProjectRootPath
    )

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        return
    }

    $resolvedTarget = Resolve-AbsolutePath -PathValue $TargetPath
    $resolvedRoot = Resolve-AbsolutePath -PathValue $ProjectRootPath
    if (-not $resolvedTarget.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside project root: $resolvedTarget"
    }
    if ($resolvedTarget -eq $resolvedRoot) {
        throw "Refusing to remove project root."
    }

    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Ensure-HuggingFaceSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string]$RepoId,
        [Parameter(Mandatory = $true)][string]$TargetDir
    )

    if (Test-Path -LiteralPath $TargetDir) {
        return
    }

    Write-Host "Downloading Hugging Face snapshot $RepoId to $TargetDir..."
    @"
from huggingface_hub import snapshot_download
snapshot_download(repo_id="$RepoId", local_dir=r"$TargetDir", local_dir_use_symlinks=False)
"@ | & $PythonExe -
    if ($LASTEXITCODE -ne 0) {
        throw "Snapshot download failed: $RepoId"
    }
}

$resolvedProjectRoot = Resolve-AbsolutePath -PathValue $ProjectRoot
Write-Host "Project root: $resolvedProjectRoot"

Push-Location $resolvedProjectRoot
try {
    $venvDir = Join-Path $resolvedProjectRoot ".venv311"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    $binDir = Join-Path $resolvedProjectRoot "bin"
    $modelsDir = Join-Path $resolvedProjectRoot "models"
    $ffmpegExe = Join-Path $binDir "ffmpeg.exe"
    $fasterWhisperMediumDir = Join-Path $modelsDir "faster-whisper-medium"
    $rupunctDir = Join-Path $modelsDir "rupunct-big"
    $tmpDir = Join-Path $resolvedProjectRoot "storage\bootstrap"

    New-Item -ItemType Directory -Force -Path $binDir, $modelsDir, $tmpDir | Out-Null

    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Python launcher 'py' not found in PATH."
    }

    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host "Creating virtual environment (.venv311) with Python $PythonVersion..."
        Invoke-CheckedCommand -FilePath "py" -Arguments @("-$PythonVersion", "-m", "venv", $venvDir)
    }
    else {
        Write-Host "Virtual environment exists: $venvDir"
    }

    Write-Host "Installing dependencies from requirements.txt..."
    Invoke-CheckedCommand -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-CheckedCommand -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", "requirements.txt")
    Write-Host "Installing CUDA runtime wheels for ctranslate2 (Windows)..."
    Invoke-CheckedCommand -FilePath $venvPython -Arguments @(
        "-m", "pip", "install", "nvidia-cublas-cu12", "nvidia-cudnn-cu12"
    )

    if ($ForceDownload -or -not (Test-Path -LiteralPath $ffmpegExe)) {
        $ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        $ffmpegZip = Join-Path $tmpDir "ffmpeg-release-essentials.zip"
        $ffmpegExtractDir = Join-Path $tmpDir ("ffmpeg_extract_" + [Guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Force -Path $ffmpegExtractDir | Out-Null

        Write-Host "Downloading ffmpeg from $ffmpegUrl..."
        Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZip
        Write-Host "Extracting ffmpeg archive..."
        Expand-Archive -LiteralPath $ffmpegZip -DestinationPath $ffmpegExtractDir -Force

        $downloadedFfmpeg = Get-ChildItem -LiteralPath $ffmpegExtractDir -Recurse -File -Filter "ffmpeg.exe" |
            Select-Object -First 1
        if ($null -eq $downloadedFfmpeg) {
            throw "ffmpeg.exe not found in archive."
        }

        Copy-Item -LiteralPath $downloadedFfmpeg.FullName -Destination $ffmpegExe -Force
        Remove-DirectorySafely -TargetPath $ffmpegExtractDir -ProjectRootPath $resolvedProjectRoot
    }
    else {
        Write-Host "ffmpeg already exists: $ffmpegExe"
    }

    if (-not (Test-Path -LiteralPath $ffmpegExe)) {
        throw "ffmpeg.exe was not prepared: $ffmpegExe"
    }
    Invoke-CheckedCommand -FilePath $ffmpegExe -Arguments @("-version")

    Ensure-HuggingFaceSnapshot -PythonExe $venvPython -RepoId "RUPunct/RUPunct_big" -TargetDir $rupunctDir
    Ensure-HuggingFaceSnapshot -PythonExe $venvPython -RepoId "Systran/faster-whisper-medium" -TargetDir $fasterWhisperMediumDir
    if (-not (Test-Path -LiteralPath $rupunctDir)) {
        throw "RUPunct model directory is missing: $rupunctDir"
    }
    if (-not (Test-Path -LiteralPath $fasterWhisperMediumDir)) {
        throw "faster-whisper medium model directory is missing: $fasterWhisperMediumDir"
    }

    Write-Host "Verifying Python imports..."
@" 
import importlib.util
missing = [name for name in ("faster_whisper", "transformers", "torch") if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit("Missing modules: " + ", ".join(missing))
cuda_bins = []
for module_path in ("nvidia/cublas/bin", "nvidia/cudnn/bin"):
    spec = importlib.util.find_spec("nvidia")
    if spec and spec.submodule_search_locations:
        base = list(spec.submodule_search_locations)[0]
        import os
        candidate = os.path.join(base, *module_path.split("/")[1:])
        cuda_bins.append((candidate, os.path.isdir(candidate)))
print("CUDA runtime bins:", cuda_bins)
print("Imports OK")
"@ | & $venvPython -
    if ($LASTEXITCODE -ne 0) {
        throw "Python import check failed."
    }

    Write-Host "Verifying RUPunct model load..."
@"
from transformers import AutoModelForTokenClassification, AutoTokenizer
AutoTokenizer.from_pretrained(r"$rupunctDir")
AutoModelForTokenClassification.from_pretrained(r"$rupunctDir")
print("RUPunct model is ready")
"@ | & $venvPython -
    if ($LASTEXITCODE -ne 0) {
        throw "RUPunct model check failed."
    }

    if (-not $SkipWarmup) {
        Write-Host "Warming up faster-whisper medium on CUDA..."
        @"
from faster_whisper import WhisperModel
model = WhisperModel(r"$fasterWhisperMediumDir", device="cuda", compute_type="float16")
print("faster-whisper medium is ready")
"@ | & $venvPython -
        if ($LASTEXITCODE -ne 0) {
            throw "faster-whisper warmup failed."
        }
    }
    else {
        Write-Host "Skipping faster-whisper warmup (SkipWarmup)."
    }

    Write-Host "Asset setup completed successfully."
    Write-Host "ffmpeg: $ffmpegExe"
    Write-Host "faster-whisper model: $fasterWhisperMediumDir"
    Write-Host "rupunct model: $rupunctDir"
    Write-Host "python: $venvPython"
}
finally {
    Pop-Location
}
