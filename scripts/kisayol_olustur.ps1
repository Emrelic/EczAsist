# Eczasist masaüstü + Başlat menüsü kısayolu oluşturur.
# Çalıştır: powershell -ExecutionPolicy Bypass -File scripts\kisayol_olustur.ps1

$ErrorActionPreference = 'Stop'

$proje    = 'C:\Users\user\OneDrive\Belgeler\GitHub\EczAsist'
$giris    = Join-Path $proje 'ana_menu.py'
$ikon     = Join-Path $proje 'assets\eczasist.ico'
$pythonw  = 'C:\Users\user\AppData\Local\Programs\Python\Python313\pythonw.exe'

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
