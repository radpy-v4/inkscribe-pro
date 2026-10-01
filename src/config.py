import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
try:
    import winreg
except ImportError:
    winreg = None
import threading

def get_user_data_dir():
    """
    Kullanıcı verileri için kalıcı dizin:
    PyInstaller Standalone (.exe) modunda %APPDATA%\\InkScribePro kullanılır
    (geçici _MEIPASS dizinindeki veri kaybını önler).
    Geliştirme / kaynak kod ortamında repo kök dizini kullanılır.
    """
    if getattr(sys, 'frozen', False):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        data_dir = os.path.join(base, "InkScribePro")
    else:
        data_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

APP_DIR = get_user_data_dir()
DEBUG_KAYDET = False
REG_STARTUP_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_APP_NAME = "InkScribePro"

logger = logging.getLogger("InkScribePro")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

def _global_excepthook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Kritik Yakalanmamış İstisna (Global):", exc_info=(exc_type, exc_value, exc_traceback))

def _threading_excepthook(args):
    logger.critical(f"Kritik Thread İstisnası [{args.thread.name}]:", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

def setup_logging(app_dir=None):
    """Loglama ve pythonw excepthook yapılandırmasını yalnızca uygulama başlatılırken kurar."""
    target_dir = app_dir or APP_DIR
    log_dosyasi = os.path.join(target_dir, "not_alici.log")
    handlers = [
        RotatingFileHandler(log_dosyasi, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
    ]
    if sys.stdout is not None:
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True
    )

    sys.excepthook = _global_excepthook
    if hasattr(threading, 'excepthook'):
        threading.excepthook = _threading_excepthook


class ConfigManager:
    """Yapılandırma ayarlarını, API modellerini ve Windows başlangıç kaydını yönetir."""

    def __init__(self, app_dir=APP_DIR):
        self.app_dir = app_dir
        self.config_dosyasi = os.path.join(self.app_dir, "config.json")
        self._lock = threading.Lock()
        self.env_api_key = os.environ.get("GEMINI_API_KEY", "")
        self.gemini_api_key = self.env_api_key
        self.api_key_env_den_mi = bool(self.env_api_key)
        self._dosyadaki_api_key = ""

        # Gemini model adayları, zaman aşımı ve varsayılan aktif model
        self.model_adaylari = ["gemini-3.5-flash-lite", "gemini-3-flash-preview"]
        self.gemini_model = "gemini-3.5-flash-lite"
        self.gemini_timeout = 3.5
        self.gemini_toplam_butce = 6.0  # Tüm modeller için maksimum toplam bekleme süresi
        self.ai_modu_aktif = True
        self.ai_onay_verildi = False
        self.ai_consent_gosterildi = False
        self.titreme_filtresi_aktif = True
        self.hotkey_toggle = "<f8>"
        self.hotkey_fullscreen = "<f9>"
        self.thinking_desteklemeyenler = set()
        self._notes_dir = self.app_dir
        self.notes_dir_fallback_olustu = False
        self._cached_notes_dir = self.app_dir

        self.yukle()

    def _dogrula_ve_coz_notes_dir(self, val):
        s = (val or "").strip()
        if not s or s == self.app_dir:
            self.notes_dir_fallback_olustu = False
            return self.app_dir

        expanded = os.path.abspath(os.path.expanduser(s))
        try:
            os.makedirs(expanded, exist_ok=True)
            test_file = os.path.join(expanded, ".inkscribe_write_test")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(test_file)
            self.notes_dir_fallback_olustu = False
            return expanded
        except Exception as e:
            logger.warning(f"[Config] notes_dir '{val}' erişilemez veya yazılamaz ({e}). '{self.app_dir}' dizinine dönülüyor.")
            self.notes_dir_fallback_olustu = True
            return self.app_dir

    @property
    def notes_dir(self):
        return self._cached_notes_dir

    @notes_dir.setter
    def notes_dir(self, val):
        self._notes_dir = val
        self._cached_notes_dir = self._dogrula_ve_coz_notes_dir(val)

    def yukle(self):
        with self._lock:
            try:
                if os.path.exists(self.config_dosyasi):
                    with open(self.config_dosyasi, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        self._dosyadaki_api_key = cfg.get("gemini_api_key", "")
                        if not self.env_api_key:
                            self.gemini_api_key = self._dosyadaki_api_key

                        if "model_adaylari" in cfg and isinstance(cfg["model_adaylari"], list) and cfg["model_adaylari"]:
                            self.model_adaylari = cfg["model_adaylari"]

                        self.gemini_timeout = float(cfg.get("gemini_timeout", self.gemini_timeout))
                        self.gemini_toplam_butce = float(cfg.get("gemini_toplam_butce", self.gemini_toplam_butce))
                        self._notes_dir = cfg.get("notes_dir", self.app_dir)
                        self._cached_notes_dir = self._dogrula_ve_coz_notes_dir(self._notes_dir)

                        self.hotkey_toggle = cfg.get("hotkey_toggle", self.hotkey_toggle)
                        self.hotkey_fullscreen = cfg.get("hotkey_fullscreen", self.hotkey_fullscreen)
                        self.ai_onay_verildi = bool(cfg.get("ai_onay_verildi", self.ai_onay_verildi))
                        self.ai_consent_gosterildi = cfg.get("ai_consent_gosterildi", self.ai_consent_gosterildi)
                        self.titreme_filtresi_aktif = bool(cfg.get("titreme_filtresi_aktif", self.titreme_filtresi_aktif))

                        loaded_model = cfg.get("gemini_model", self.gemini_model)
                        # Sadece fiilen kapanmış veya aşırı kotalı eski modelleri yükselt
                        if loaded_model in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-3.5-flash"]:
                            logger.info(f">> [Config Güncelleme] Emekli/kotalı model ({loaded_model}) yerine '{self.model_adaylari[0]}' atandı.")
                            self.gemini_model = self.model_adaylari[0]
                            self._kaydet_unlocked()
                        else:
                            self.gemini_model = loaded_model

                        self.thinking_desteklemeyenler = set(cfg.get("thinking_desteklemeyenler", []))
                        self.ai_modu_aktif = cfg.get("ai_modu_aktif", self.ai_modu_aktif)
                        logger.info(f">> [Config] Yüklendi ({self.config_dosyasi}) - Model: {self.gemini_model} | Timeout: {self.gemini_timeout}s")
                else:
                    self._kaydet_unlocked()
            except Exception as e:
                logger.error(f"[Config Hatası]: {e}")

    def kaydet(self):
        with self._lock:
            self._kaydet_unlocked()

    def _kaydet_unlocked(self):
        """Atomik ve kilit korumalı dosya yazma (geçiçi dosya + os.replace)."""
        try:
            # Ortam değişkeni varsa dosyadaki mevcut anahtarı ezme
            kaydedilecek_key = self._dosyadaki_api_key if self.api_key_env_den_mi else self.gemini_api_key
            cfg = {
                "gemini_api_key": kaydedilecek_key,
                "gemini_model": self.gemini_model,
                "model_adaylari": self.model_adaylari,
                "gemini_timeout": self.gemini_timeout,
                "gemini_toplam_butce": self.gemini_toplam_butce,
                "notes_dir": self._notes_dir,
                "hotkey_toggle": self.hotkey_toggle,
                "hotkey_fullscreen": self.hotkey_fullscreen,
                "ai_modu_aktif": self.ai_modu_aktif,
                "ai_onay_verildi": self.ai_onay_verildi,
                "ai_consent_gosterildi": self.ai_consent_gosterildi,
                "titreme_filtresi_aktif": self.titreme_filtresi_aktif,
                "thinking_desteklemeyenler": sorted(list(self.thinking_desteklemeyenler)),
                "aciklama": "ai_modu_aktif true iken Gemini Vision modeli kullanılır. Model yanıt vermezse anında offline Windows Ink motoruna düşer."
            }
            tmp_dosya = self.config_dosyasi + ".tmp"
            with open(tmp_dosya, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
            os.replace(tmp_dosya, self.config_dosyasi)
        except Exception as e:
            logger.error(f"[Config Kayıt Hatası]: {e}")

    def baslangic_durumu_al(self):
        if not winreg:
            return False
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_STARTUP_PATH, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, REG_APP_NAME)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def baslangic_durumu_degistir(self, script_path=None):
        if not winreg:
            return
        mevcut = self.baslangic_durumu_al()
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_STARTUP_PATH, 0, winreg.KEY_SET_VALUE)
            if not mevcut:
                if getattr(sys, 'frozen', False):
                    cmd = f'"{sys.executable}"'
                else:
                    python_dir = os.path.dirname(sys.executable)
                    pythonw_exe = os.path.join(python_dir, "pythonw.exe")
                    if not os.path.exists(pythonw_exe):
                        pythonw_exe = sys.executable
                    if not script_path:
                        script_path = os.path.join(self.app_dir, "app.py")
                    cmd = f'"{pythonw_exe}" "{script_path}"'

                winreg.SetValueEx(key, REG_APP_NAME, 0, winreg.REG_SZ, cmd)
                logger.info(f">> [Windows Başlangıç] Eklendi: {cmd}")
            else:
                try:
                    winreg.DeleteValue(key, REG_APP_NAME)
                    logger.info(">> [Windows Başlangıç] Kaldırıldı.")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            logger.error(f"[Kayıt Defteri Hatası]: {e}")
