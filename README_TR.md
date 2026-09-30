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
  - **Online (Gemini Vision AI):** İnternet ve API anahtarı mevcutken karmaşık el yazılarını en yüksek doğrulukla çözümleme.
  - **Evrensel Anahtar & Kesintisiz Geçiş:** Hem Google AI Studio (`AIzaSy...`) hem de Google Cloud (`AQ....`) anahtarlarını destekler. Ağ gecikmesi veya sunucu yoğunluğu (HTTP 503) olduğunda anında çevrimdışı Windows Ink motoruna düşerek asla takılmaz.
- **💬 Canlı 2 Satır Not Önizlemesi:**
  - Dönüştürülen son 2 notu pedin altındaki şık şeritte anlık olarak görüntüler.
  - Defterler arasında geçiş yapıldığında ilgili defterdeki son notları otomatik olarak yükler.
- **🖥️ Çift Çalışma Modu:**
  - **Yüzen Mini Pad (Floating Pad):** Ekranın köşesinde modern koyu cam temalı, boyutlandırılabilir ve taşınabilir pratik not alanı.
  - **Yarı Saydam Tam Ekran (Canvas Overlay):** Tüm ekran üzerine serbestçe yazıp not alma modu.
- **✍️ Akıllı Jestler (Gestures):**
  - **Karalama:** Yazının üzerini karaladığınızda ped otomatik olarak temizlenir.
  - **Dikey Hızlı Çizgi:** Doğal bir el hareketiyle doğrudan yeni satır ekler.
- **📚 Çoklu Defter Yönetimi:**
  - `Ders Notları`, `Yapılacaklar`, `Fikirler` gibi farklı sekmeler arasında tek tıkla geçiş ve otomatik dosya kaydı (`.txt`).
- **🛎️ Sistem Tepsisi (Tray Icon) ve Arka Plan:**
  - Görev çubuğunda simge durumu, Windows açılışında otomatik başlama desteği ve sessiz arka plan çalışma modu.

---

## ⌨️ Kısayol Tuşları

| Kısayol | İşlev |
| :--- | :--- |
| **`F8`** | Not pedini göster / gizle (Global Kısayol) |
| **`F9`** | Yüzen Mini Pad ile Tam Ekran modu arasında geçiş yap |
| **`Enter`** | Beklemeden çizimi anında metne dönüştür |
| **`Esc`** | Çizim pedini gizle |
| **`Shift + Esc`** | Uygulamayı tamamen kapat |

---

## 🚀 Kurulum

### 1. Gereksinimler
- **İşletim Sistemi:** Windows 10 veya Windows 11
- **Python:** 3.10 veya üzeri

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
`config.json` dosyasını açıp Google AI Studio'dan aldığınız **Gemini API anahtarınızı** ekleyebilirsiniz.

---

## 🏃‍♂️ Çalıştırma

```bash
python hand_to_text.py
```

---

## 📦 Bağımsız EXE (.exe) Olarak Derleme

```bash
pyinstaller TabletNotAlici.spec
```

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında lisanslanmıştır.
