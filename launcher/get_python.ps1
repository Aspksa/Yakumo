# Скачивает встроенный Python для Yakumo в папку python рядом с программой.
# Вызывается из Yakumo.bat. Файл сохранён в UTF-8 с BOM, иначе
# Windows PowerShell 5.1 прочитает русский текст в неверной кодировке.
param([Parameter(Mandatory = $true)][string]$Root)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'  # без этого загрузка в PowerShell 5.1 очень медленная
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Version = '3.12.10'
$Arch = 'win32'
if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') { $Arch = 'arm64' }
elseif ([Environment]::Is64BitOperatingSystem) { $Arch = 'amd64' }

$Dest = Join-Path $Root 'python'
$Zip = Join-Path $env:TEMP "yakumo-python-$Version-$Arch.zip"
$Url = "https://www.python.org/ftp/python/$Version/python-$Version-embed-$Arch.zip"

try {
    Write-Host "Скачиваю Python $Version ($Arch)..."
    Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing
    if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
    Expand-Archive -Path $Zip -DestinationPath $Dest -Force
    Remove-Item $Zip -Force -ErrorAction SilentlyContinue

    # Встроенный Python берёт пути только из ._pth: добавляем site-packages
    # и папку программы (..), чтобы работал "python -m yakumo".
    $Pth = Get-ChildItem -Path $Dest -Filter 'python*._pth' | Select-Object -First 1
    $ZipLine = Get-Content $Pth.FullName | Where-Object { $_ -like '*.zip' } | Select-Object -First 1
    Set-Content -Path $Pth.FullName -Encoding Ascii -Value @($ZipLine, '.', 'Lib\site-packages', '..', 'import site')
    Write-Host 'Python готов.'
}
catch {
    Write-Host "Ошибка: $($_.Exception.Message)"
    exit 1
}

# Необязательно: библиотеки для значка в трее. Без них Yakumo работает в консоли.
try {
    Write-Host 'Ставлю библиотеки для значка в трее (pystray, Pillow)...'
    $Python = Join-Path $Dest 'python.exe'
    $GetPip = Join-Path $env:TEMP 'yakumo-get-pip.py'
    Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile $GetPip -UseBasicParsing
    & $Python $GetPip --no-warn-script-location --disable-pip-version-check | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'get-pip завершился с ошибкой' }
    & $Python -m pip install --no-warn-script-location --disable-pip-version-check -r (Join-Path $Root 'requirements.txt') | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'pip install завершился с ошибкой' }
    Remove-Item $GetPip -Force -ErrorAction SilentlyContinue
    Write-Host 'Готово.'
}
catch {
    Write-Host "Значок в трее не установлен ($($_.Exception.Message)). Yakumo будет работать без него."
}
exit 0
