@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0APKResearch.ps1" -Action Stop %*
if errorlevel 1 pause
