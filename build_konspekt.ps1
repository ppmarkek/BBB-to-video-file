param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Не найдено .venv. Сначала запусти .\setup_local_ai.ps1."
}

Write-Host "Installing build dependencies..." -ForegroundColor Cyan
& $python -m pip install -r requirements-dev.txt -r requirements-local-ai.txt
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
& $python -m PyInstaller --noconfirm --clean Konspekt.spec
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось собрать Konspekt.exe."
}

Copy-Item -LiteralPath "KONSPEKT_RELEASE.md" -Destination "dist\Konspekt\README.md" -Force
Write-Host ""
Write-Host "Ready: dist\Konspekt\Konspekt.exe" -ForegroundColor Green
Write-Host "Copy the whole dist\Konspekt folder; do not move the exe out of it." -ForegroundColor Green
