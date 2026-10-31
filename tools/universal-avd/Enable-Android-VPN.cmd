@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0APKResearch.ps1" -Action ProxyOn %*
if errorlevel 1 pause
