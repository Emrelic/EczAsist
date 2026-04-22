# Eczasist masaüstü + Başlat menüsü kısayolu oluşturur.
# Çalıştır: powershell -ExecutionPolicy Bypass -File scripts\kisayol_olustur.ps1

$ErrorActionPreference = 'Stop'

$proje = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$giris = Join-Path $proje 'main.py'
$ikon  = Join-Path $proje 'assets\eczasist.ico'

$adaylar = @(
    "$env:LOCALAPPDATA\Python\bin\pythonw.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\pythonw.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\pythonw.exe"
)
$pythonw = $adaylar | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $pythonw) {
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notmatch 'WindowsApps' } |
        Select-Object -First 1
    if ($cmd) { $pythonw = $cmd.Source }
}
if (-not $pythonw) { throw "pythonw.exe bulunamadi" }

$ws       = New-Object -ComObject WScript.Shell
$hedefler = @(
    [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('Programs')
)

foreach ($klasor in $hedefler) {
    $lnk = Join-Path $klasor 'Eczasist.lnk'
    $sc = $ws.CreateShortcut($lnk)
    $sc.TargetPath        = $pythonw
    $sc.Arguments         = '"' + $giris + '"'
    $sc.WorkingDirectory  = $proje
    $sc.IconLocation      = $ikon + ',0'
    $sc.Description       = 'Eczasist - Eczane Yonetim Asistani'
    $sc.WindowStyle       = 1
    $sc.Save()
    Write-Host "Olusturuldu: $lnk"
}
