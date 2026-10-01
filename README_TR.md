# 🖊️ Tablet Not Alıcı (Windows İçin Hibrit El Yazısı Not Aracı)

[English Documentation](README.md)

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=flat&logo=windows&logoColor=white)](https://microsoft.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![AI Supported](https://img.shields.io/badge/AI-Google%20Gemini%20Vision-4285F4?style=flat&logo=google)](https://ai.google.dev/)

Grafik tabletler (VEIKK, Wacom, XP-Pen, Huion vb.) ve Windows dokunmatik cihazlar için geliştirilmiş; **Windows Ink (Çevrimdışı)** ve **Google Gemini Vision (Hibrit Yapay Zekâ)** motorlarını bir arada kullanan akıllı el yazısı not alma ve dönüştürme uygulaması.

---

## ✨ Öne Çıkan Özellikler

- **🤖 Hibrit El Yazısı Tanıma:**
  - **Offline (Windows Ink):** İnternet olmadan doğrudan Windows'un yerel el yazısı motoruyla hızlı ve kesintisiz çevrim.
  - **Online (Gemini Vision AI):** Güncel `gemini-2.5-flash` ve `gemini-3.5-flash` modelleriyle karmaşık el yazılarını en yüksek doğrulukla çözümleme.
  - **Işık Hızında OCR & Akıllı Fallback:** Modelin düşünme süresi sıfırlanarak (`thinkingBudget: 0`) 0.3 saniyede yanıt alınır. Model kapanması veya 404 durumunda otomatik olarak sıradaki yedek modele geçer; internet yoksa kesintisiz yerel Windows Ink motoruna düşer.
- **💬 Canlı 2 Satır Not Önizlemesi & Çakışmasız Toast Bildirimleri:**
  - Dönüştürülen son 2 notu pedin altındaki şık şeritte anlık olarak görüntüler.
  - Defterler arasında geçiş yapıldığında ilgili defterdeki son notları otomatik olarak yükler.
  - Hatalı veya engellenen işlemlerde şık ve çakışmasız geçici uyarı kutuları (toast) gösterir.
- **🖥️ Çift Çalışma Modu & Odak Koruma:**
  - **Yüzen Mini Pad (Floating Pad):** Ekranın köşesinde modern koyu cam temalı, boyutlandırılabilir (min. 680 px) ve taşınabilir pratik not alanı. Windows `WS_EX_NOACTIVATE` stili sayesinde arkadaki Word, tarayıcı veya kod editörünün klavye odağını asla çalmaz.
  - **Yarı Saydam Tam Ekran (Canvas Overlay):** Tüm ekran üzerine serbestçe yazıp not alma modu.
- **↶ Akıllı Geri Al (Undo) Mekanizması:**
  - Kalemle tek tıkla basılabilen **`[↶ Geri]`** butonu ve **`Ctrl + Z`** kısayolu.
  - Karalama veya dikey çizgi jestleri yapıldığında yazınız çöpe gitmez; çizgi lekesi olmadan tertemiz geri çağrılabilir.
  - Hem Canvas görselini hem de yerel Windows Ink vuruşlarını (strokes) eşzamanlı geri yükler.
- **✍️ Akıllı Jestler (Gestures):**
  - **Karalama (Scratch-out):** Yazının üzerini karaladığınızda ped temizlenir (bitişik el yazısıyla karışmaması için yoğunluk korumalıdır).
  - **Dikey Hızlı Çizgi (Enter):** Doğal bir aşağı kaydırma hareketiyle yeni satır ekler; dönüşüm sürüyorsa satırı sıraya alıp doğru konuma ekler.
- **📚 Çoklu Defter Yönetimi:**
  - `Ders Notları`, `Yapılacaklar`, `Fikirler` gibi farklı sekmeler arasında tek tıkla geçiş ve otomatik dosya kaydı (`.txt`).
- **🛡️ Gizlilik Odaklı Loglama & %0 Boşta CPU:**
  - Özel not metinleri log dosyasına asla düz metin yazılmaz; yalnızca karakter uzunluğu tutulur.
  - `RotatingFileHandler` (512 KB × 2) ile log boyutu sınırlandırılır.
  - Tuval boşken hiçbir arka plan döngüsü çalışmaz, işlemci tüketimi **%0**'dır.

---

## ⌨️ Kısayol Tuşları & Kontroller

| Kısayol / Buton | İşlev |
| :--- | :--- |
| **`F8`** | Not pedini göster / gizle (Global Kısayol) |
| **`F9`** | Yüzen Mini Pad ile Tam Ekran modu arasında geçiş yap |
| **`[↶ Geri]` / `Ctrl + Z`** | Yanlışlıkla silinen veya karalanan çizimi geri al |
| **`Enter`** | Beklemeden çizimi anında metne dönüştür |
| **`Esc`** | Çizim pedini gizle |
| **`Shift + Esc`** | Uygulamayı tamamen kapat |

---

## 🚀 Kurulum

### 1. Gereksinimler
- **İşletim Sistemi:** Windows 10 veya Windows 11
- **Python:** 3.10 veya üzeri
- **Grafik Tablet veya Stylus:** VEIKK, Wacom, Huion, XP-Pen veya Windows Dokunmatik/Kalem uyumlu ekranlar.
- *(Önerilen)* Windows Türkçe el yazısı dil paketinin kurulu olduğundan emin olun:
  > *Ayarlar > Zaman ve Dil > Dil ve Bölge > Türkçe > Seçenekler > **El Yazısı**.*

### 2. Projeyi Klonlayın
```bash
git clone https://github.com/KULLANICI_ADINIZ/tablet-not-alici.git
cd tablet-not-alici
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
    "gemini_model": "gemini-2.5-flash",
    "ai_modu_aktif": true
}
```
*(Dilerseniz anahtarı `GEMINI_API_KEY` ortam değişkeni olarak da tanımlayabilirsiniz. Anahtar girilmezse sistem 100% çevrimdışı Windows Ink motoruyla çalışır).*

---

## 🏃‍♂️ Çalıştırma

```bash
python hand_to_text.py
```
*(Arka planda konsolsuz çalıştırmak için `pythonw hand_to_text.py` kullanabilirsiniz).*

---

## 🧪 Testleri Çalıştırma

Donanımdan bağımsız birim ve mantık testlerini çalıştırmak için:
```bash
pytest tests/test_logic.py -v
```

---

## 📦 Bağımsız EXE (.exe) Olarak Derleme

```bash
pyinstaller TabletNotAlici.spec
```
Derlenen çalıştırılabilir dosya `dist/TabletNotAlici.exe` altında oluşturulur.

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında lisanslanmıştır.
