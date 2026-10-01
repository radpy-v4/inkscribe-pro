# 🖊️ InkScribe Pro (Windows İçin Hibrit El Yazısı Not Aracı)

[English Documentation](README.md)

[![CI & Tests](https://github.com/radpy-v4/inkscribe-pro/actions/workflows/ci.yml/badge.svg)](https://github.com/radpy-v4/inkscribe-pro/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=flat&logo=windows&logoColor=white)](https://microsoft.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![AI Supported](https://img.shields.io/badge/AI-Google%20Gemini%20Vision-4285F4?style=flat&logo=google)](https://ai.google.dev/)

Grafik tabletler (VEIKK, Wacom, XP-Pen, Huion vb.) ve Windows dokunmatik cihazlar için geliştirilmiş; **Windows Ink (Çevrimdışı)** ve **Google Gemini Vision (Hibrit Yapay Zekâ)** motorlarını bir arada kullanan akıllı el yazısı not alma ve dönüştürme uygulaması.

---

## ✨ Öne Çıkan Özellikler

- **🤖 Hibrit El Yazısı Tanıma:**
  - **Offline (Windows Ink):** İnternet olmadan doğrudan Windows'un yerel el yazısı motoruyla 30 milisaniyede (0.03 sn) ışık hızında çevrim.
  - **Online (Gemini Vision AI):** Ultra hızlı ve yüksek kotalı **`gemini-3.5-flash-lite`** (~1.2 sn) ve yedek **`gemini-3-flash-preview`** modelleriyle karmaşık el yazılarını en yüksek doğrulukla çözümleme.
  - **Akıllı Fallback & Kota Koruması:** İnternet kesilirse veya model yanıt vermezse kesintisiz yerel Windows Ink motoruna otomatik düşer.
- **🛡️ Açık Gizlilik Onayı (Privacy Consent):**
  - El yazısı görüntüleri, kullanıcıdan grafik onay diyaloğu (`tkinter.messagebox.askyesno`) alınmadıkça **asla** Google sunucularına gönderilmez; onay verilene kadar uygulama %100 çevrimdışı yerel modda kalır.
- **⌨️ Doğal Kelime Boşluklu Auto-Type:**
  - Dönüştürülen her kelime aktif uygulamanıza (Word, Notion, VS Code vb.) yapıştırılırken kelime sonuna otomatik boşluk eklenir; böylece kelimeler birbirine yapışmaz, doğal daktilo gibi aralıklı yazılır.
- **💬 Canlı 2 Satır Not Önizlemesi & Çakışmasız Toast Bildirimleri:**
  - Dönüştürülen son 2 notu pedin altındaki şık şeritte anlık olarak görüntüler.
  - Defterler arasında geçiş yapıldığında ilgili defterdeki son notları otomatik olarak yükler.
  - Hatalı veya engellenen işlemlerde şık ve çakışmasız geçici uyarı kutuları (toast) gösterir.
- **🖥️ Çift Çalışma Modu & Odak Koruma:**
  - **Yüzen Mini Pad (Floating Pad):** Ekranın köşesinde modern koyu cam temalı, boyutlandırılabilir (DPI duyarlı) ve taşınabilir pratik not alanı. Windows `WS_EX_NOACTIVATE` stili sayesinde arkadaki Word, tarayıcı veya kod editörünün klavye odağını asla çalmaz.
  - **Yarı Saydam Tam Ekran (Canvas Overlay):** Tüm ekran üzerine serbestçe yazıp not alma modu.
- **↶ Akıllı Geri Al (Undo) Mekanizması:**
  - Kalemle tek tıkla basılabilen **`[↶ Geri]`** butonu ve Tam Ekran modunda **`Ctrl + Z`** kısayolu.
  - Karalama veya dikey çizgi jestleri yapıldığında yazınız çöpe gitmez; çizgi lekesi olmadan tertemiz geri çağrılabilir.
  - Hem Canvas görselini hem de yerel Windows Ink vuruşlarını (strokes) eşzamanlı geri yükler.
- **✍️ Akıllı Jestler (Gestures):**
  - **Karalama (Scratch-out):** Yazının üzerini karaladığınızda ped temizlenir (bitişik el yazısıyla karışmaması için yoğunluk korumalıdır).
  - **Dikey Hızlı Çizgi (Enter):** Doğal bir aşağı fiske hareketiyle deftere yeni satır ekler; tuvalde yazı varsa önce dönüştürür, ardından yeni satırı kuyruğa alır (Tepsiden "Otomatik Enter Tuşu" açılarak harici uygulamalara da Enter basılabilir).
- **📚 Çoklu Defter Yönetimi:**
  - `Ders Notları`, `Yapılacaklar`, `Fikirler` gibi farklı sekmeler arasında tek tıkla geçiş ve otomatik dosya kaydı (`.txt`).
- **🛡️ Gizlilik Odaklı Loglama & %0 Boşta CPU:**
  - Özel not metinleri log dosyasına asla düz metin yazılmaz; yalnızca karakter uzunluğu tutulur.
  - `RotatingFileHandler` (512 KB × 2) ile log boyutu sınırlandırılır.
  - Tuval boşken hiçbir arka plan döngüsü çalışmaz, işlemci tüketimi **%0**'dır.

---

## ⌨️ Kısayol Tuşları & Kontroller

| Kısayol / Buton | Çalıştığı Mod | İşlev |
| :--- | :--- | :--- |
| **`F8`** | Global (Her Zaman) | Not pedini göster / gizle (config.json ile özelleştirilebilir) |
| **`F9`** | Global (Her Zaman) | Yüzen Mini Pad ile Tam Ekran modu arasında geçiş yap |
| **`[↶]` Butonu** | Mini Pad & Tam Ekran | Yanlışlıkla silinen veya karalanan çizimi anında geri al |
| **`[Temizle]` Butonu** | Mini Pad & Tam Ekran | Tuvali temizle (Geri alınabilir tampona kaydeder) |
| **`Hızlı Dikey Çizgi`** | Stylus / Kalem Jesti | Deftere yeni satır / Enter ekler (Tuvalde yazı varsa önce dönüştürür) |
| **`Karalama Jesti`** | Stylus / Kalem Jesti | Çizimi silip ekranı temizler (↶ butonuyla geri alınabilir) |
| **`Ctrl + Z`** | Tam Ekran Modu | Son silinen çizimi geri al |
| **`Enter`** | Tam Ekran Modu | Beklemeden çizimi anında metne dönüştür |
| **`Esc`** | Tam Ekran Modu | Çizim pedini gizle |
| **`Shift + Esc`** | Tam Ekran Modu | Uygulamayı tamamen kapat |

> **ℹ️ Mini Pad Modunda Klavye Odağı:**  
> Yüzen Mini Pad, siz çizim yaparken arkadaki uygulamanızın (Word, Notion, VS Code, Tarayıcı vb.) klavye odağını kaybetmemesi ve imlecinizin yerinde kalması için Windows `WS_EX_NOACTIVATE` mimarisiyle çalışır. Bu nedenle klavye basışları (`Esc`, `Enter`, `Ctrl+Z`) arkadaki aktif uygulamanıza gider. Mini Pad'de tüm aksiyonlar doğrudan stylus/kalem ile (ekran üzerindeki `[↶]`, `[Temizle]`, `[✕]` butonları ve el yazısı jestleriyle) yönetilir. Klavye kısayolları doğrudan klavye odağı alan **Tam Ekran** modunda etkindir.

---

## 🚀 Kurulum

### 1. Gereksinimler

- **İşletim Sistemi:** Windows 10 veya Windows 11
- **Python:** 3.10 veya üzeri
- **Grafik Tablet veya Stylus:** VEIKK, Wacom, Huion, XP-Pen veya Windows Dokunmatik/Kalem uyumlu ekranlar.
  > 💡 **Önerilen Tablet Sürücü Ayarları (VEIKK, XP-Pen, Huion, Wacom):**  
  > 1. **Windows Ink:** Sürücü panelinde **"Windows Ink"** (veya **"Windows Mürekkep"**) seçeneğini mutlaka işaretleyin (gecikmesiz ve pürüzsüz yazı altyapısı için gereklidir).  
  > 2. **Ekran Eşleme (Screen Mapping):** **"Tam Ekran (Full Screen / Ekran 1)"** seçilmelidir. *(Çoklu monitör kullanıyorsanız "Tüm Ekranlar" yerine yalnızca not aldığınız monitörü seçin; aksi takdirde yatay harf oranı basıklaşır).*  
  > 3. **Tablet Alanı ve Modu:** Çalışma alanını **"Tam Alan (Full Area)"** ve imleç türünü **"Kalem Modu (Pen / Absolute Mode)"** olarak seçin. *(Varsa "Oranı Koru / Keep Aspect Ratio" seçeneğini açmanız 1:1 doğal çizim hissi sağlar).*
- *(Önerilen)* Windows Türkçe el yazısı dil paketinin kurulu olduğundan emin olun:
  > *Ayarlar > Zaman ve Dil > Dil ve Bölge > Türkçe > Seçenekler > **El Yazısı**.*

### 2. Projeyi Klonlayın

```bash
git clone https://github.com/radpy-v4/inkscribe-pro.git
cd inkscribe-pro
```

### 3. Bağımlılıkları Yükleyin

```bash
pip install -r requirements.txt
```

### 4. Yapılandırma (İsteğe Bağlı Gemini AI)

```bash
copy config.example.json config.json
```

`config.json` dosyasını açıp [Google AI Studio](https://aistudio.google.com/)'dan aldığınız **Gemini API anahtarınızı** ekleyebilirsiniz:

```json
{
    "gemini_api_key": "API_ANAHTARINIZ",
    "gemini_model": "gemini-3.5-flash-lite",
    "model_adaylari": [
        "gemini-3.5-flash-lite",
        "gemini-3-flash-preview"
    ],
    "gemini_timeout": 3.5,
    "ai_modu_aktif": true
}
```

*(Dilerseniz anahtarı `GEMINI_API_KEY` ortam değişkeni olarak da tanımlayabilirsiniz. Anahtar girilmezse sistem 100% çevrimdışı Windows Ink motoruyla çalışır).*

---

## 🏃‍♂️ Çalıştırma

```bash
python app.py
```

*(Arka planda konsolsuz çalıştırmak için `pythonw app.py` kullanabilirsiniz).*

---

## 🧪 Testleri Çalıştırma

Donanımdan bağımsız birim ve mantık testlerini çalıştırmak için:

```bash
python -m unittest tests/test_logic.py
```

---

## 📦 Bağımsız EXE (.exe) Olarak Derleme

```bash
pyinstaller TabletNotAlici.spec
```

Derlenen bağımsız tek parça çalıştırılabilir dosya `dist/TabletNotAlici.exe` altında oluşturulur. Standalone modda çalıştırıldığında ayarlar ve notlar `%APPDATA%\InkScribePro` klasöründe güvenle ve kalıcı olarak saklanır.

---

## 🏗️ Modüler Mimari

Proje, temiz ve sürdürülebilir bir Python modül yapısına sahiptir:

```text
TABLET_ELYAZİ/
├── src/
│   ├── __init__.py      # Paket tanımı & public API dışa aktarımları
│   ├── config.py        # ConfigManager, kalıcı ayarlar ve Windows başlangıç kaydı
│   ├── engine.py        # RecognitionEngine: Windows Ink (Offline) & Gemini Vision (Online)
│   ├── gestures.py      # Saf Karalama (Scratch-out) ve Dikey Çizgi (Enter) algoritmaları
│   ├── storage.py       # NotebookManager, çoklu defterler ve metin biçimlendirme
│   ├── tray.py          # TrayManager: Sistem tepsisi menüsü ve masaüstü bildirimleri
│   └── ui.py            # ArkaPlanNotDonusturucu: Çift modlu arayüz, çizim tuvali ve iş akışı
├── app.py               # Hafif ana giriş noktası
├── tests/
│   └── test_logic.py    # Donanımdan bağımsız birim test paketi (28 test)
├── TabletNotAlici.spec  # PyInstaller derleme spesifikasyonu
└── config.json          # Kullanıcı yapılandırması
```

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında lisanslanmıştır.
