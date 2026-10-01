# 🖊️ InkScribe Pro (TabletNote AI)

> **Fast, hybrid handwriting-to-text note-taking app for graphics tablets and touch screens on Windows.**  
> Powered by **Windows Ink (Offline)** and **Google Gemini Vision (Online AI)**.

[🇹🇷 Türkçe Dokümantasyon](README_TR.md)

[![CI & Tests](https://github.com/radpy-v4/inkscribe-pro/actions/workflows/ci.yml/badge.svg)](https://github.com/radpy-v4/inkscribe-pro/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=flat&logo=windows&logoColor=white)](https://microsoft.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![AI Supported](https://img.shields.io/badge/AI-Google%20Gemini%20Vision-4285F4?style=flat&logo=google)](https://ai.google.dev/)

---

## 🌟 Highlights

- **⚡ Hybrid Recognition Engine:**
  - **Offline (Windows Ink):** Ultra-fast 30ms local handwriting recognition powered by native Windows Ink APIs. No internet connection required.
  - **Online (Google Gemini Vision AI):** High-accuracy cloud AI recognition using ultra-fast **`gemini-3.5-flash-lite`** (~1.2s) with fallback to **`gemini-3-flash-preview`**.
  - **Resilient Fallback & Quota Protection:** Automatically fails over to the next candidate model or drops smoothly to offline Windows Ink if network drops or rate limits occur.
- **🛡️ Explicit Privacy Consent:**
  - Handwriting drawings are **never** transmitted to Google Cloud without explicit user confirmation via an interactive GUI dialog (`tkinter.messagebox.askyesno`).
- **⌨️ Natural Word-Spaced Auto-Type:**
  - Recognized words automatically append trailing whitespace when pasted into your active application (Word, Notion, VS Code, Browser), preventing consecutive handwritten words from sticking together.
- **💬 Live 2-Line Note Preview & Floating Toast Notifications:**
  - Displays the last 2 recognized notes directly on the pad's footer in real-time.
  - Automatically loads and displays the latest notes whenever you switch between notebooks.
  - Displays non-intrusive, temporary toast alerts (e.g., when undo is blocked) with distinct background shading.
- **🖥️ Dual Display Modes with Non-Activating Focus:**
  - **Floating Mini Pad:** Sleek dark-glass PIP (picture-in-picture) notepad that floats on top of your apps. Movable and resizable (DPI scaled). Equipped with Win32 `WS_EX_NOACTIVATE` so it never steals keyboard focus from Word, your browser, or code editor.
  - **Transparent Full-Screen Overlay:** Annotate and take notes directly over your entire screen.
- **↶ Smart Undo Buffer:**
  - Stylus-friendly **`[↶]`** top bar button and **`Ctrl + Z`** keyboard shortcut in Full-Screen mode.
  - Protects against accidental scratch-outs or clears without contaminating the restored canvas with scribble lines.
  - Simultaneously reconstructs both the PIL image and native Windows Ink stroke containers.
- **✍️ Intuitive In-Pad Gestures:**
  - **Scratch-out:** Scribble over your drawing to instantly wipe the canvas clean (protected by oscillation density checks against cursive words).
  - **Vertical Stroke:** A quick downward stroke creates a newline immediately (converts existing text first if present, then queues newline).
- **📚 Multi-Notebook Management:**
  - Switch seamlessly between designated notebooks (e.g. *Lecture Notes*, *To-Do List*, *Ideas*) with automatic `.txt` file persistence.
- **🛡️ Privacy-First Logging & 0% Idle CPU:**
  - Handwritten notes are never logged as plaintext; only length and status are saved.
  - Built-in `RotatingFileHandler` (512 KB × 2 backups) caps disk space.
  - Zero idle CPU footprint when nothing is drawn on the canvas.

---

## ⌨️ Controls & Shortcuts

| Shortcut / Button | Supported Mode | Description |
| :--- | :--- | :--- |
| **`F8`** | Global (Always) | Toggle Note Pad display (configurable in config.json) |
| **`F9`** | Global (Always) | Switch between Floating Mini Pad and Full-Screen Mode |
| **`[↶]` Button** | Mini Pad & Full-Screen | Undo last cleared or scratched-out drawing |
| **`[Temizle]` Button** | Mini Pad & Full-Screen | Clear canvas (saved to undo buffer) |
| **`Vertical Flick`** | Stylus / Pen Gesture | Add new line / Enter in active notebook (converts text first if written) |
| **`Scratch-out`** | Stylus / Pen Gesture | Erase stroke and clear pad (recoverable via ↶ button) |
| **`Ctrl + Z`** | Full-Screen Mode | Undo last cleared drawing |
| **`Enter`** | Full-Screen Mode | Convert drawing to text immediately |
| **`Esc`** | Full-Screen Mode | Hide drawing pad |
| **`Shift + Esc`** | Full-Screen Mode | Exit application completely |

> **ℹ️ Keyboard Focus in Mini Pad Mode:**  
> The Floating Mini Pad utilizes Windows `WS_EX_NOACTIVATE` window styling so your background application (Word, Notion, VS Code, Browser, etc.) keeps its physical typing focus and text cursor untouched while you write notes with your stylus. Therefore, hardware keyboard strokes (`Esc`, `Enter`, `Ctrl+Z`) continue to route to your underlying app. In Floating Mini Pad mode, all interactions are performed directly via stylus/touch controls (`[↶]`, `[Temizle]`, `[✕]` buttons and gestures). Keyboard shortcuts are active in **Full-Screen** overlay mode.

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
git clone https://github.com/radpy-v4/inkscribe-pro.git
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
    "gemini_model": "gemini-3.5-flash-lite",
    "model_adaylari": [
        "gemini-3.5-flash-lite",
        "gemini-3-flash-preview"
    ],
    "gemini_timeout": 3.5,
    "ai_modu_aktif": true
}
```
*(You can also set the `GEMINI_API_KEY` environment variable. If left empty, the application runs entirely in offline mode using Windows Ink).*

---

## 🏃 Run Application

```bash
python app.py
```
*(For headless background execution without a console window, run `pythonw app.py`).*

Press **`F8`** anywhere in Windows to bring up the notepad and start writing with your pen!

---

## 🧪 Running Unit Tests

Run the hardware-independent logic and algorithm test suite:
```bash
python -m unittest tests/test_logic.py
```

---

## 📦 Build Standalone Executable (.exe)

You can package the application into a standalone Windows binary using PyInstaller:

```bash
pyinstaller TabletNotAlici.spec
```
The compiled single-file executable will be located in `dist/TabletNotAlici.exe`. In standalone mode, user settings, notebooks, and logs are safely and persistently stored under `%APPDATA%\InkScribePro` to prevent temporary `_MEIPASS` data loss.

---

## 🏗️ Modular Architecture

The codebase is organized into clean, single-responsibility modules:

```text
TABLET_ELYAZİ/
├── src/
│   ├── __init__.py      # Package indicator & public API exports
│   ├── config.py        # ConfigManager, persistent settings & Windows startup registry
│   ├── engine.py        # RecognitionEngine: Windows Ink (Offline) & Gemini Vision (Online)
│   ├── gestures.py      # Pure Scratch-out & Vertical Stroke (Enter) algorithms
│   ├── storage.py       # NotebookManager, multi-notebooks & text formatting
│   ├── tray.py          # TrayManager: System tray icon & desktop notifications
│   └── ui.py            # ArkaPlanNotDonusturucu: Dual-mode UI, drawing canvas & workflow
├── app.py               # Lightweight main entry point
├── tests/
│   └── test_logic.py    # Hardware-independent unit test suite (28 tests)
├── TabletNotAlici.spec  # PyInstaller build specification
└── config.json          # User configuration
```

---

## 📄 License

This project is open-source and licensed under the [MIT License](LICENSE).
