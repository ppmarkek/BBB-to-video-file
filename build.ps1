$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Creating local virtual environment (.venv)..." -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$pip = ".\.venv\Scripts\python.exe"
$pyinstaller = ".\.venv\Scripts\pyinstaller.exe"

Write-Host "Installing local dependencies..." -ForegroundColor Cyan
& $pip -m pip install --upgrade pip
& $pip -m pip install -r requirements-dev.txt

Write-Host "Building bbb-download.exe..." -ForegroundColor Cyan
& $pyinstaller --noconfirm bbb_download.spec

Write-Host ""
Write-Host "Done: dist\bbb-download.exe" -ForegroundColor Green
Copy-Item -Force "run.bat" "dist\run.bat"
Write-Host "Also: dist\run.bat (double-click to paste URL)" -ForegroundColor Green
