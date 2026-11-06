#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TabletNotAlici / InkScribe Pro
Ana Giriş Noktası (Main Application Entry Point)

Bu dosya uygulamanın modern ve modüler mimarideki standart çalıştırma noktasıdır.
Doğrudan `python app.py` komutuyla veya `TabletNotAlici.exe` derlemesiyle başlatılır.
"""

import os
import sys

# Eğer sanal ortam (.venv) mevcutsa ve uygulama bağımlılıkların bulunmadığı küresel Python ile
# başlatılmışsa, pystray/winrt gibi modüllerin eksik kalmaması için otomatik .venv ile yeniden başlat.
if not getattr(sys, 'frozen', False):
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python) and os.path.abspath(sys.executable).lower() != os.path.abspath(venv_python).lower():
        import subprocess
        sys.exit(subprocess.call([venv_python] + sys.argv))

from src.ui import main

if __name__ == "__main__":
    main()
