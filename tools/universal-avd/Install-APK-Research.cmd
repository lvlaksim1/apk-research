@echo off
if "%~1"=="" (
  echo Drag a .apk, .apk+, .xapk, .apkm or .apks onto this file.
  pause
  exit /b 2
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0APKResearch.ps1" -Action Install -PackageFile "%~1"
pause
