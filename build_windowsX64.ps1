<#
.SYNOPSIS
    build_win.ps1 - Đóng gói DK Music Player v1.0 thành file .exe trên Windows bằng PowerShell.
#>

$ErrorActionPreference = "Stop"

$AppName = "DKMusicPlayer"
$EntryPoint = "main.py"
$IconPath = "assets\icon.ico"
$AssetsDir = "assets"
$VersionFile = "VERSION.txt"

Write-Host "==> [1/6] Kiem tra thu muc goc du an..." -ForegroundColor Cyan
if (-not (Test-Path $EntryPoint)) {
    Write-Host "Khong tim thay $EntryPoint. Hay chac chan ban chay script nay tu thu muc goc cua project." -ForegroundColor Red
    exit 1
}

Write-Host "==> [2/6] Quan ly phien ban (Auto-increment Version)..." -ForegroundColor Cyan
if (-not (Test-Path $VersionFile)) {
    "1.0.0" | Out-File -FilePath $VersionFile -Encoding utf8
}

$CurrentVersion = (Get-Content $VersionFile).Trim()
$Parts = $CurrentVersion.Split('.')
$BaseVersion = "$($Parts[0]).$($Parts[1])"
$BuildNum = if ($Parts.Count -ge 3) { [int]$Parts[2] } else { 0 }
$NewBuildNum = $BuildNum + 1
$Version = "$BaseVersion.$NewBuildNum"

$Version | Out-File -FilePath $VersionFile -Encoding utf8
Write-Host "    Version cu: $CurrentVersion" -ForegroundColor Gray
Write-Host "    Version moi: $Version" -ForegroundColor Green

Write-Host "==> [3/6] Kiem tra va cap nhat thu vien can thiet..." -ForegroundColor Cyan
python -m pip install --upgrade pip -q
if (Test-Path "requirements.txt") {
    python -m pip install -r requirements.txt -q
} else {
    python -m pip install PyQt6 PyQt6-Fluent-Widgets pygame mutagen -q
}
python -m pip install pyinstaller -q

Write-Host "==> [4/6] Don dep cac tep build cu..." -ForegroundColor Cyan
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "$AppName.spec") { Remove-Item -Force "$AppName.spec" }

Write-Host "==> [5/6] Build $AppName.exe v1.0 bang PyInstaller..." -ForegroundColor Cyan
pyinstaller `
    --name "$AppName" `
    --onefile `
    --windowed `
    --icon="$IconPath" `
    --add-data "$AssetsDir;$AssetsDir" `
    --hidden-import="PyQt6.QtSvg" `
    --hidden-import="PyQt6.QtNetwork" `
    --hidden-import="pygame" `
    --hidden-import="mutagen" `
    --collect-all="qfluentwidgets" `
    --collect-all="pygame" `
    "$EntryPoint"

Write-Host ""
Write-Host "Build binary hoan tat! File thuc thi nam tai: dist\$AppName.exe" -ForegroundColor Green
Write-Host ""
Write-Host "==> [6/6] Dong goi thanh Setup.exe bang Inno Setup..." -ForegroundColor Cyan

$ProgramFilesX86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
$ISCC = Join-Path $ProgramFilesX86 'Inno Setup 6\ISCC.exe'

if (-not (Test-Path $ISCC)) {
    $ISCC = Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'
}

if (-not (Test-Path $ISCC)) {
    Write-Host ""
    Write-Host "Khong tim thay Inno Setup 6 bang duong dan mac dinh." -ForegroundColor Yellow
    Write-Host "File Portable EXE van co san tai: dist\$AppName.exe" -ForegroundColor Green
    exit 0
}

$PackageId = "dk-music-player"
$Arch = "amd64"
$OutDir = "installer\windows"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

& $ISCC "/DBuildVersion=$Version" build_windowsX64.iss

$SetupFileName = "${PackageId}_${Version}_${Arch}.exe"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "BUILD WINDOWS THANH CONG (DK Music Player v1.0)" -ForegroundColor Green
Write-Host "Portable EXE : dist\$AppName.exe" -ForegroundColor Yellow
Write-Host "Setup EXE    : $OutDir\$SetupFileName" -ForegroundColor Yellow
Write-Host "=============================================" -ForegroundColor Green