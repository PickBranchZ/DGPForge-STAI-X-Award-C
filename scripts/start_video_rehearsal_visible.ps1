$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$scriptPath = Join-Path $repoRoot "scripts\video_rehearsal_visible_case.ps1"

if (-not (Test-Path $scriptPath)) {
    throw "Missing visible rehearsal script: $scriptPath"
}

Start-Process `
    -FilePath "powershell.exe" `
    -WorkingDirectory $repoRoot `
    -WindowStyle Maximized `
    -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ".\scripts\video_rehearsal_visible_case.ps1",
        "-SkipInstall"
    )
