$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace([Environment]::GetFolderPath('Desktop'))
$item = $folder.ParseName('Recete Kontrol.lnk')
if ($item) {
    Write-Host "Kisayol bulundu"
    $verbs = $item.Verbs()
    foreach ($verb in $verbs) {
        Write-Host "Verb: $($verb.Name)"
        if ($verb.Name -match 'sabitle|pin to task|Taskbar') {
            $verb.DoIt()
            Write-Host "Gorev cubuguna sabitlendi!"
        }
    }
} else {
    Write-Host "Kisayol bulunamadi"
}
