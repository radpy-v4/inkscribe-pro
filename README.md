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
  - **Online (Google Gemini Vision AI):** High-accuracy cloud AI recognition for cursive, complex handwriting, or shorthand using `gemini-2.5-flash` and `gemini-3.5-flash`.
  - **Instant OCR & Resilient Model Fallback:** Optimized with `thinkingBudget: 0` for lightning-fast ~0.3s response times. Automatically fails over to the next candidate model if a model is deprecated (HTTP 404), or drops seamlessly to offline Windows Ink.
- **💬 Live 2-Line Note Preview & Floating Toast Notifications:**
  - Displays the last 2 recognized notes directly on the pad's footer in real-time.
  - Automatically loads and displays the latest notes whenever you switch between notebooks.
  - Displays non-intrusive, temporary toast alerts (e.g., when undo is blocked) with distinct background shading.
- **🖥️ Dual Display Modes with Non-Activating Focus:**
  - **Floating Mini Pad:** Sleek dark-glass PIP (picture-in-picture) notepad that floats on top of your apps. Movable and resizable (min 680 px width). Equipped with Win32 `WS_EX_NOACTIVATE` so it never steals keyboard focus from Word, your browser, or code editor.
  - **Transparent Full-Screen Overlay:** Annotate and take notes directly over your entire screen.
- **↶ Smart Undo Buffer:**
  - Stylus-friendly **`[↶ Geri]`** top bar button and **`Ctrl + Z`** keyboard shortcut.
  - Protects against accidental scratch-outs or clears without contaminating the restored canvas with scribble lines.
  - Simultaneously reconstructs both the PIL image and native Windows Ink stroke containers.
- **✍️ Intuitive In-Pad Gestures:**
  - **Scratch-out:** Scribble over your drawing to instantly wipe the canvas clean (protected by oscillation density checks against cursive words).
  - **Vertical Stroke:** A quick downward stroke creates a newline immediately (asynchronously queued if an active conversion is in progress).
- **📚 Multi-Notebook Management:**
  - Switch seamlessly between designated notebooks (e.g. *Lecture Notes*, *To-Do List*, *Ideas*) with automatic `.txt` file persistence.
- **🛡️ Privacy-First Logging & 0% Idle CPU:**
  - Handwritten notes are never logged as plaintext; only length and status are saved.
  - Built-in `RotatingFileHandler` (512 KB × 2 backups) caps disk space.
  - Zero idle CPU footprint when nothing is drawn on the canvas.

---

## ⌨️ Controls & Shortcuts

| Shortcut / Button | Description |
| :--- | :--- |
| **`F8`** | Toggle Note Pad display (Global Hotkey) |
| **`F9`** | Switch between Floating Mini Pad and Full-Screen Mode |
| **`[↶ Geri]` / `Ctrl + Z`** | Undo last cleared or scratched-out drawing |
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
    "gemini_model": "gemini-2.5-flash",
    "ai_modu_aktif": true
}
```
*(You can also set the `GEMINI_API_KEY` environment variable. If left empty, the application runs entirely in offline mode using Windows Ink).*

---

## 🏃 Run Application

```bash
python hand_to_text.py
```
*(For headless background execution without a console window, run `pythonw hand_to_text.py`).*

Press **`F8`** anywhere in Windows to bring up the notepad and start writing with your pen!

---

## 🧪 Running Unit Tests

Run the hardware-independent logic and algorithm test suite:
```bash
pytest tests/test_logic.py -v
```

---

## 📦 Build Standalone Executable (.exe)

You can package the application into a standalone Windows binary using PyInstaller:

```bash
pyinstaller TabletNotAlici.spec
```
The compiled executable will be located in `dist/TabletNotAlici.exe`.

---

## 🏗️ Modular Architecture

The codebase is organized into clean, single-responsibility modules:

```text
TABLET_ELYAZİ/
├── src/
│   ├── __init__.py      # Package indicator
│   ├── config.py        # ConfigManager, persistent settings & Windows startup registry
│   ├── engine.py        # RecognitionEngine: Windows Ink (Offline) & Gemini Vision (Online)
│   ├── gestures.py      # Pure Scratch-out & Vertical Stroke (Enter) algorithms
│   ├── storage.py       # NotebookManager, multi-notebooks & text formatting
│   ├── tray.py          # TrayManager: System tray icon & desktop notifications
│   └── ui.py            # ArkaPlanNotDonusturucu: Dual-mode UI, drawing canvas & workflow
├── hand_to_text.py      # Backward-compatible main entry point
├── tests/
│   └── test_logic.py    # Hardware-independent unit test suite
├── TabletNotAlici.spec  # PyInstaller build specification
└── config.json          # User configuration
```

---

## 📄 License

This project is open-source and licensed under the [MIT License](LICENSE).
