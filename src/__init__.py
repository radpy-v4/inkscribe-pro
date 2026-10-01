"""
TabletNotAlici / InkScribe Pro
Modüler El Yazısı Tanıma ve Not Alma Paketi (v2.1.0)
"""

__version__ = "2.1.0"

from .config import ConfigManager, logger, APP_DIR, setup_logging
from .storage import NotebookManager, metin_ekleme_bicimlendir
from .engine import RecognitionEngine, WindowsInkRecognizer, GeminiVisionRecognizer, gemini_metin_ayristir
from .gestures import karalama_jesti_mi, dikey_cizgi_jesti_mi

try:
    from .tray import TrayManager
except ImportError:
    TrayManager = None

try:
    from .ui import ArkaPlanNotDonusturucu, main
except ImportError:
    ArkaPlanNotDonusturucu = None
    main = None

__all__ = [
    "ConfigManager",
    "logger",
    "APP_DIR",
    "NotebookManager",
    "metin_ekleme_bicimlendir",
    "RecognitionEngine",
    "WindowsInkRecognizer",
    "GeminiVisionRecognizer",
    "gemini_metin_ayristir",
    "karalama_jesti_mi",
    "dikey_cizgi_jesti_mi",
    "TrayManager",
    "ArkaPlanNotDonusturucu",
    "main",
]
