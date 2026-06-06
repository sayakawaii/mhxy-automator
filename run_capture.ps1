# run_capture.ps1
# Runs run_tasks.py as admin, captures all output to a timestamped log file.
# Called via: Start-Process powershell.exe -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File <this_file>"
param(
    [string]$ExtraArgs = ""
)

# --- Force UTF-8 everywhere so Chinese task names / window titles are readable ---
# (ISSUE-003: garbled Chinese; ISSUE-005: NativeCommandError from stderr capture).
try { chcp 65001 > $null } catch {}
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$projectRoot = "E:\Documents\Project\Python\mhxy-automator"
$pyExe       = "$projectRoot\venv\Scripts\python.exe"
$script      = "$projectRoot\src\run_tasks.py"
$logDir      = "$projectRoot\src\img\debug_captures"
$timestamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile     = "$logDir\run_${timestamp}.log"
$doneFile    = "$logDir\run_${timestamp}.done"

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }

"=== RUN START $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File -FilePath $logFile -Encoding UTF8

if ($ExtraArgs) {
    & $pyExe $script $ExtraArgs.Split(" ") 2>&1 | Tee-Object -FilePath $logFile -Append
} else {
    & $pyExe $script 2>&1 | Tee-Object -FilePath $logFile -Append
}

$exitCode = $LASTEXITCODE
"=== RUN END $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') EXIT_CODE=$exitCode ===" | Out-File -FilePath $logFile -Append -Encoding UTF8

# Write sentinel file so the caller knows the run is complete
"$timestamp|$exitCode|$logFile" | Out-File -FilePath $doneFile -Encoding UTF8 -NoNewline
