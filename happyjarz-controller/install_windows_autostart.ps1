$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue)
if (-not $Python) {
    $Python = (Get-Command python.exe -ErrorAction Stop)
}

& $Python.Source -m pip install --user -r (Join-Path $Here "requirements.txt")

$Startup = [Environment]::GetFolderPath("Startup")
$Launcher = Join-Path $Startup "HappyJarzController.cmd"
$Script = Join-Path $Here "happyjarz_controller.py"

$Command = '@echo off' + "`r`n" + 'start "" "' + $Python.Source + '" "' + $Script + '"' + "`r`n"
Set-Content -Path $Launcher -Value $Command -Encoding ASCII

Write-Host "Installed: $Launcher"
Write-Host "HAPPY JARZ Controller will start at Windows login and wait for a Jar to be plugged in."
