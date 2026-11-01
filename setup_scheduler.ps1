<#
.SYNOPSIS
    Creates a Windows Scheduled Task for daily Personal News Briefing at 8 AM IST.
.DESCRIPTION
    - Runs as SYSTEM (no login required), whether user is logged on or not
    - Retries on failure: up to 3 times, 15 min apart
    - Logs output to a daily log file
    - Handles DST transitions correctly
#>

param(
    [string]$ProjectDir = (Get-Location).Path,
    [string]$TaskName = "PersonalNewsBriefing"
)

$configFile = Join-Path $ProjectDir "config.yaml"

if (-not (Test-Path $configFile)) {
    Write-Error "config.yaml not found in $ProjectDir. Run this script from the project directory."
    exit 1
}

# Find Python
$python = (Get-Command python).Source
if (-not $python) {
    Write-Error "Python not found in PATH. Make sure Python is installed."
    exit 1
}

# Resolve Python to absolute path (in case it's a symlink/app alias on Windows)
try {
    $python = (Get-Item $python).FullName
} catch {}

# Create logs directory
$logDir = Join-Path $ProjectDir "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# Convert 8 AM IST (UTC+5:30) to local time properly using timezone info
try {
    $istTz = [TimeZoneInfo]::FindSystemTimeZoneById("India Standard Time")
} catch {
    # Fallback: manual offset calculation
    Write-Warning "India Standard Time zone not found. Using manual UTC+5:30 offset."
    $istOffset = [TimeSpan]::FromMinutes(330)
    $utcNow = [DateTime]::UtcNow
    $istNow = $utcNow.Add($istOffset)
    $triggerLocal = [DateTime]::Today.AddHours(8).AddMinutes(0)
    
    # Convert IST trigger to UTC
    $istTrigger = [DateTime]::SpecifyKind($triggerLocal, [DateTimeKind]::Utc).AddHours(-5).AddMinutes(-30)
    # Then convert UTC to local
    $localTrigger = $istTrigger.ToLocalTime()
    $triggerTime = $localTrigger.ToString("HH:mm")
    Write-Host "Using calculated trigger time: $triggerTime"
}

if ($istTz) {
    # Build an IST DateTime for today at 8:00 AM
    $utcNow = [DateTime]::UtcNow
    $istNow = [TimeZoneInfo]::ConvertTimeFromUtc($utcNow, $istTz)
    $istTrigger = [DateTime]::new($istNow.Year, $istNow.Month, $istNow.Day, 8, 0, 0)
    
    # Convert IST trigger time to UTC, then to local
    $utcTrigger = [TimeZoneInfo]::ConvertTimeToUtc($istTrigger, $istTz)
    $localTrigger = $utcTrigger.ToLocalTime()
    $triggerTime = $localTrigger.ToString("HH:mm")
    Write-Host "8:00 AM IST = $triggerTime local time"
}

Write-Host ""
Write-Host "Setting up scheduled task: $TaskName"
Write-Host "  Python:      $python"
Write-Host "  Project:     $ProjectDir"
Write-Host "  Trigger:     Daily at $triggerTime (local)"
Write-Host "  Logs:        $logDir"

# Build the argument string
$argsStr = "main.py --log-file `"$logDir\briefing.log`""
$action = New-ScheduledTaskAction -Execute $python -Argument $argsStr -WorkingDirectory $ProjectDir

# Daily trigger at converted local time
$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime

# Run as SYSTEM, whether user is logged on or not
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Retry settings: if it fails, retry up to 3 times every 15 minutes
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval ([TimeSpan]::FromMinutes(15)) `
    -ExecutionTimeLimit ([TimeSpan]::FromMinutes(30))

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Write-Host ""
    Write-Host "SUCCESS: Task '$TaskName' registered."
    Write-Host "  Runs daily at:  $triggerTime (local time = 8:00 AM IST)"
    Write-Host "  Retries:        3 times, 15 min apart on failure"
    Write-Host "  Runs as:        SYSTEM (background, no login needed)"
    Write-Host "  Logs:           $logDir\briefing.log"
} catch {
    Write-Error "FAILED to create scheduled task: $_"
    exit 1
}

# Also create a batch file for manual testing.
# Written portably: no absolute paths, so the repo does not leak a username
# or a machine-specific Python location.
$batPath = Join-Path $ProjectDir "run_manually.bat"
@"
@echo off
cd /d "%~dp0"

rem Prefer the py launcher, fall back to python on PATH.
set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py"

%PY% main.py --log-file "%~dp0logs\manual_run.log"
pause
"@ | Out-File -FilePath $batPath -Encoding ascii

Write-Host ""
Write-Host "Manual test: Double-click run_manually.bat or run:"
Write-Host "  python main.py"
Write-Host ""
Write-Host "To test the task immediately:"
Write-Host "  Start-ScheduledTask -TaskName `"$TaskName`""
Write-Host ""
Write-Host "To view logs:"
Write-Host "  Get-Content "$logDir\briefing.log" -Tail 20"
