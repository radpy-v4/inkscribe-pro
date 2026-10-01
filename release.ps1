# InkScribe Pro - Otomatik Release (Sürüm Paketleme & Yayınlama) Scripti
[CmdletBinding()]
param (
    [string]$Version = "v1.0.0"
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   InkScribe Pro - Otomatik Release Paketi Hazırlayıcı   " -ForegroundColor Cyan
Write-Host "   Hedef Sürüm: $Version                                  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Python Tespiti
$pythonCmd = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    $pythonCmd = ".venv\Scripts\python.exe"
}

# 2. Birim Testleri Çalıştır
Write-Host "[1/5] Birim testleri çalıştırılıyor..." -ForegroundColor Yellow
& $pythonCmd -m unittest tests/test_logic.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "[X] HATA: Testler başarısız oldu! Release durduruldu."
    exit 1
}
Write-Host "[✓] Tüm testler başarıyla geçti." -ForegroundColor Green

# 3. EXE Derleme (Yoksa veya güncellenecekse)
Write-Host "`n[2/5] TabletNotAlici.exe derleniyor..." -ForegroundColor Yellow
& $pythonCmd -m PyInstaller --noconfirm --clean TabletNotAlici.spec
if ($LASTEXITCODE -ne 0) {
    Write-Error "[X] HATA: PyInstaller derlemesi başarısız!"
    exit 1
}

$exePath = "dist\TabletNotAlici.exe"
if (-not (Test-Path $exePath)) {
    Write-Error "[X] HATA: $exePath bulunamadı!"
    exit 1
}
Write-Host "[✓] EXE başarıyla oluşturuldu." -ForegroundColor Green

# 4. Release Paketini (.zip) Hazırla
Write-Host "`n[3/5] Sürüm dağıtım paketi (ZIP) hazırlanıyor..." -ForegroundColor Yellow
$tempPackageDir = "dist\InkScribe-Pro-$Version-windows-x64"
$zipPath = "dist\InkScribe-Pro-$Version-windows-x64.zip"

if (Test-Path $tempPackageDir) { Remove-Item -Recurse -Force $tempPackageDir }
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

New-Item -ItemType Directory -Path $tempPackageDir | Out-Null
Copy-Item "dist\TabletNotAlici.exe" -Destination $tempPackageDir\
Copy-Item "config.example.json" -Destination $tempPackageDir\
Copy-Item "README_TR.md" -Destination $tempPackageDir\
Copy-Item "README.md" -Destination $tempPackageDir\
Copy-Item "LICENSE" -Destination $tempPackageDir\

Compress-Archive -Path "$tempPackageDir\*" -DestinationPath $zipPath -Force
Remove-Item -Recurse -Force $tempPackageDir
Write-Host "[✓] ZIP Paketi oluşturuldu: $zipPath" -ForegroundColor Green

# 5. SHA256 Checksum Hesabı
Write-Host "`n[4/5] SHA256 sağlama toplamı hesaplanıyor..." -ForegroundColor Yellow
$exeHash = (Get-FileHash -Path $exePath -Algorithm SHA256).Hash
$zipHash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash

$sha256Content = @"
# InkScribe Pro $Version - SHA256 Checksums
$exeHash *TabletNotAlici.exe
$zipHash *InkScribe-Pro-$Version-windows-x64.zip
"@

$sha256File = "dist\SHA256SUMS.txt"
Set-Content -Path $sha256File -Value $sha256Content -Encoding UTF8
Write-Host "[✓] SHA256 Özeti: $sha256File" -ForegroundColor Green

# 6. GitHub Release / Git Tagging
Write-Host "`n[5/5] GitHub Release Kontrolü..." -ForegroundColor Yellow
$hasGh = (Get-Command gh -ErrorAction SilentlyContinue)

if ($hasGh) {
    Write-Host "[i] GitHub CLI (gh) tespit edildi." -ForegroundColor Cyan
    $publish = Read-Host "Bu sürümü ($Version) doğrudan GitHub Releases'e yayınlamak ister misiniz? (E/H)"
    if ($publish -eq "E" -or $publish -eq "e") {
        Write-Host "[i] GitHub Release oluşturuluyor..." -ForegroundColor Yellow
        & gh release create $Version $exePath $zipPath $sha256File --title "InkScribe Pro $Version" --notes "InkScribe Pro $Version Windows x64 Sürümü. Taşınabilir (portable) ve tek parça çalıştırılabilir dosya."
        if ($LASTEXITCODE -eq 0) {
            Write-Host "`n[✓] TEBRİKLER! GitHub Release başarıyla yayınlandı!" -ForegroundColor Green
        }
    }
} else {
    Write-Host "[i] GitHub CLI bulunamadı. Git tag ile yayınlamak için şu komutları kullanabilirsiniz:" -ForegroundColor Cyan
    Write-Host "    git tag -a $Version -m 'Release $Version'" -ForegroundColor White
    Write-Host "    git push origin $Version" -ForegroundColor White
    Write-Host "    (Tag push edildiğinde GitHub Actions otomatik olarak Release açacaktır)." -ForegroundColor DarkGray
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  RELEASE DOSYALARI HAZIR: dist/ klasörü altında  " -ForegroundColor Green
Write-Host "  1. $exePath" -ForegroundColor Green
Write-Host "  2. $zipPath" -ForegroundColor Green
Write-Host "  3. $sha256File" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
