$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "Creating local virtual environment (.venv)..." -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$pip = ".\.venv\Scripts\python.exe"
$pyinstaller = ".\.venv\Scripts\pyinstaller.exe"

Write-Host "Installing local dependencies..." -ForegroundColor Cyan
& $pip -m pip install --upgrade pip
& $pip -m pip install -e ".[dev]"

Write-Host "Building bbb-download.exe..." -ForegroundColor Cyan
& $pyinstaller --noconfirm packaging\bbb_download.spec

Write-Host ""
Write-Host "Done: dist\bbb-download.exe" -ForegroundColor Green
Copy-Item -Force "scripts\run_bbb_downloader.bat" "dist\run.bat"
Write-Host "Also: dist\run.bat (double-click to paste URL)" -ForegroundColor Green
