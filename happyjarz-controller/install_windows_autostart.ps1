$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue)
if (-not $Python) {
    $Python = (Get-Command python.exe -ErrorAction Stop)
}

& $Python.Source -m pip install --user -r (Join-Path $Here "requirements.txt")

$Startup = [Environment]::GetFolderPath("Startup")
$Launcher = Join-Path $Startup "HappyJarzPlugWatch.cmd"
$Watcher = Join-Path $Here "happyjarz_plug_watch.py"

$Command = '@echo off' + "`r`n" + 'start "" "' + $Python.Source + '" "' + $Watcher + '"' + "`r`n"
Set-Content -Path $Launcher -Value $Command -Encoding ASCII

Write-Host "Installed: $Launcher"
Write-Host "The watcher will start at Windows login and open the HAPPY JARZ controller when a Jar is plugged in."
