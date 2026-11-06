@echo off
chcp 65001 >nul
title Mehrad Kavir AI - One Click Install
cd /d "%~dp0"
where docker >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop is required. Install Docker Desktop and launch it.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
if errorlevel 1 (
  echo Installation failed. See details above.
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8787"
echo.
echo Mehrad Kavir AI: http://127.0.0.1:8787
echo Your initial login is in .local-credentials.txt
pause
