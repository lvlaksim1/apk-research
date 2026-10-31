#Requires -Version 5.1
<#
.SYNOPSIS
  Install reusable APK Research emulator helpers for the current Windows user.
  Does not modify LDPlayer, AVDs or their settings.
#>
[CmdletBinding()]
param(
    [string]$InstallRoot,
    [switch]$NoShortcuts
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $InstallRoot) {
    if (Test-Path 'D:\') { $InstallRoot = 'D:\Tools\APKResearch' }
    else { $InstallRoot = Join-Path $env:LOCALAPPDATA 'APKResearch\Tools' }
}
$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$files = @(
    'APKResearch.ps1',
    'Start-APK-Research.cmd',
    'Stop-APK-Research.cmd',
    'Status-APK-Research.cmd',
    'Install-APK-Research.cmd',
    'Create-APK-Research-Profile.cmd',
    'Enable-Android-VPN.cmd',
    'Disable-Android-VPN.cmd',
    'Status-Android-VPN.cmd'
)
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
foreach ($file in $files) {
    $from = Join-Path $source $file
    if (-not (Test-Path -LiteralPath $from)) { throw "Missing source file: $from" }
    $to = Join-Path $InstallRoot $file
    if (([IO.Path]::GetFullPath($from)) -ine ([IO.Path]::GetFullPath($to))) {
        Copy-Item -LiteralPath $from -Destination $to -Force
    }
}
if (-not $NoShortcuts) {
    $menu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\APK Research Emulator'
    New-Item -ItemType Directory -Path $menu -Force | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    $links = [ordered]@{
        'Запустить эмулятор.lnk' = 'Start-APK-Research.cmd'
        'Остановить эмулятор.lnk' = 'Stop-APK-Research.cmd'
        'Состояние эмулятора.lnk' = 'Status-APK-Research.cmd'
        'Включить VPN в Android.lnk' = 'Enable-Android-VPN.cmd'
        'Отключить VPN в Android.lnk' = 'Disable-Android-VPN.cmd'
        'Проверить VPN Android.lnk' = 'Status-Android-VPN.cmd'
    }
    foreach ($displayName in $links.Keys) {
        $shortcut = $shell.CreateShortcut((Join-Path $menu $displayName))
        $shortcut.TargetPath = Join-Path $InstallRoot $links[$displayName]
        $shortcut.WorkingDirectory = $InstallRoot
        $shortcut.Description = 'APK Research - independent Android 16 emulator'
        $shortcut.Save()
    }
}
Write-Output "TOOLS INSTALLED: $InstallRoot"
Write-Output 'Use Start-APK-Research.cmd or APKResearch.ps1 -Action Start'
