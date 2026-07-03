@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" (
  bbb-download.exe
) else (
  bbb-download.exe "%~1"
)
