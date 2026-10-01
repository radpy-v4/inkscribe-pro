# InkScribe Pro - PowerShell Derleme Scripti
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  InkScribe Pro - Otomatik Derleme Scripti (PowerShell)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Python ve Sanal Ortam Tespiti
$pythonCmd = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "[i] .venv sanal ortami tespit edildi ve kullaniliyor." -ForegroundColor DarkCyan
    $pythonCmd = ".venv\Scripts\python.exe"
}

try {
    & $pythonCmd --version
} catch {
    Write-Error "[X] Python bulunamadi! Lutfen Python'in kurulu oldugundan emin olun."
    exit 1
}

# 2. Birim Testleri Calistir
Write-Host "`n[1/4] Birim testleri calistiriliyor..." -ForegroundColor Yellow
& $pythonCmd -m unittest tests/test_logic.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "[X] Testler basarisiz oldu! Derleme durduruldu."
    exit 1
}
Write-Host "[OK] Tum testler basariyla gecti." -ForegroundColor Green

# 3. PyInstaller Kontrolu
Write-Host "`n[2/4] PyInstaller kontrol ediliyor..." -ForegroundColor Yellow
& $pythonCmd -m pip show pyinstaller 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[i] PyInstaller kuruluyor..." -ForegroundColor DarkYellow
    & $pythonCmd -m pip install pyinstaller
}

# 4. Temizlik
Write-Host "`n[3/4] Eski build klasoru temizleniyor..." -ForegroundColor Yellow
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}

# 5. Derleme
Write-Host "`n[4/4] TabletNotAlici.exe derleniyor (TabletNotAlici.spec)..." -ForegroundColor Yellow
& $pythonCmd -m PyInstaller --noconfirm --clean TabletNotAlici.spec

if ($LASTEXITCODE -ne 0) {
    Write-Error "[X] Derleme sirasinda hata meydana geldi!"
    exit 1
}

$exePath = "dist\TabletNotAlici.exe"
if (Test-Path $exePath) {
    $sizeMB = [math]::Round((Get-Item $exePath).Length / 1MB, 2)
    Write-Host "`n========================================================" -ForegroundColor Green
    Write-Host "[OK] DERLEME BASARILI!" -ForegroundColor Green
    Write-Host "[OK] Calistirilabilir Dosya: $exePath" -ForegroundColor Green
    Write-Host "[OK] Dosya Boyutu: $sizeMB MB" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
} else {
    Write-Error "[X] Beklenen cikti ($exePath) olusturulamadi!"
}
