param(
    [string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
    [string]$PythonVersion = "3.11",
    [string]$ExeName = "Voctarium"
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
        [Parameter(Mandatory = $true)][string]$RootPath
    )

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        return
    }

    $resolvedTarget = Resolve-AbsolutePath -PathValue $TargetPath
    $resolvedRoot = Resolve-AbsolutePath -PathValue $RootPath
    if (-not $resolvedTarget.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside project root: $resolvedTarget"
    }
    if ($resolvedTarget -eq $resolvedRoot) {
        throw "Refusing to remove project root."
    }

    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$PathValue)
    if (-not (Test-Path -LiteralPath $PathValue)) {
        New-Item -ItemType Directory -Path $PathValue | Out-Null
    }
}

function Copy-FileIfExists {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    if (-not (Test-Path -LiteralPath $SourcePath)) {
        Write-Warning "Not found, skipping: $SourcePath"
        return $false
    }

    $destinationDirectory = Split-Path -Path $DestinationPath -Parent
    Ensure-Directory -PathValue $destinationDirectory
    Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
    return $true
}

function Copy-DirectoryIfExists {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    if (-not (Test-Path -LiteralPath $SourcePath)) {
        Write-Warning "Not found, skipping: $SourcePath"
        return $false
    }

    Ensure-Directory -PathValue (Split-Path -Path $DestinationPath -Parent)
    if (Test-Path -LiteralPath $DestinationPath) {
        Remove-Item -LiteralPath $DestinationPath -Recurse -Force
    }
    Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Recurse -Force
    return $true
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Ensure-FasterWhisperModel {
    param(
        [Parameter(Mandatory = $true)][string]$ModelDir,
        [Parameter(Mandatory = $true)][string]$PythonExe
    )

    if (Test-Path -LiteralPath $ModelDir) {
        return
    }

    Write-Host "Downloading faster-whisper-medium model to $ModelDir ..."
    Ensure-Directory -PathValue (Split-Path -Path $ModelDir -Parent)
    $pythonCode = "from huggingface_hub import snapshot_download; " +
        "snapshot_download(repo_id='Systran/faster-whisper-medium', " +
        "local_dir=r'$ModelDir', local_dir_use_symlinks=False)"
    Invoke-Checked -FilePath $PythonExe -Arguments @("-c", $pythonCode)
}

function Ensure-HuggingFaceSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$RepoId,
        [Parameter(Mandatory = $true)][string]$ModelDir,
        [Parameter(Mandatory = $true)][string]$PythonExe
    )

    if (Test-Path -LiteralPath $ModelDir) {
        return
    }

    Write-Host "Downloading $RepoId model to $ModelDir ..."
    Ensure-Directory -PathValue (Split-Path -Path $ModelDir -Parent)
    $pythonCode = "from huggingface_hub import snapshot_download; " +
        "snapshot_download(repo_id='$RepoId', " +
        "local_dir=r'$ModelDir', local_dir_use_symlinks=False)"
    Invoke-Checked -FilePath $PythonExe -Arguments @("-c", $pythonCode)
}

$resolvedProjectRoot = Resolve-AbsolutePath -PathValue $ProjectRoot
Write-Host "Project root: $resolvedProjectRoot"

Push-Location $resolvedProjectRoot
try {
    $venvDir = Join-Path $resolvedProjectRoot ".venv311"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"

    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host "Creating .venv311 with Python $PythonVersion..."
        Invoke-Checked -FilePath "py" -Arguments @("-$PythonVersion", "-m", "venv", $venvDir)
    }

    Write-Host "Installing runtime dependencies..."
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", "requirements.txt")
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", "requirements-desktop.txt")

    Remove-DirectorySafely -TargetPath (Join-Path $resolvedProjectRoot "build") -RootPath $resolvedProjectRoot
    Remove-DirectorySafely -TargetPath (Join-Path $resolvedProjectRoot "dist") -RootPath $resolvedProjectRoot

    Write-Host "Building one-folder desktop EXE..."
    $args = @(
        "-m", "PyInstaller",
        "--name", $ExeName,
        "--icon", "app/static/voctarium-icon.ico",
        "--onedir",
        "--noconsole",
        "--clean",
        "--collect-all", "webview",
        "--collect-all", "faster_whisper",
        "--collect-all", "nvidia.cublas",
        "--collect-all", "nvidia.cudnn",
        "--collect-all", "nvidia.cuda_nvrtc",
        "--collect-all", "transformers",
        "--collect-all", "tokenizers",
        "--collect-all", "torch",
        "--collect-all", "reportlab",
        "--add-data", "app/templates;app/templates",
        "--add-data", "app/static;app/static",
        "app/desktop_entry.py"
    )
    Invoke-Checked -FilePath $venvPython -Arguments $args

    $appDistDir = Join-Path $resolvedProjectRoot ("dist\" + $ExeName)
    $exePath = Join-Path $appDistDir ($ExeName + ".exe")
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "Build completed but EXE not found: $exePath"
    }

    Write-Host "Desktop EXE built successfully:"
    Write-Host $exePath

    $distDir = $appDistDir
    $copiedAssets = @()
    if (Copy-FileIfExists -SourcePath (Join-Path $resolvedProjectRoot "bin\ffmpeg.exe") -DestinationPath (Join-Path $distDir "bin\ffmpeg.exe")) {
        $copiedAssets += "bin\\ffmpeg.exe"
    }

    $fasterWhisperModelSource = Join-Path $resolvedProjectRoot "models\faster-whisper-medium"
    Ensure-FasterWhisperModel -ModelDir $fasterWhisperModelSource -PythonExe $venvPython
    if (Copy-DirectoryIfExists -SourcePath $fasterWhisperModelSource -DestinationPath (Join-Path $distDir "models\faster-whisper-medium")) {
        $copiedAssets += "models\\faster-whisper-medium"
    }

    $rupunctModelSource = Join-Path $resolvedProjectRoot "models\rupunct-big"
    Ensure-HuggingFaceSnapshot -RepoId "RUPunct/RUPunct_big" -ModelDir $rupunctModelSource -PythonExe $venvPython
    if (Copy-DirectoryIfExists -SourcePath $rupunctModelSource -DestinationPath (Join-Path $distDir "models\rupunct-big")) {
        $copiedAssets += "models\\rupunct-big"
    }

    if ($copiedAssets.Count -gt 0) {
        Write-Host "Runtime assets copied to dist:"
        $copiedAssets | ForEach-Object { Write-Host " - $_" }
    } else {
        Write-Warning "No runtime assets copied to dist. Add bin/models under project root and rebuild."
    }

    $intermediateExePath = Join-Path $resolvedProjectRoot ("build\" + $ExeName + "\" + $ExeName + ".exe")
    if (Test-Path -LiteralPath $intermediateExePath) {
        Remove-Item -LiteralPath $intermediateExePath -Force
    }

    Write-Host ""
    Write-Host "Use this executable:"
    Write-Host $exePath
    Write-Host "Do not run the intermediate build artifact under build\\$ExeName\\."
}
finally {
    Pop-Location
}
