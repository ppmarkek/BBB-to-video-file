param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Не найдено .venv. Сначала запусти .\setup_local_ai.ps1."
}

Write-Host "Installing build dependencies..." -ForegroundColor Cyan
& $python -m pip install -e ".[dev,local-ai]"
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось установить зависимости для сборки."
}

if (-not $SkipTests) {
    Write-Host "Running tests..." -ForegroundColor Cyan
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) {
        throw "Сборка остановлена: тесты не прошли."
    }
}

Write-Host "Building Konspekt.exe..." -ForegroundColor Cyan
& $python scripts\make_icon.py
& $python -m PyInstaller --noconfirm --clean packaging\Konspekt.spec
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось собрать Konspekt.exe."
}

Copy-Item -LiteralPath "docs\release.md" -Destination "dist\Konspekt\README.md" -Force
Write-Host ""
Write-Host "Ready: dist\Konspekt\Konspekt.exe" -ForegroundColor Green
Write-Host "Copy the whole dist\Konspekt folder; do not move the exe out of it." -ForegroundColor Green
