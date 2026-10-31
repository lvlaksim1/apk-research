#Requires -Version 5.1
<#
.SYNOPSIS
  Project-independent Android APK research AVD controller.
.DESCRIPTION
  Supports Android 16 AVD creation/start/stop, generic APK and split-APK
  installation, application launch and diagnostics. Never touches LDPlayer.
  System images are provided by the installed Android SDK.
.EXAMPLE
  .\APKResearch.ps1 -Action Start
  .\APKResearch.ps1 -Action Install -PackageFile "D:\samples\app.apk+"
  .\APKResearch.ps1 -Action Create -Name APK_Research_NewProject
  .\APKResearch.ps1 -Action Start -Name APK_Research_NewProject -Port 5572
#>
[CmdletBinding()]
param(
    [ValidateSet('Create','Start','Stop','Status','Install','Launch')]
    [string]$Action = 'Status',
    [ValidatePattern('^[a-zA-Z][a-zA-Z0-9_]{2,60}$')]
    [string]$Name = 'APK_Research_API36',
    [ValidateRange(5554,5682)]
    [int]$Port = 5570,
    [string]$PackageFile,
    [string]$PackageName,
    [string]$AvdRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (($Port % 2) -ne 0) {
    throw 'The Android emulator console port must be even (for example 5570 or 5572).'
}
if (-not $AvdRoot) {
    if (Test-Path 'D:\') { $AvdRoot = 'D:\AndroidAVD' }
    else { $AvdRoot = Join-Path $env:LOCALAPPDATA 'AndroidAVD' }
}
$sdk = $env:ANDROID_SDK_ROOT
if (-not $sdk) { $sdk = $env:ANDROID_HOME }
if (-not $sdk) { $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
$adb = Join-Path $sdk 'platform-tools\adb.exe'
$emulator = Join-Path $sdk 'emulator\emulator.exe'
$avdManager = Join-Path $sdk 'cmdline-tools\latest\bin\avdmanager.bat'
$serial = 'emulator-' + $Port

foreach ($tool in @($adb, $emulator)) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "Android SDK component not found: $tool" }
}

function Test-DeviceOnline {
    $devices = @(& $adb devices -l)
    return [bool](@($devices | Where-Object {
        $_ -match ('^' + [regex]::Escape($serial) + '\s+device(?:\s|$)')
    }).Count -gt 0)
}

function Assert-AvdIdentity {
    if (-not (Test-DeviceOnline)) {
        throw "AVD $serial is not online. Start $Name first."
    }
    $raw = @(& $adb -s $serial emu avd name 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "Cannot identify $serial : $($raw -join ' ')" }
    $actual = @($raw | ForEach-Object { "$_".Trim() })
    if ($actual -notcontains $Name) {
        throw "Refusing to operate on $serial : expected AVD '$Name', got '$($actual -join ', ')'."
    }
}

function Invoke-Device {
    param([string[]]$Arguments)
    Assert-AvdIdentity
    & $adb -s $serial @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "ADB command failed (exit $LASTEXITCODE)."
    }
}

switch ($Action) {
    'Create' {
        if (-not (Test-Path -LiteralPath $avdManager)) { throw "Missing avdmanager: $avdManager" }
        $avdDir = Join-Path $AvdRoot ($Name + '.avd')
        $ini = Join-Path $env:USERPROFILE ('.android\avd\' + $Name + '.ini')
        if ((Test-Path -LiteralPath $avdDir) -or (Test-Path -LiteralPath $ini)) {
            throw "Profile '$Name' already exists. Refusing to overwrite data."
        }
        $image = Join-Path $sdk 'system-images\android-36\google_apis_playstore\x86_64'
        if (-not (Test-Path -LiteralPath (Join-Path $image 'system.img'))) {
            throw 'Android 16 Google Play image is missing. Install system-images;android-36;google_apis_playstore;x86_64 first.'
        }
        New-Item -ItemType Directory -Force -Path $AvdRoot | Out-Null
        & $avdManager create avd --name $Name --package 'system-images;android-36;google_apis_playstore;x86_64' --tag google_apis_playstore --abi x86_64 --device pixel_6_pro --path $avdDir
        if ($LASTEXITCODE -ne 0) { throw "AVD creation failed (exit $LASTEXITCODE)" }
        $config = Join-Path $avdDir 'config.ini'
        if (-not (Test-Path -LiteralPath $config)) { throw "AVD created but config is missing: $config" }
        $settings = [ordered]@{}
        foreach ($line in [IO.File]::ReadAllLines($config)) {
            if ($line -match '^([^=]+)=(.*)$') { $settings[$Matches[1]] = $Matches[2] }
        }
        $overrides = @{
            'avd.ini.displayname' = 'APK Research - Android 16'
            'hw.cpu.ncore' = '4'
            'hw.ramSize' = '4096'
            'disk.dataPartition.size' = '16G'
            'hw.gpu.enabled' = 'yes'
            'hw.gpu.mode' = 'auto'
            'hw.keyboard' = 'yes'
            'hw.lcd.width' = '1080'
            'hw.lcd.height' = '2400'
            'hw.lcd.density' = '420'
            'PlayStore.enabled' = 'yes'
        }
        foreach ($key in $overrides.Keys) { $settings[$key] = $overrides[$key] }
        $lines = [string[]]@($settings.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" })
        [IO.File]::WriteAllLines($config, $lines, (New-Object System.Text.UTF8Encoding($false)))
        Write-Output "CREATED AVD=$Name DATA=$avdDir"
    }
    'Start' {
        $avds = @(& $emulator -list-avds)
        if ($avds -notcontains $Name) { throw "AVD '$Name' is not registered; use -Action Create first." }
        if (Test-DeviceOnline) {
            Assert-AvdIdentity
            Write-Output "ALREADY RUNNING: $Name ($serial)"
            break
        }
        $proc = Start-Process -FilePath $emulator -WorkingDirectory (Split-Path $emulator) -ArgumentList @(
            '-avd', $Name, '-port', "$Port", '-no-boot-anim', '-gpu', 'auto'
        ) -PassThru
        Write-Output "START REQUESTED: $Name / $serial / PID $($proc.Id)"
        Write-Output 'Run -Action Status to verify boot, or use the Android Emulator window.'
    }
    'Stop' {
        Assert-AvdIdentity
        & $adb -s $serial emu kill
        if ($LASTEXITCODE -ne 0) { throw "Could not stop $Name" }
        Write-Output "STOP REQUESTED: $Name ($serial)"
    }
    'Status' {
        $known = @(& $emulator -list-avds)
        if ($known -notcontains $Name) { throw "AVD '$Name' is not registered." }
        if (-not (Test-DeviceOnline)) {
            Write-Output "AVD=$Name PORT=$Port STATE=not-online DATA=$(Join-Path $AvdRoot ($Name + '.avd'))"
            break
        }
        # ADB can briefly report 'device' while the emulator is being stopped.
        # Treat an empty identity as a transient state, never as a different AVD.
        $rawIdentity = @(& $adb -s $serial emu avd name 2>&1)
        $identity = @($rawIdentity | ForEach-Object { "$_".Trim() } | Where-Object { $_ -and $_ -ne 'OK' })
        if ($LASTEXITCODE -ne 0 -or $identity.Count -eq 0) {
            Write-Output "AVD=$Name SERIAL=$serial STATE=transition"
            break
        }
        Assert-AvdIdentity
        $sdkVersion = (& $adb -s $serial shell getprop ro.build.version.sdk).Trim()
        $android = (& $adb -s $serial shell getprop ro.build.version.release).Trim()
        $abis = (& $adb -s $serial shell getprop ro.product.cpu.abilist).Trim()
        $bridge = (& $adb -s $serial shell getprop ro.dalvik.vm.native.bridge).Trim()
        $boot = (& $adb -s $serial shell getprop sys.boot_completed).Trim()
        Write-Output "AVD=$Name SERIAL=$serial ANDROID=$android API=$sdkVersion BOOT=$boot"
        Write-Output "ABIS=$abis NATIVE_BRIDGE=$bridge"
        Write-Output "DATA=$(Join-Path $AvdRoot ($Name + '.avd'))"
    }
    'Install' {
        if (-not $PackageFile) { throw 'Use -PackageFile <path-to-apk-or-archive>.' }
        $source = (Resolve-Path -LiteralPath $PackageFile -ErrorAction Stop).ProviderPath
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            throw "Not a file: $source"
        }
        Assert-AvdIdentity
        $extension = [IO.Path]::GetExtension($source).ToLowerInvariant()
        $staging = $null
        $files = @()
        try {
            if ($extension -eq '.apk') {
                $files = @($source)
            } elseif ($extension -in @('.apk+', '.apks', '.apkm', '.xapk', '.zip')) {
                Add-Type -AssemblyName System.IO.Compression
                Add-Type -AssemblyName System.IO.Compression.FileSystem
                $archive = [IO.Compression.ZipFile]::OpenRead($source)
                try {
                    $entries = @($archive.Entries | Where-Object {
                        $_.Name -match '\.apk$' -and $_.Length -gt 0
                    } | Sort-Object @{Expression={if ($_.Name -ieq 'base.apk') {0} else {1}}}, FullName)
                    if ($entries.Count -lt 1 -or $entries.Count -gt 100) {
                        throw "Archive contains $($entries.Count) APKs; expected 1..100."
                    }
                    $total = [long]0
                    foreach ($entry in $entries) { $total += $entry.Length }
                    if ($total -gt 4GB) { throw 'Archive APK payload exceeds 4 GiB limit.' }
                    $staging = Join-Path $env:TEMP ('APKResearch-' + [guid]::NewGuid().ToString('N'))
                    New-Item -ItemType Directory -Force -Path $staging | Out-Null
                    $index = 0
                    foreach ($entry in $entries) {
                        $entryFileName = '{0:D3}-{1}' -f $index, [IO.Path]::GetFileName($entry.Name)
                        $destination = Join-Path $staging $entryFileName
                        $inputStream = $entry.Open()
                        try {
                            $outputStream = [IO.File]::Create($destination)
                            try { $inputStream.CopyTo($outputStream) }
                            finally { $outputStream.Dispose() }
                        } finally { $inputStream.Dispose() }
                        $files += $destination
                        $index++
                    }
                } finally { $archive.Dispose() }
                if ($extension -eq '.xapk') {
                    Write-Warning 'XAPK expansion OBB files are not installed; APK splits only.'
                }
                if ($extension -eq '.apks') {
                    Write-Warning 'Bundletool .apks may contain incompatible device variants. A device-filtered set may be needed.'
                }
            } else {
                throw "Unsupported extension '$extension'. Use .apk, .apk+, .xapk, .apkm or .apks."
            }
            Write-Output "INSTALLING $($files.Count) APK(s) on $Name ($serial)"
            if ($files.Count -eq 1) { & $adb -s $serial install -r $files[0] }
            else { & $adb -s $serial install-multiple -r @files }
            if ($LASTEXITCODE -ne 0) { throw "APK installation failed (exit $LASTEXITCODE)" }
            Write-Output 'INSTALL VERIFIED'
        } finally {
            if ($staging -and (Test-Path -LiteralPath $staging)) {
                Remove-Item -LiteralPath $staging -Recurse -Force
            }
        }
    }
    'Launch' {
        if (-not $PackageName -or $PackageName -notmatch '^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$') {
            throw 'Use -PackageName in Android package format, e.g. com.example.app.'
        }
        Invoke-Device -Arguments @('shell','monkey','-p',$PackageName,'-c','android.intent.category.LAUNCHER','1')
        Write-Output "LAUNCH REQUESTED: $PackageName"
    }
}
