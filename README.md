# 🖊️ InkScribe Pro (TabletNote AI)

> **Fast, hybrid handwriting-to-text note-taking app for graphics tablets and touch screens on Windows.**  
> Powered by **Windows Ink (Offline)** and **Google Gemini Vision (Online AI)**.

[🇹🇷 Türkçe Dokümantasyon](README_TR.md)

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=flat&logo=windows&logoColor=white)](https://microsoft.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![AI Supported](https://img.shields.io/badge/AI-Google%20Gemini%20Vision-4285F4?style=flat&logo=google)](https://ai.google.dev/)

---

## 🌟 Highlights

- **⚡ Hybrid Recognition Engine:**
  - **Offline (Windows Ink):** Ultra-fast, zero-latency local handwriting recognition powered by native Windows Ink APIs. No internet connection required.
  - **Online (Google Gemini Vision AI):** High-accuracy cloud AI recognition for cursive, complex handwriting, or shorthand. Automatically falls back to offline mode when offline.
- **🖥️ Dual Display Modes:**
  - **Floating Mini Pad:** Sleek dark-glass PIP (picture-in-picture) notepad that floats on top of your apps. Fully movable and resizable.
  - **Transparent Full-Screen Overlay:** Annotate and take notes directly over your entire screen.
- **✍️ Intuitive In-Pad Gestures:**
  - **Scratch-out:** Scribble over your drawing to instantly wipe the canvas clean.
  - **Vertical Stroke:** A quick downward stroke creates a newline immediately.
- **📚 Multi-Notebook Management:**
  - Switch seamlessly between designated notebooks (e.g. *Lecture Notes*, *To-Do List*, *Ideas*) with automatic `.txt` file persistence.
- **🛎️ System Tray & Background Worker:**
  - Runs quietly in the notification area. Includes Windows startup autostart integration.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Description |
| :--- | :--- |
| **`F8`** | Toggle Note Pad display (Global Hotkey) |
| **`F9`** | Switch between Floating Mini Pad and Full-Screen Mode |
| **`Enter`** | Convert drawing to text immediately |
| **`Esc`** | Hide drawing pad |
| **`Shift + Esc`** | Exit application completely |

---

## 🚀 Quick Start

### 1. Prerequisites
- **OS:** Windows 10 or Windows 11
- **Python:** 3.10 or higher
- **Graphics Tablet or Stylus:** Wacom, VEIKK, XP-Pen, Huion, or any Windows Pen/Touch compatible device.
- *(Recommended)* Ensure your language handwriting pack is installed in Windows:
  > *Settings > Time & Language > Language & Region > Preferred Language > Options > **Handwriting**.*

### 2. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/inkscribe-pro.git
cd inkscribe-pro
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configuration (Optional Gemini Vision AI)
Copy the template configuration file:
```cmd
copy config.example.json config.json
```
Open `config.json` and insert your [Google AI Studio](https://aistudio.google.com/) Gemini API key:
```json
{
    "gemini_api_key": "YOUR_GEMINI_API_KEY",
    "ai_modu_aktif": true
}
```
*(You can also set the `GEMINI_API_KEY` environment variable. If left empty, the application runs entirely in offline mode using Windows Ink).*

---

## 🏃 Run Application

```bash
python hand_to_text.py
```
Press **`F8`** anywhere in Windows to bring up the notepad and start writing with your pen!

---

## 📦 Build Standalone Executable (.exe)

You can package the application into a standalone Windows binary using PyInstaller:

```bash
pyinstaller TabletNotAlici.spec
```
The compiled executable will be located in `dist/TabletNotAlici.exe`.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!  
Feel free to check out the [issues page](https://github.com/YOUR_USERNAME/inkscribe-pro/issues).

---

## 📄 License

This project is open-source and licensed under the [MIT License](LICENSE).
# inkscribe-pro
