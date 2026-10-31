@echo off
if "%~1"=="" (
  echo Usage: Create-APK-Research-Profile.cmd APK_Research_ProjectName
  pause
  exit /b 2
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0APKResearch.ps1" -Action Create -Name "%~1"
pause
