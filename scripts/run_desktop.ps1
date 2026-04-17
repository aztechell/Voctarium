param(
    [string]$ProjectRoot = (Join-Path $PSScriptRoot "..")
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

$resolvedProjectRoot = Resolve-AbsolutePath -PathValue $ProjectRoot
$venvPython = Join-Path $resolvedProjectRoot ".venv311\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Python environment not found: $venvPython. Run scripts/setup_assets.ps1 first."
}

Push-Location $resolvedProjectRoot
try {
    # Local desktop run: use project directory as runtime root.
    $env:VOCTARIUM_RUNTIME_ROOT = $resolvedProjectRoot
    $env:VOCTARIUM_RESOURCE_ROOT = $resolvedProjectRoot

    Write-Host "Ensuring desktop dependencies..."
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", "requirements-desktop.txt")

    Write-Host "Launching desktop window..."
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "app.desktop_entry")
}
finally {
    Pop-Location
}

