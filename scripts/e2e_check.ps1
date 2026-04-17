param(
    [string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
    [string]$InputPath = "test-input",
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [int]$SmokeDurationSeconds = 180,
    [int]$PollIntervalSeconds = 3,
    [int]$SmokeTimeoutMinutes = 45,
    [int]$FullTimeoutMinutes = 240
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Resolve-AbsolutePath {
    param(
        [Parameter(Mandatory = $true)][string]$BaseDir,
        [Parameter(Mandatory = $true)][string]$PathValue
    )

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $BaseDir $PathValue))
}

function Resolve-InputFilePath {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRootPath,
        [Parameter(Mandatory = $true)][string]$InputValue
    )

    $candidate = Resolve-AbsolutePath -BaseDir $ProjectRootPath -PathValue $InputValue
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        return $candidate
    }

    if (Test-Path -LiteralPath $candidate -PathType Container) {
        $supported = @("*.mp4", "*.m4a", "*.mp3", "*.wav")
        $files = @()
        foreach ($pattern in $supported) {
            $files += Get-ChildItem -LiteralPath $candidate -File -Filter $pattern
        }
        if ($files.Count -eq 0) {
            throw "No supported input files found in: $candidate"
        }

        $selected = $files | Sort-Object Length -Descending | Select-Object -First 1
        Write-Host "InputPath is a directory. Selected file: $($selected.FullName)"
        return $selected.FullName
    }

    throw "Input path does not exist: $candidate"
}

function Invoke-CurlJson {
    param([Parameter(Mandatory = $true)][string[]]$Args)

    $output = & curl.exe @Args "-w" "`n%{http_code}"
    if ($LASTEXITCODE -ne 0) {
        throw "curl failed: $($Args -join ' ')"
    }

    $lines = $output -split "`r?`n"
    if ($lines.Count -lt 1) {
        throw "Unexpected curl output."
    }
    $statusCode = [int]$lines[-1]
    if ($lines.Count -eq 1) {
        $body = ""
    }
    else {
        $body = ($lines[0..($lines.Count - 2)] -join "`n").Trim()
    }
    return @{
        StatusCode = $statusCode
        Body = $body
    }
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

function Get-HealthPayload {
    param([Parameter(Mandatory = $true)][string]$Url)

    $response = Invoke-CurlJson -Args @("-sS", "$Url/health")
    if ($response.StatusCode -ne 200) {
        throw "Health check returned HTTP $($response.StatusCode)."
    }
    return ($response.Body | ConvertFrom-Json)
}

function Wait-ServiceReady {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Get-HealthPayload -Url $Url
            Write-Host "Service ready. status=$($health.status) queue=$($health.queue_size)"
            return $health
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Service did not become ready in $TimeoutSeconds seconds."
}

function New-Job {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][bool]$IncludeTimestamps
    )

    $includeValue = if ($IncludeTimestamps) { "true" } else { "false" }
    $response = Invoke-CurlJson -Args @(
        "-sS",
        "-X", "POST",
        "-F", "file=@$FilePath",
        "-F", "include_timestamps=$includeValue",
        "$Url/api/jobs"
    )
    if ($response.StatusCode -ne 200) {
        throw "Create job failed with HTTP $($response.StatusCode): $($response.Body)"
    }

    return ($response.Body | ConvertFrom-Json)
}

function Get-JobStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$JobId
    )

    $response = Invoke-CurlJson -Args @("-sS", "$Url/api/jobs/$JobId")
    if ($response.StatusCode -ne 200) {
        throw "Job status failed for '$JobId' with HTTP $($response.StatusCode): $($response.Body)"
    }
    return ($response.Body | ConvertFrom-Json)
}

function Wait-JobFinal {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$JobId,
        [Parameter(Mandatory = $true)][int]$TimeoutMinutes,
        [Parameter(Mandatory = $true)][int]$PollSeconds
    )

    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $job = Get-JobStatus -Url $Url -JobId $JobId
        Write-Host "job=$JobId status=$($job.status) progress=$($job.progress_percent)% queue=$($job.queue_position)"
        if ($job.status -in @("done", "failed", "cancelled")) {
            return $job
        }
        Start-Sleep -Seconds $PollSeconds
    }
    throw "Job '$JobId' did not finish in $TimeoutMinutes minutes."
}

function Download-Result {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$JobId,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    $httpCode = & curl.exe -sS -L -o $DestinationPath -w "%{http_code}" "$Url/api/jobs/$JobId/result.md"
    if ($LASTEXITCODE -ne 0) {
        throw "curl failed while downloading markdown for job '$JobId'."
    }
    if ([int]$httpCode -ne 200) {
        throw "Result download failed for job '$JobId'. HTTP $httpCode"
    }
}

function Assert-MarkdownShape {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][bool]$ExpectTimestamps
    )

    $content = Get-Content -LiteralPath $Path -Raw
    if ([string]::IsNullOrWhiteSpace($content)) {
        throw "Markdown is empty: $Path"
    }

    $timecodeRegex = "\[\d{2}:\d{2}:\d{2} - \d{2}:\d{2}:\d{2}\]"
    $hasTimecodes = [bool]([regex]::IsMatch($content, $timecodeRegex))
    if ($ExpectTimestamps -and -not $hasTimecodes) {
        throw "Expected timestamps in markdown, but none found: $Path"
    }
    if (-not $ExpectTimestamps -and $hasTimecodes) {
        throw "Expected markdown without timestamps, but timecodes were found: $Path"
    }
}

function Write-Diagnostics {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [string[]]$JobIds
    )

    Write-Host "=== Diagnostics ==="
    try {
        $healthResponse = Invoke-CurlJson -Args @("-sS", "$Url/health")
        Write-Host "Health HTTP: $($healthResponse.StatusCode)"
        Write-Host $healthResponse.Body
    }
    catch {
        Write-Host "Health unavailable: $($_.Exception.Message)"
    }

    foreach ($jobId in $JobIds) {
        if ([string]::IsNullOrWhiteSpace($jobId)) {
            continue
        }
        try {
            $jobResponse = Invoke-CurlJson -Args @("-sS", "$Url/api/jobs/$jobId")
            Write-Host "Job $jobId HTTP: $($jobResponse.StatusCode)"
            Write-Host $jobResponse.Body
        }
        catch {
            Write-Host "Job $jobId unavailable: $($_.Exception.Message)"
        }
    }
}

$resolvedProjectRoot = Resolve-AbsolutePath -BaseDir (Get-Location).Path -PathValue $ProjectRoot
$resolvedInputPath = Resolve-InputFilePath -ProjectRootPath $resolvedProjectRoot -InputValue $InputPath
$pythonExe = Join-Path $resolvedProjectRoot ".venv311\Scripts\python.exe"
$ffmpegExe = Join-Path $resolvedProjectRoot "bin\ffmpeg.exe"
$runDir = Join-Path $resolvedProjectRoot "storage\e2e"
$smokeClipPath = Join-Path $runDir "smoke_3min.mp4"
$fullInputCopyPath = Join-Path $runDir "full_input.mp4"
$metricsPath = Join-Path $runDir "metrics.json"
$serverStdout = Join-Path $runDir "uvicorn.stdout.log"
$serverStderr = Join-Path $runDir "uvicorn.stderr.log"

if (-not (Test-Path -LiteralPath $resolvedInputPath)) {
    throw "Input file not found: $resolvedInputPath"
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python environment missing: $pythonExe. Run scripts/setup_assets.ps1 first."
}
if (-not (Test-Path -LiteralPath $ffmpegExe)) {
    throw "ffmpeg missing: $ffmpegExe. Run scripts/setup_assets.ps1 first."
}

New-Item -ItemType Directory -Force -Path $runDir | Out-Null

Write-Host "Preparing smoke clip ($SmokeDurationSeconds seconds)..."
Invoke-CheckedCommand -FilePath $ffmpegExe -Arguments @(
    "-hide_banner",
    "-loglevel", "error",
    "-y",
    "-i", $resolvedInputPath,
    "-t", "$SmokeDurationSeconds",
    "-c", "copy",
    $smokeClipPath
)

Write-Host "Copying full input to ASCII-safe path..."
Copy-Item -LiteralPath $resolvedInputPath -Destination $fullInputCopyPath -Force

$jobs = [ordered]@{
    smoke = ""
    full = ""
}
$serverProcess = $null

try {
    Write-Host "Starting API server..."
    $serverProcess = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $resolvedProjectRoot `
        -RedirectStandardOutput $serverStdout `
        -RedirectStandardError $serverStderr `
        -PassThru

    Wait-ServiceReady -Url $BaseUrl | Out-Null

    Write-Host "Smoke #1: faster_whisper with timestamps..."
    $swSmokeFaster = [System.Diagnostics.Stopwatch]::StartNew()
    $createSmokeFaster = New-Job -Url $BaseUrl -FilePath $smokeClipPath -IncludeTimestamps $true
    $jobs.smoke = $createSmokeFaster.job_id
    $finalSmokeFaster = Wait-JobFinal -Url $BaseUrl -JobId $createSmokeFaster.job_id -TimeoutMinutes $SmokeTimeoutMinutes -PollSeconds $PollIntervalSeconds
    $swSmokeFaster.Stop()
    if ($finalSmokeFaster.status -ne "done") {
        throw "Smoke faster_whisper job failed: $($finalSmokeFaster.error)"
    }
    $smokeFasterResult = Join-Path $runDir "smoke.md"
    Download-Result -Url $BaseUrl -JobId $createSmokeFaster.job_id -DestinationPath $smokeFasterResult
    Assert-MarkdownShape -Path $smokeFasterResult -ExpectTimestamps $true

    Write-Host "Full run: faster_whisper on full input..."
    $swFull = [System.Diagnostics.Stopwatch]::StartNew()
    $createFull = New-Job -Url $BaseUrl -FilePath $fullInputCopyPath -IncludeTimestamps $true
    $jobs.full = $createFull.job_id
    $finalFull = Wait-JobFinal -Url $BaseUrl -JobId $createFull.job_id -TimeoutMinutes $FullTimeoutMinutes -PollSeconds $PollIntervalSeconds
    $swFull.Stop()
    if ($finalFull.status -ne "done") {
        throw "Full faster_whisper job failed: $($finalFull.error)"
    }
    $fullResult = Join-Path $runDir "full.md"
    Download-Result -Url $BaseUrl -JobId $createFull.job_id -DestinationPath $fullResult
    Assert-MarkdownShape -Path $fullResult -ExpectTimestamps $true

    $fullText = Get-Content -LiteralPath $fullResult -Raw
    $metrics = [ordered]@{
        generated_at = (Get-Date).ToString("o")
        smoke_job_id = $jobs.smoke
        full_job_id = $jobs.full
        smoke_duration_seconds = [math]::Round($swSmokeFaster.Elapsed.TotalSeconds, 2)
        full_duration_seconds = [math]::Round($swFull.Elapsed.TotalSeconds, 2)
        full_markdown_bytes = (Get-Item -LiteralPath $fullResult).Length
        full_markdown_chars = $fullText.Length
    }
    $metrics | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $metricsPath -Encoding UTF8

    Write-Host "E2E completed successfully."
    Write-Host "Metrics: $metricsPath"
}
catch {
    Write-Host "E2E failed: $($_.Exception.Message)"
    Write-Diagnostics -Url $BaseUrl -JobIds @($jobs.smoke, $jobs.full)
    throw
}
finally {
    if ($null -ne $serverProcess) {
        try {
            if (-not $serverProcess.HasExited) {
                Stop-Process -Id $serverProcess.Id -Force
            }
        }
        catch {
            Write-Host "Failed to stop API process: $($_.Exception.Message)"
        }
    }
}
