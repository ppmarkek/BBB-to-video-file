@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m konspekt
) else (
  start "" pythonw -m konspekt
)
