$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -e ".[local-ai]"

Write-Host "" 
Write-Host "Local Whisper is ready." -ForegroundColor Green
Write-Host "For local OCR, install Tesseract separately:" -ForegroundColor Yellow
Write-Host "  winget install UB-Mannheim.TesseractOCR"
Write-Host "" 
Write-Host "The first transcription downloads the selected open Whisper model once."
