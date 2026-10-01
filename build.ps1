# InkScribe Pro - PowerShell Derleme Scripti
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  InkScribe Pro - Otomatik Derleme Scripti (PowerShell)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Python ve Sanal Ortam Tespiti
$pythonCmd = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "[i] .venv sanal ortamı tespit edildi ve kullanılıyor." -ForegroundColor DarkCyan
    $pythonCmd = ".venv\Scripts\python.exe"
}

try {
    & $pythonCmd --version
} catch {
    Write-Error "[X] Python bulunamadı! Lütfen Python'ın kurulu olduğundan emin olun."
    exit 1
}

# 2. Birim Testleri Çalıştır
Write-Host "`n[1/4] Birim testleri çalıştırılıyor..." -ForegroundColor Yellow
& $pythonCmd -m unittest tests/test_logic.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "[X] Testler başarısız oldu! Derleme durduruldu."
    exit 1
}
Write-Host "[✓] Tüm testler başarıyla geçti." -ForegroundColor Green

# 3. PyInstaller Kontrolü
Write-Host "`n[2/4] PyInstaller kontrol ediliyor..." -ForegroundColor Yellow
& $pythonCmd -m pip show pyinstaller 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[i] PyInstaller kuruluyor..." -ForegroundColor DarkYellow
    & $pythonCmd -m pip install pyinstaller
}

# 4. Temizlik
Write-Host "`n[3/4] Eski build klasörü temizleniyor..." -ForegroundColor Yellow
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}

# 5. Derleme
Write-Host "`n[4/4] TabletNotAlici.exe derleniyor (TabletNotAlici.spec)..." -ForegroundColor Yellow
& $pythonCmd -m PyInstaller --noconfirm --clean TabletNotAlici.spec

if ($LASTEXITCODE -ne 0) {
    Write-Error "[X] Derleme sırasında hata meydana geldi!"
    exit 1
}

$exePath = "dist\TabletNotAlici.exe"
if (Test-Path $exePath) {
    $sizeMB = [math]::Round((Get-Item $exePath).Length / 1MB, 2)
    Write-Host "`n========================================================" -ForegroundColor Green
    Write-Host "[✓] DERLEME BAŞARILI!" -ForegroundColor Green
    Write-Host "[✓] Çalıştırılabilir Dosya: $exePath" -ForegroundColor Green
    Write-Host "[✓] Dosya Boyutu: $sizeMB MB" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
} else {
    Write-Error "[X] Beklenen çıktı ($exePath) oluşturulamadı!"
}
