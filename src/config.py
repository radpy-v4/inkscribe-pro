import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
import winreg

# Uygulama ana dizini (Çalıştırılan ortamdan bağımsız mutlak yol)
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBUG_KAYDET = False  # Disk I/O tasarrufu için varsayılan kapalı
REG_STARTUP_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_APP_NAME = "TabletNotAlici"

# Gizlilik Odaklı ve Boyut Korumalı Loglama: 512 KB x 2 yedek, özel el yazısı içeriğini diske sızdırmaz
LOG_DOSYASI = os.path.join(APP_DIR, "not_alici.log")
log_handlers = [
    RotatingFileHandler(LOG_DOSYASI, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
]
if sys.stdout is not None:
    log_handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=log_handlers
)
logger = logging.getLogger("TabletNotAlici")


class ConfigManager:
    """Yapılandırma ayarlarını, API modellerini ve Windows başlangıç kaydını yönetir."""

    def __init__(self, app_dir=APP_DIR):
        self.app_dir = app_dir
        self.config_dosyasi = os.path.join(self.app_dir, "config.json")
        self.env_api_key = os.environ.get("GEMINI_API_KEY", "")
        self.gemini_api_key = self.env_api_key
        self.api_key_env_den_mi = bool(self.env_api_key)

        # Gemini model adayları ve varsayılan aktif model
        self.model_adaylari = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash"]
        self.gemini_model = "gemini-3.5-flash"
        self.ai_modu_aktif = True
        self.thinking_desteklemeyenler = set()

        self.yukle()

    def yukle(self):
        try:
            if os.path.exists(self.config_dosyasi):
                with open(self.config_dosyasi, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if not self.env_api_key:
                        self.gemini_api_key = cfg.get("gemini_api_key", self.gemini_api_key)

                    loaded_model = cfg.get("gemini_model", self.gemini_model)
                    # Eski veya kapanmış modeller kayıtlıysa yeni varsayılana otomatik yükselt
                    if loaded_model in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash"]:
                        logger.info(f">> [Config Güncelleme] Emekli model ({loaded_model}) yerine '{self.model_adaylari[0]}' atandı.")
                        self.gemini_model = self.model_adaylari[0]
                        self.kaydet()
                    else:
                        self.gemini_model = loaded_model

                    self.thinking_desteklemeyenler = set(cfg.get("thinking_desteklemeyenler", []))
                    self.ai_modu_aktif = cfg.get("ai_modu_aktif", self.ai_modu_aktif)
                    logger.info(f">> [Config] Yüklendi ({self.config_dosyasi}) - Model: {self.gemini_model} | AI: {self.ai_modu_aktif}")
            else:
                self.kaydet()
        except Exception as e:
            logger.error(f"[Config Hatası]: {e}")

    def kaydet(self):
        try:
            # Ortam değişkeninden gelen API anahtarını diske açık metin yazma
            kaydedilecek_key = "" if self.api_key_env_den_mi else self.gemini_api_key
            cfg = {
                "gemini_api_key": kaydedilecek_key,
                "gemini_model": self.gemini_model,
                "ai_modu_aktif": self.ai_modu_aktif,
                "thinking_desteklemeyenler": sorted(list(self.thinking_desteklemeyenler)),
                "aciklama": "ai_modu_aktif true iken Gemini Vision modeli kullanılır. Model yanıt vermezse anında offline Windows Ink motoruna düşer."
            }
            with open(self.config_dosyasi, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[Config Kayıt Hatası]: {e}")

    def baslangic_durumu_al(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_STARTUP_PATH, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, REG_APP_NAME)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def baslangic_durumu_degistir(self, script_path=None):
        mevcut = self.baslangic_durumu_al()
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_STARTUP_PATH, 0, winreg.KEY_SET_VALUE)
            if not mevcut:
                python_dir = os.path.dirname(sys.executable)
                pythonw_exe = os.path.join(python_dir, "pythonw.exe")
                if not os.path.exists(pythonw_exe):
                    pythonw_exe = sys.executable
                if not script_path:
                    script_path = os.path.join(self.app_dir, "hand_to_text.py")
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
