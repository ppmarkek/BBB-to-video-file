@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" (
  echo.
  echo BBB Recording Downloader
  echo.
  set /p URL="Вставьте ссылку BBB playback: "
) else (
  set "URL=%~1"
)

if "%URL%"=="" (
  echo Ошибка: ссылка не указана.
  pause
  exit /b 1
)

bbb-download.exe "%URL%"
pause
