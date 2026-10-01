import tkinter as tk
from PIL import Image, ImageDraw, ImageChops, ImageTk
import threading
import time
import os
import sys
import io
import base64
import urllib.request
import urllib.error
import json
import winreg
import asyncio
import ctypes
import logging
from logging.handlers import RotatingFileHandler
from pynput import keyboard
import pystray

# Windows Yerel Türkçe El Yazısı Tanıma API'si (Windows Ink Recognition)
import winrt.windows.ui.input.inking as inking
import winrt.windows.foundation as foundation

user32 = ctypes.windll.user32
REG_STARTUP_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_APP_NAME = "TabletNotAlici"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_KAYDET = False  # Disk I/O tasarrufu için varsayılan kapalı

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


class ArkaPlanNotDonusturucu:
    def __init__(self, root):
        self.root = root
        self.root.title("VEIKK VK640 Not Alıcı Pro")
        
        # Ekran boyutları
        self.ekran_genislik = self.root.winfo_screenwidth()
        self.ekran_yukseklik = self.root.winfo_screenheight()

        # ÇİFT MOD AYARLARI: Yüzen Mini Pad (Varsayılan) ve Tam Ekran
        self.tam_ekran_mi = False
        self.pad_genislik = 880
        self.pad_yukseklik = 420
        self.pad_x = max(20, self.ekran_genislik - 910)
        self.pad_y = max(20, self.ekran_yukseklik - 480)
        self.boyutlandiriliyor = False

        # Başlangıç pencere konfigürasyonu
        self.root.overrideredirect(True)  # Menü çubuğunu gizle
        self.root.lift()
        self.root.wm_attributes("-topmost", True)
        self.pencere_boyutunu_guncelle()

        logger.info("[1/3] Windows Yerel El Yazısı Tanıma Motoru (Windows Ink) başlatılıyor...")
        self.ink_container = inking.InkRecognizerContainer()
        self.stroke_builder = inking.InkStrokeBuilder()
        self.stroke_container = inking.InkStrokeContainer()
        self.aktif_noktalar = []
        self.tum_stroke_noktalari = []  # Windows Ink Undo ve bellek tasarruflu görsel üretimi için
        self.stroke_baslangic_zamani = 0

        # Türkçe el yazısı tanıyıcısını seç (Kesin eşleşme - Chinese Traditional vb. dilleri ele)
        motor_adi = "Varsayılan"
        for r in self.ink_container.get_recognizers():
            name = r.name.lower()
            if "turkish" in name or "türk" in name or name.startswith("tr-") or name == "tr":
                self.ink_container.set_default_recognizer(r)
                motor_adi = r.name
                break
        logger.info(f"[2/3] El yazısı motoru hazır: {motor_adi} (100% Çevrimdışı & Donanım Hızlandırmalı)")

        self.son_yazma_zamani = time.time()
        self.bekleme_suresi = 0.65  # Hızlı algılama süresi (0.65 saniye)
        self.kalem_basili = False
        self.isleniyor = False
        self.yazma_modu_aktif = False
        self.surukleniyor = False
        self.cizim_yapildi = False  # Boşta %0 CPU için bayrak
        self.bekleyen_yeni_satir = 0  # Dönüşüm sürerken gelen Enter jestlerinin sayacı

        # Akıllı metin akışı takibi ve Hedef Pencere Odak Takibi
        self.son_kayit_zamani = 0
        self.son_kayit_tarihi = ""
        self.son_hedef_hwnd = None
        self.toast_timer_id = None

        # Geri Al (Undo) Tamponu (Tek kullanımlık, bayatlamayan yapı)
        self.son_silinen_resim = None
        self.son_silinen_stroke_noktalari = []
        self.canvas_bg_photo = None

        # Yetenekler
        self.otomatik_yapistir = True
        self.otomatik_enter = False  # Hedef uygulamaya gerçek Enter basma (güvenlik için varsayılan KAPALI)
        self.thinking_desteklemeyenler = set()  # thinkingConfig desteklemeyen modelleri önbelleğe al

        # Çoklu Defterler (Mutlak yollara bağlandı - CWD bağımsız)
        self.defterler = [
            ("Genel", os.path.join(APP_DIR, "notlar.txt")),
            ("Ders Notları", os.path.join(APP_DIR, "ders_notlari.txt")),
            ("Yapılacaklar", os.path.join(APP_DIR, "yapilacaklar.txt")),
            ("Fikirler", os.path.join(APP_DIR, "fikirler.txt"))
        ]
        self.aktif_defter_index = 0
        self.son_metinler = []
        self.defterin_son_satirlarini_yukle()

        # Gemini Vision Hibrit Ayarları & Güncel Model Listesi (Emekli 1.5 kaldırıldı)
        self.config_dosyasi = os.path.join(APP_DIR, "config.json")
        self.env_api_key = os.environ.get("GEMINI_API_KEY", "")
        self.gemini_api_key = self.env_api_key
        self.model_adaylari = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash"]
        self.gemini_model = "gemini-3.5-flash"
        self.ai_modu_aktif = True
        self.api_key_env_den_mi = bool(self.env_api_key)
        self.yapilandirmayi_yukle()

        # Canvas ve arka plan görsel katmanı
        w, h = self.mevcut_boyut()
        self.image = Image.new("RGB", (w, h), "white")
        self.draw = ImageDraw.Draw(self.image)

        self.canvas = tk.Canvas(root, bg="#0f172a", highlightthickness=1, highlightbackground="#38bdf8", cursor="pencil")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Çizim ve sürükleme olayları
        self.canvas.bind("<Button-1>", self.fare_basildi)
        self.canvas.bind("<B1-Motion>", self.fare_hareket)
        self.canvas.bind("<ButtonRelease-1>", self.fare_birakildi)

        self.son_x, self.son_y = None, None

        # Kısayol Tuşları (Tam ekran modunda çalışır)
        self.root.bind("<Escape>", lambda e: self.yazma_modunu_kapat())
        self.root.bind("<Return>", lambda e: self.aninda_donustur())
        self.root.bind("<Shift-Escape>", lambda e: self.programi_kapat())
        self.root.bind("<Control-z>", lambda e: self.geri_al())
        self.root.bind("<Control-Z>", lambda e: self.geri_al())

        # Başlangıçta pencereyi gizle
        self.root.withdraw()

        # Global Kısayol Dinleyicisi
        def _f8_tetiklendi():
            try:
                cur_hwnd = user32.GetForegroundWindow()
                my_hwnd = self.root.winfo_id()
                parent_hwnd = user32.GetParent(my_hwnd) if my_hwnd else None
                if cur_hwnd and cur_hwnd not in (my_hwnd, parent_hwnd):
                    self.son_hedef_hwnd = cur_hwnd
            except Exception:
                pass
            self.root.after(0, self.toggle_yazma_modu)

        self.hotkey_listener = keyboard.GlobalHotKeys({
            '<f8>': _f8_tetiklendi,
            '<f9>': lambda: self.root.after(0, self.toggle_tam_ekran)
        })
        self.hotkey_listener.start()

        # Sistem Tepsisi
        self.tepsi_simgesi_olustur()

        logger.info("[3/3] Dinleyici aktif!")
        logger.info("      [F8] = Not Pedini Göster/Gizle")
        logger.info("      [F9] = Yüzen Mini Pad / Tam Ekran Değiştir")
        logger.info("      [↶ / Ctrl+Z] = Silinen Çizimi Geri Al")
        logger.info("      Jestler: Karalama = Temizle, Dikey Çizgi = Enter / Yeni Satır.")

        # Zamanlayıcı döngüsü (Thread-Safe after çağrısıyla)
        threading.Thread(target=self.zamanlayici_dongusu, daemon=True).start()

    def noactivate_ayarla(self):
        """Mini Pad modunda pencerenin klavye odağını çalmasını engeller (WS_EX_NOACTIVATE)."""
        try:
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            hwnd = self.root.winfo_id()
            if hwnd:
                parent = user32.GetParent(hwnd)
                target = parent if parent else hwnd
                style = user32.GetWindowLongW(target, GWL_EXSTYLE)
                user32.SetWindowLongW(target, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
        except Exception as e:
            logger.error(f"[NoActivate Ayar Hatası]: {e}")

    def noactivate_kaldir(self):
        """Tam Ekran modunda WS_EX_NOACTIVATE kaldırılır, klavye kısayolları çalışır."""
        try:
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            hwnd = self.root.winfo_id()
            if hwnd:
                parent = user32.GetParent(hwnd)
                target = parent if parent else hwnd
                style = user32.GetWindowLongW(target, GWL_EXSTYLE)
                user32.SetWindowLongW(target, GWL_EXSTYLE, style & ~WS_EX_NOACTIVATE)
        except Exception as e:
            logger.error(f"[NoActivate Kaldırma Hatası]: {e}")

    def mevcut_boyut(self):
        if self.tam_ekran_mi:
            return self.ekran_genislik, self.ekran_yukseklik
        return self.pad_genislik, self.pad_yukseklik

    def pencere_boyutunu_guncelle(self):
        """Moda göre pencere boyutunu, saydamlığını ve pencere stilini ayarlar."""
        if self.tam_ekran_mi:
            self.root.geometry(f"{self.ekran_genislik}x{self.ekran_yukseklik}+0+0")
            self.root.wm_attributes("-alpha", 0.30)
            if hasattr(self, 'canvas'):
                self.canvas.config(bg="#111111", highlightthickness=0)
            self.noactivate_kaldir()
        else:
            self.root.geometry(f"{self.pad_genislik}x{self.pad_yukseklik}+{self.pad_x}+{self.pad_y}")
            self.root.wm_attributes("-alpha", 0.92)  # Yüzen ped şık koyu cam görünümünde
            if hasattr(self, 'canvas'):
                self.canvas.config(bg="#0f172a", highlightthickness=2, highlightbackground="#38bdf8")
            self.noactivate_ayarla()

    def tamponu_temizle(self):
        """Geri alma tamponunu bayatlamaması için sıfırlar."""
        self.son_silinen_resim = None
        self.son_silinen_stroke_noktalari = []

    def stroke_noktalarindan_resim_uret(self, stroke_listesi):
        """Önceki stroke noktalarından temiz bir PIL resmi üretir (Bellek kopyalarını önler)."""
        w, h = self.mevcut_boyut()
        img = Image.new("RGB", (w, h), "white")
        draw = ImageDraw.Draw(img)
        cizgi_w = 3 if not self.tam_ekran_mi else 5
        r = 1.5 if not self.tam_ekran_mi else 2.5
        for pts in stroke_listesi:
            if not pts:
                continue
            if len(pts) == 1:
                draw.ellipse([pts[0].x - r, pts[0].y - r, pts[0].x + r, pts[0].y + r], fill="black")
            for i in range(1, len(pts)):
                draw.line([pts[i - 1].x, pts[i - 1].y, pts[i].x, pts[i].y], fill="black", width=cizgi_w)
                draw.ellipse([pts[i].x - r, pts[i].y - r, pts[i].x + r, pts[i].y + r], fill="black")
        return img

    def toggle_tam_ekran(self):
        """Mini Pad ve Tam Ekran arasında geçiş yapar."""
        self.tam_ekran_mi = not self.tam_ekran_mi
        self.pencere_boyutunu_guncelle()
        self.tamponu_temizle()
        self.ekrani_temizle(yedekle=False)
        mod_adi = "Tam Ekran" if self.tam_ekran_mi else "Yüzen Mini Pad"
        logger.info(f">> [Mod Değişti] {mod_adi}")

    @property
    def aktif_defter_adi(self):
        return self.defterler[self.aktif_defter_index][0]

    @property
    def aktif_defter_dosyasi(self):
        return self.defterler[self.aktif_defter_index][1]

    def defterin_son_satirlarini_yukle(self):
        """Defteri okur, son metinleri ve bugünün tarihi daha önce yazılmış mı kontrol eder."""
        try:
            dosya = self.aktif_defter_dosyasi
            if os.path.exists(dosya):
                bugun_str = time.strftime("%d.%m.%Y")
                bugun_iso = time.strftime("%Y-%m-%d")
                with open(dosya, "r", encoding="utf-8") as f:
                    tum_satirlar = f.readlines()
                    for s in reversed(tum_satirlar[-60:]):
                        if f"📅 {bugun_str}" in s:
                            self.son_kayit_tarihi = bugun_iso
                            break
                    satirlar = [s.strip() for s in tum_satirlar if s.strip() and not s.startswith("#") and not s.startswith("=")]
                    self.son_metinler = satirlar[-2:] if len(satirlar) >= 2 else satirlar
            else:
                self.son_metinler = []
        except Exception:
            self.son_metinler = []

    def sonraki_deftere_gec(self):
        self.aktif_defter_index = (self.aktif_defter_index + 1) % len(self.defterler)
        self.son_kayit_zamani = 0
        self.son_kayit_tarihi = ""
        self.defterin_son_satirlarini_yukle()
        logger.info(f">> [Defter] Aktif: {self.aktif_defter_adi}")
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def defter_sec(self, index):
        self.aktif_defter_index = index
        self.son_kayit_zamani = 0
        self.son_kayit_tarihi = ""
        self.defterin_son_satirlarini_yukle()
        logger.info(f">> [Defter] Aktif: {self.aktif_defter_adi}")
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def yapilandirmayi_yukle(self):
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
                        self.yapilandirmayi_kaydet()
                    else:
                        self.gemini_model = loaded_model

                    self.thinking_desteklemeyenler = set(cfg.get("thinking_desteklemeyenler", []))
                    self.ai_modu_aktif = cfg.get("ai_modu_aktif", self.ai_modu_aktif)
                    logger.info(f">> [Config] Yüklendi ({self.config_dosyasi}) - Model: {self.gemini_model} | AI: {self.ai_modu_aktif}")
            else:
                self.yapilandirmayi_kaydet()
        except Exception as e:
            logger.error(f"[Config Hatası]: {e}")

    def yapilandirmayi_kaydet(self):
        try:
            # Ortam değişkeninden gelen API anahtarını diske sızdırmadan açık metin yazma
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

    def toggle_ai_modu(self, icon=None, item=None):
        self.ai_modu_aktif = not self.ai_modu_aktif
        self.yapilandirmayi_kaydet()
        durum = "⚡ Açık (Online Hibrit)" if self.ai_modu_aktif else "💻 Kapalı (Sadece Çevrimdışı)"
        logger.info(f">> [Vision AI Modu] {durum}")
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def gemini_vision_ile_tani(self, kirpilmis_resim):
        if not self.gemini_api_key or not self.ai_modu_aktif:
            return None
        
        try:
            w, h = kirpilmis_resim.size
            if w > 650:
                h = max(1, int(h * (650 / w)))
                w = 650
                kirpilmis_resim = kirpilmis_resim.resize((w, h), Image.Resampling.BILINEAR)

            buf = io.BytesIO()
            kirpilmis_resim.convert("RGB").save(buf, format="JPEG", quality=78)
            b64_data = base64.b64encode(buf.getvalue()).decode('utf-8')
            
            headers = {
                'Content-Type': 'application/json',
                'X-goog-api-key': self.gemini_api_key
            }

            def _model_cagrisi(model_adi, gonderi_verisi):
                url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_adi}:generateContent'
                r = urllib.request.Request(url, data=json.dumps(gonderi_verisi).encode('utf-8'), headers=headers)
                with urllib.request.urlopen(r, timeout=3.5) as resp:
                    return json.loads(resp.read().decode())

            # Model listesi: önce aktif modeli, 404/kapanma durumunda yedekleri dene
            denenecek_modeller = [self.gemini_model] + [m for m in self.model_adaylari if m != self.gemini_model]
            model_404_aldi = False
            
            for m_adi in denenecek_modeller:
                payload = {
                    'contents': [{
                        'parts': [
                            {'text': 'Sadece bu görseldeki Türkçe el yazısını oku. Başka hiçbir açıklama yapma:'},
                            {
                                'inline_data': {
                                    'mime_type': 'image/jpeg',
                                    'data': b64_data
                                }
                            }
                        ]
                    }],
                    'generationConfig': {
                        'temperature': 0.0,
                        'maxOutputTokens': 500
                    }
                }
                # thinkingConfig reddeden modeller önbellekte tutulur, gereksiz çift istek önlenir
                if m_adi not in self.thinking_desteklemeyenler:
                    payload['generationConfig']['thinkingConfig'] = {
                        'thinkingBudget': 0
                    }

                try:
                    res = _model_cagrisi(m_adi, payload)
                except urllib.error.HTTPError as http_err:
                    hata_metni = http_err.read().decode('utf-8', errors='ignore')
                    
                    # 404/410 (Model Emekli/Kapatılmış) durumunda yedek modele geçiş izni ver
                    if http_err.code in (404, 410):
                        logger.warning(f"[AI Vision] '{m_adi}' modeli bulunamadı/emekli edilmiş (HTTP {http_err.code}).")
                        if m_adi == self.gemini_model:
                            model_404_aldi = True
                        continue

                    # 429 (Kota/Hız Sınırı) veya 503 (Sunucu Aşırı Yoğunluğu) durumunda sıradaki yedek modeli dene
                    if http_err.code in (429, 503):
                        sebep = "hız/kota aşımı (HTTP 429)" if http_err.code == 429 else "sunucu aşırı yoğunluğu (HTTP 503)"
                        logger.warning(f"[AI Vision] '{m_adi}' {sebep} nedeniyle yanıt veremedi. Sıradaki model deneniyor...")
                        continue

                    # ThinkingConfig hatası ise modele göre önbelleğe alıp kalıcı kaydet ve parametresiz tekrar dene
                    if "thinking" in hata_metni.lower() and 'thinkingConfig' in payload.get('generationConfig', {}):
                        logger.info(f"[AI Vision] '{m_adi}' için thinkingConfig desteklenmiyor, önbelleğe alınıp parametresiz deneniyor...")
                        self.thinking_desteklemeyenler.add(m_adi)
                        self.yapilandirmayi_kaydet()
                        kopya_payload = dict(payload)
                        kopya_payload['generationConfig'] = dict(payload['generationConfig'])
                        kopya_payload['generationConfig'].pop('thinkingConfig', None)
                        try:
                            res = _model_cagrisi(m_adi, kopya_payload)
                        except urllib.error.HTTPError as retry_err:
                            retry_hata = retry_err.read().decode('utf-8', errors='ignore')
                            logger.error(f"[AI Vision API Hatası]: HTTP {retry_err.code} - {retry_hata}")
                            return None
                    else:
                        logger.error(f"[AI Vision API Hatası]: HTTP {http_err.code} ({m_adi}) - {hata_metni}")
                        return None

                if res and 'candidates' in res and res['candidates']:
                    candidate = res['candidates'][0]
                    finish_reason = candidate.get('finishReason', '')
                    if finish_reason and finish_reason != 'STOP':
                        logger.warning(f"[AI Vision] Sıradışı finishReason: {finish_reason}")

                    content_obj = candidate.get('content', {})
                    parts_list = content_obj.get('parts', [])
                    # KeyError koruması: tüm parçalardaki text alanlarını güvenle birleştir
                    txt = ''.join(p.get('text', '') for p in parts_list if isinstance(p, dict)).strip()

                    if txt.startswith("```") and txt.endswith("```"):
                        lines = txt.split("\n")
                        txt = "\n".join(lines[1:-1]).strip() if len(lines) >= 3 else txt.replace("```", "").strip()

                    if txt and not txt.lower().startswith("görüntüde") and not txt.lower().startswith("bu görselde"):
                        # YALNIZCA önceki model 404/410 verdiyse yeni modeli kalıcı olarak config'e yaz
                        if model_404_aldi and m_adi != self.gemini_model:
                            logger.info(f">> [Model Otomatik Güncellendi] Eski model kapandığı için yeni varsayılan model: {m_adi}")
                            self.gemini_model = m_adi
                            self.yapilandirmayi_kaydet()
                        return txt

        except Exception as e:
            logger.warning(f"[Vision AI Hızlı Geçiş]: ({e}), yerel motora aktarılıyor...")
        return None

    def baslangic_durumu_al(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_STARTUP_PATH, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, REG_APP_NAME)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def baslangic_durumu_degistir(self, icon=None, item=None):
        mevcut = self.baslangic_durumu_al()
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_STARTUP_PATH, 0, winreg.KEY_SET_VALUE)
            if not mevcut:
                python_dir = os.path.dirname(sys.executable)
                pythonw_exe = os.path.join(python_dir, "pythonw.exe")
                if not os.path.exists(pythonw_exe):
                    pythonw_exe = sys.executable
                script_path = os.path.abspath(__file__)
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

    def otomatik_yapistir_degistir(self, icon=None, item=None):
        self.otomatik_yapistir = not self.otomatik_yapistir
        durum = "Açık" if self.otomatik_yapistir else "Kapalı"
        logger.info(f">> [Auto-Type] Otomatik Yapıştırma: {durum}")

    def otomatik_enter_degistir(self, icon=None, item=None):
        self.otomatik_enter = not self.otomatik_enter
        durum = "Açık (Dikkat: Mesaj/Form/Komut gönderebilir)" if self.otomatik_enter else "Kapalı (Güvenli - Yalnızca Deftere)"
        logger.info(f">> [Auto-Enter] Otomatik Enter Tuşu: {durum}")

    def tepsi_simgesi_olustur(self):
        icon_img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(icon_img)
        d.rounded_rectangle([4, 4, 60, 60], radius=12, fill="#0f172a", outline="#38bdf8", width=3)
        d.polygon([(46, 14), (50, 18), (24, 48), (16, 48), (16, 40)], fill="#38bdf8")
        d.polygon([(16, 48), (14, 52), (20, 50)], fill="#f59e0b")

        # Pystray menü çağrıları Tkinter thread güvenliği için root.after ile sarmalandı
        menu = pystray.Menu(
            pystray.MenuItem("✍️ Not Pedi (F8)", lambda icon, item: self.root.after(0, self.yazma_modunu_ac)),
            pystray.MenuItem("⛶ Tam Ekran / Mini Pad (F9)", lambda icon, item: self.root.after(0, self.toggle_tam_ekran)),
            pystray.MenuItem("↶ Son Çizimi Geri Al", lambda icon, item: self.root.after(0, self.geri_al)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📁 Aktif Defter", pystray.Menu(
                pystray.MenuItem("📝 Genel", lambda icon, item: self.root.after(0, lambda: self.defter_sec(0)), checked=lambda item: self.aktif_defter_index == 0),
                pystray.MenuItem("📘 Ders Notları", lambda icon, item: self.root.after(0, lambda: self.defter_sec(1)), checked=lambda item: self.aktif_defter_index == 1),
                pystray.MenuItem("✅ Yapılacaklar", lambda icon, item: self.root.after(0, lambda: self.defter_sec(2)), checked=lambda item: self.aktif_defter_index == 2),
                pystray.MenuItem("💡 Fikirler", lambda icon, item: self.root.after(0, lambda: self.defter_sec(3)), checked=lambda item: self.aktif_defter_index == 3),
            )),
            pystray.MenuItem("📂 Notlar Dosyasını Aç", lambda icon, item: self.notlar_dosyasini_ac()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚡ Vision AI (Gemini) Hibrit", lambda icon, item: self.root.after(0, self.toggle_ai_modu), checked=lambda item: self.ai_modu_aktif),
            pystray.MenuItem("📋 Otomatik İmlece Yapıştır", self.otomatik_yapistir_degistir, checked=lambda item: self.otomatik_yapistir),
            pystray.MenuItem("⏎ Otomatik Enter Tuşu", self.otomatik_enter_degistir, checked=lambda item: self.otomatik_enter),
            pystray.MenuItem("🚀 Windows Açılışında Başlat", self.baslangic_durumu_degistir, checked=lambda item: self.baslangic_durumu_al()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Programdan Çık", lambda icon, item: self.root.after(0, self.programi_kapat))
        )

        self.tray_icon = pystray.Icon("TabletNotAlici", icon_img, "VEIKK Tablet Not Alıcı Pro", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def notlar_dosyasini_ac(self):
        dosya_yolu = self.aktif_defter_dosyasi
        if not os.path.exists(dosya_yolu):
            with open(dosya_yolu, "w", encoding="utf-8") as f:
                f.write(f"# VEIKK VK640 - {self.aktif_defter_adi}\n\n")
        try:
            os.startfile(dosya_yolu)
        except Exception as e:
            logger.error(f"Dosya açma hatası: {e}")

    def alt_cubuk_gecici_mesaj(self, mesaj, sure=2.2):
        """Alt çubukta veya ekranda çakışmasız, arka planlı geçici bir uyarı gösterir (Toast).
        Eğer pencere gizliyse (örneğin tam ekran modunda dönüşüm sırasında withdraw edilmişse)
        kullanıcıya Windows masaüstü tepsi bildirimi (tray notification) gösterir."""
        pencere_gorunur = False
        try:
            pencere_gorunur = self.root.winfo_viewable() and self.yazma_modu_aktif
        except Exception:
            pencere_gorunur = False

        if not pencere_gorunur:
            if hasattr(self, 'tray_icon') and self.tray_icon:
                try:
                    self.tray_icon.notify(mesaj, "VEIKK Not Alıcı Pro")
                    return
                except Exception as e:
                    logger.debug(f"Tepsi bildirimi hatası: {e}")

        if self.toast_timer_id:
            try:
                self.root.after_cancel(self.toast_timer_id)
            except Exception:
                pass
            self.toast_timer_id = None

        self.canvas.delete("toast_mesaj")
        w, h_win = self.mevcut_boyut()

        if not self.tam_ekran_mi:
            fy1 = h_win - 44
            # Arka plan kutusu çizerek "Son: ..." yazısıyla çakışmasını engelle
            self.canvas.create_rectangle(0, fy1, w, h_win, fill="#0b1120", outline="#ef4444", width=1, tags="toast_mesaj")
            self.canvas.create_text(
                14, fy1 + 22,
                text=mesaj,
                fill="#f87171", anchor="w", font=("Segoe UI", 9, "bold"), tags="toast_mesaj"
            )
        else:
            # Tam ekran modunda ekranın alt-orta kısmında şık yüzen kutu
            bx1 = (w - 460) // 2
            bx2 = (w + 460) // 2
            by1 = h_win - 75
            by2 = h_win - 25
            self.canvas.create_rectangle(bx1, by1, bx2, by2, fill="#1e293b", outline="#ef4444", width=2, tags="toast_mesaj")
            self.canvas.create_text((bx1 + bx2) // 2, (by1 + by2) // 2, text=mesaj, fill="#f87171", font=("Segoe UI", 10, "bold"), tags="toast_mesaj")

        self.toast_timer_id = self.root.after(int(sure * 1000), self._toast_temizle_ve_guncelle)

    def _toast_temizle_ve_guncelle(self):
        self.canvas.delete("toast_mesaj")
        self.toast_timer_id = None
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def geri_al(self):
        """Son silinen veya temizlenen çizimi hem Canvas'a hem de Windows Ink container'a geri yükler (Tek kullanımlık)."""
        # Tuvalde aktif çizim varken geri alma yapılmaz (kullanıcıya görsel bildirim verilir)
        if self.cizim_yapildi:
            self.alt_cubuk_gecici_mesaj("⚠️ Tuvalde çizim varken geri alınamaz! Önce temizleyin.")
            logger.info(">> [Geri Al Engellendi] Tuvalde aktif çizim varken geri alma yapılamaz.")
            return

        if getattr(self, 'son_silinen_resim', None):
            self.image = self.son_silinen_resim.copy()
            self.draw = ImageDraw.Draw(self.image)
            self.canvas.delete("all")
            self.canvas_bg_photo = ImageTk.PhotoImage(self.image)
            self.canvas.create_image(0, 0, image=self.canvas_bg_photo, anchor="nw")

            # Windows Ink stroke'larını yeniden oluştur
            self.stroke_container = inking.InkStrokeContainer()
            self.tum_stroke_noktalari = [list(pts) for pts in self.son_silinen_stroke_noktalari]
            for pts in self.tum_stroke_noktalari:
                try:
                    stroke = self.stroke_builder.create_stroke(pts)
                    self.stroke_container.add_stroke(stroke)
                except Exception:
                    pass

            self.cizim_yapildi = True
            self.son_yazma_zamani = time.time()
            if self.yazma_modu_aktif:
                self.butonlari_ciz()

            # Tampon tek kullanımlıktır, geri yüklendikten sonra temizlenir
            self.tamponu_temizle()
            logger.info(">> [Geri Al] Son çizim ve Windows Ink vuruşları geri yüklendi.")

    def butonlari_ciz(self):
        """Üst kontrol çubuğunu ve butonları çizer."""
        self.canvas.delete("ui_eleman")
        w, _ = self.mevcut_boyut()
        bar_h = 42

        # Mini Pad modunda şık üst taşıma başlığı
        if not self.tam_ekran_mi:
            self.canvas.create_rectangle(0, 0, w, bar_h, fill="#1e293b", outline="", tags="ui_eleman")
            self.canvas.create_text(12, 21, text="⋮⋮ Not Pedi", fill="#94a3b8", anchor="w", font=("Arial", 9, "bold"), tags="ui_eleman")

        sag_x = w - 10
        y = 6
        h = 30

        # [✕ Kapat] Butonu
        self.canvas.create_rectangle(sag_x - 70, y, sag_x, y + h, fill="#ef4444", outline="", tags=("ui_eleman", "btn_kapat"))
        self.canvas.create_text(sag_x - 35, y + 15, text="✕", fill="white", font=("Arial", 11, "bold"), tags=("ui_eleman", "btn_kapat"))

        # [⛶ / 🗗 Boyut Değiştir] Butonu
        boyut_ico = "🗗" if self.tam_ekran_mi else "⛶"
        self.canvas.create_rectangle(sag_x - 125, y, sag_x - 75, y + h, fill="#64748b", outline="", tags=("ui_eleman", "btn_boyut"))
        self.canvas.create_text(sag_x - 100, y + 15, text=boyut_ico, fill="white", font=("Arial", 11, "bold"), tags=("ui_eleman", "btn_boyut"))

        # [🗑 Temizle] Butonu
        self.canvas.create_rectangle(sag_x - 205, y, sag_x - 130, y + h, fill="#f59e0b", outline="", tags=("ui_eleman", "btn_temizle"))
        self.canvas.create_text(sag_x - 167, y + 15, text="🗑 Temizle", fill="white", font=("Arial", 9, "bold"), tags=("ui_eleman", "btn_temizle"))

        # [↶ Geri] Butonu (Stylus / Fare ile basılabilir)
        self.canvas.create_rectangle(sag_x - 275, y, sag_x - 210, y + h, fill="#6366f1", outline="", tags=("ui_eleman", "btn_geri"))
        self.canvas.create_text(sag_x - 242, y + 15, text="↶ Geri", fill="white", font=("Arial", 9, "bold"), tags=("ui_eleman", "btn_geri"))

        # [✓ Dönüştür] Butonu
        self.canvas.create_rectangle(sag_x - 375, y, sag_x - 280, y + h, fill="#10b981", outline="", tags=("ui_eleman", "btn_donustur"))
        self.canvas.create_text(sag_x - 327, y + 15, text="✓ Dönüştür", fill="white", font=("Arial", 9, "bold"), tags=("ui_eleman", "btn_donustur"))

        # [📁 Defter Rozeti]
        defter_metni = f"📁 {self.aktif_defter_adi}"
        defter_w = max(110, len(defter_metni) * 8 + 20)
        btn_sol = sag_x - 385 - defter_w
        self.canvas.create_rectangle(btn_sol, y, sag_x - 385, y + h, fill="#3b82f6", outline="", tags=("ui_eleman", "btn_defter"))
        self.canvas.create_text(btn_sol + (defter_w // 2), y + 15, text=defter_metni, fill="white", font=("Arial", 9, "bold"), tags=("ui_eleman", "btn_defter"))

        # [⚡ AI Modu Rozeti / Butonu]
        ai_metni = "⚡ AI: Açık" if self.ai_modu_aktif else "💻 Offline"
        ai_renk = "#8b5cf6" if self.ai_modu_aktif else "#475569"
        ai_w = 95
        ai_sol = btn_sol - 10 - ai_w
        self.canvas.create_rectangle(ai_sol, y, btn_sol - 10, y + h, fill=ai_renk, outline="", tags=("ui_eleman", "btn_ai"))
        self.canvas.create_text(ai_sol + (ai_w // 2), y + 15, text=ai_metni, fill="white", font=("Arial", 9, "bold"), tags=("ui_eleman", "btn_ai"))

        # Alt Önizleme Çubuğu (Son Eklenen 2 Satır)
        _, h_win = self.mevcut_boyut()
        footer_h = 44
        fy1 = h_win - footer_h
        fy2 = h_win

        if not self.tam_ekran_mi:
            self.canvas.create_rectangle(0, fy1, w, fy2, fill="#0b1120", outline="#1e293b", tags="ui_eleman")

            if not self.son_metinler:
                self.canvas.create_text(
                    14, fy1 + (footer_h // 2), 
                    text="✏️ Kalemle yazın... Otomatik algılar | ↶ = Geri Al | 🗑 = Temizle", 
                    fill="#64748b", anchor="w", font=("Segoe UI", 9, "italic"), tags="ui_eleman"
                )
            elif len(self.son_metinler) == 1:
                txt = self.son_metinler[0]
                if len(txt) > 85: txt = txt[:82] + "..."
                self.canvas.create_text(
                    14, fy1 + 22, 
                    text=f"💬 Son: {txt}", 
                    fill="#38bdf8", anchor="w", font=("Segoe UI", 9, "bold"), tags="ui_eleman"
                )
            else:
                txt1 = self.son_metinler[-2]
                txt2 = self.son_metinler[-1]
                if len(txt1) > 85: txt1 = txt1[:82] + "..."
                if len(txt2) > 85: txt2 = txt2[:82] + "..."
                self.canvas.create_text(
                    14, fy1 + 13, 
                    text=f"  • {txt1}", 
                    fill="#94a3b8", anchor="w", font=("Segoe UI", 8), tags="ui_eleman"
                )
                self.canvas.create_text(
                    14, fy1 + 31, 
                    text=f"💬 {txt2}", 
                    fill="#38bdf8", anchor="w", font=("Segoe UI", 9, "bold"), tags="ui_eleman"
                )

            # Sağ alt köşe boyutlandırma simgesi
            self.canvas.create_line(w - 18, h_win - 6, w - 6, h_win - 18, fill="#64748b", width=2, tags="ui_eleman")
            self.canvas.create_line(w - 12, h_win - 6, w - 6, h_win - 12, fill="#64748b", width=2, tags="ui_eleman")
            self.canvas.create_line(w - 6, h_win - 6, w - 6, h_win - 6, fill="#64748b", width=2, tags="ui_eleman")

    def buton_tiklandi_mi(self, x, y):
        w, _ = self.mevcut_boyut()
        sag_x = w - 10

        defter_metni = f"📁 {self.aktif_defter_adi}"
        defter_w = max(110, len(defter_metni) * 8 + 20)
        btn_sol = sag_x - 385 - defter_w
        ai_w = 95
        ai_sol = btn_sol - 10 - ai_w
        ai_sag = btn_sol - 10

        if 6 <= y <= 36:
            if sag_x - 70 <= x <= sag_x:
                self.yazma_modunu_kapat()
                return True
            elif sag_x - 125 <= x <= sag_x - 75:
                self.toggle_tam_ekran()
                return True
            elif sag_x - 205 <= x <= sag_x - 130:
                self.ekrani_temizle(yedekle=True)
                return True
            elif sag_x - 275 <= x <= sag_x - 210:
                self.geri_al()
                return True
            elif sag_x - 375 <= x <= sag_x - 280:
                self.aninda_donustur()
                return True
            elif btn_sol <= x <= sag_x - 385:
                self.sonraki_deftere_gec()
                return True
            elif ai_sol <= x <= ai_sag:
                self.toggle_ai_modu()
                return True
        return False

    def toggle_yazma_modu(self):
        if self.yazma_modu_aktif:
            self.yazma_modunu_kapat()
        else:
            self.yazma_modunu_ac()

    def yazma_modunu_ac(self):
        self.yazma_modu_aktif = True
        self.ekrani_temizle(yedekle=False)
        self.root.deiconify()
        self.root.lift()
        if self.tam_ekran_mi:
            self.root.focus_force()
        self.butonlari_ciz()
        mod = "Tam Ekran" if self.tam_ekran_mi else "Yüzen Mini Pad"
        logger.info(f">> [{mod.upper()} AÇIK] Aktif Defter: {self.aktif_defter_adi}")

    def yazma_modunu_kapat(self):
        self.yazma_modu_aktif = False
        self.root.withdraw()
        self.ekrani_temizle(yedekle=False)
        logger.info("<< [NOT PEDİ GİZLENDİ] Masaüstüne dönüldü.")

    def fare_basildi(self, event):
        # 1. Buton tıklaması kontrolü
        if self.buton_tiklandi_mi(event.x, event.y):
            return

        w, h = self.mevcut_boyut()

        # 2. Yeniden Boyutlandırma kontrolü (Sağ alt köşe 25x25 piksel)
        if not self.tam_ekran_mi and event.x >= w - 25 and event.y >= h - 25:
            self.boyutlandiriliyor = True
            self._resize_start_x = event.x_root
            self._resize_start_y = event.y_root
            self._orig_w = self.pad_genislik
            self._orig_h = self.pad_yukseklik
            return

        # 3. Üst bar sürükleme kontrolü (Mini Pad modunda y <= 42 ise pencereyi taşır)
        if not self.tam_ekran_mi and event.y <= 42:
            self.surukleniyor = True
            self._drag_start_x = event.x_root
            self._drag_start_y = event.y_root
            self._win_start_x = self.root.winfo_x()
            self._win_start_y = self.root.winfo_y()
            return

        # 4. Alt önizleme çubuğu kontrolü
        if not self.tam_ekran_mi and event.y >= h - 44:
            return

        # 5. Çizim başlatma (Her dokunuşta 6 MB resim kopyalama kaldırıldı - bellek koruması)
        self.kalem_basili = True
        self.cizim_yapildi = True
        self.son_x, self.son_y = event.x, event.y
        self.son_yazma_zamani = time.time()
        self.stroke_baslangic_zamani = time.time()

        self.aktif_noktalar = [foundation.Point(float(event.x), float(event.y))]

        r = 1.5 if not self.tam_ekran_mi else 2.5
        self.draw.ellipse([event.x - r, event.y - r, event.x + r, event.y + r], fill="black")

    def fare_hareket(self, event):
        # Pencere boyutlandırma hareketi (Minimum genişlik 680 px - butonların sığması için)
        if self.boyutlandiriliyor:
            dw = event.x_root - self._resize_start_x
            dh = event.y_root - self._resize_start_y
            self.pad_genislik = max(680, self._orig_w + dw)
            self.pad_yukseklik = max(280, self._orig_h + dh)
            self.root.geometry(f"{self.pad_genislik}x{self.pad_yukseklik}+{self.pad_x}+{self.pad_y}")
            return

        # Pencere taşıma hareketi
        if self.surukleniyor:
            dx = event.x_root - self._drag_start_x
            dy = event.y_root - self._drag_start_y
            self.pad_x = self._win_start_x + dx
            self.pad_y = self._win_start_y + dy
            self.root.geometry(f"{self.pad_genislik}x{self.pad_yukseklik}+{self.pad_x}+{self.pad_y}")
            return

        if not self.kalem_basili:
            return

        self.cizim_yapildi = True
        cizgi_w = 3 if not self.tam_ekran_mi else 5
        r = 1.5 if not self.tam_ekran_mi else 2.5

        if self.son_x is not None and self.son_y is not None:
            self.canvas.create_line(
                self.son_x, self.son_y, event.x, event.y, 
                fill="#00ffcc", width=cizgi_w, capstyle=tk.ROUND, joinstyle=tk.ROUND, smooth=True
            )
            self.draw.line([self.son_x, self.son_y, event.x, event.y], fill="black", width=cizgi_w)
            self.draw.ellipse([event.x - r, event.y - r, event.x + r, event.y + r], fill="black")

            self.aktif_noktalar.append(foundation.Point(float(event.x), float(event.y)))
        
        self.son_x, self.son_y = event.x, event.y
        self.son_yazma_zamani = time.time()

    def jestleri_kontrol_et(self):
        nokta_sayisi = len(self.aktif_noktalar)
        gecen_sure = time.time() - self.stroke_baslangic_zamani

        # 1. Hızlı dikey çizgi (Enter / Yeni Satır)
        # Asenkron yarış durumu çözümü: Eğer arka planda dönüşüm sürüyorsa satırı sıraya al
        if nokta_sayisi >= 5 and gecen_sure < 0.35:
            p_ilk = self.aktif_noktalar[0]
            p_son = self.aktif_noktalar[-1]
            dy = p_son.y - p_ilk.y
            dx = abs(p_son.x - p_ilk.x)
            if dy > 130 and dx < 30 and (dy / max(1.0, dx)) > 4.0:
                logger.info(">> [JEST] Hızlı Dikey Çizgi: Enter (Yeni Satır)!")
                
                # Öncesinde yazılmış bir metin varsa temiz yedek al
                if self.tum_stroke_noktalari:
                    self.son_silinen_resim = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
                    self.son_silinen_stroke_noktalari = [list(pts) for pts in self.tum_stroke_noktalari]

                if self.isleniyor:
                    # Halen Gemini/Ink dönüşümü sürüyorsa yeni satırı dönüşüm sonrasına sıraya al (sayaç)
                    self.bekleyen_yeni_satir += 1
                    logger.info(f">> [JEST Sıralama] Dönüşüm sürdüğü için yeni satır yanıttan sonraya sıraya alındı (Bekleyen: {self.bekleyen_yeni_satir}).")
                else:
                    self.dosyaya_yeni_satir_ekle()
                    # YALNIZCA otomatik_enter açık ise hedef uygulamaya gerçek Enter tuşu gönder
                    if self.otomatik_enter:
                        threading.Thread(target=self._arka_planda_enter_bas, daemon=True).start()

                self.ekrani_temizle(yedekle=False)
                return True

        # 2. Karalama ile Silme Jesti (Scratch-out)
        # Çizginin aynı dar bölgede ileri-geri salınımı (total path vs span) kontrol edilir.
        if nokta_sayisi >= 12:
            x_degerleri = [p.x for p in self.aktif_noktalar]
            yon_degisimleri = 0
            son_yon = 0
            toplam_yol_x = 0
            for i in range(1, len(x_degerleri)):
                fark = x_degerleri[i] - x_degerleri[i - 1]
                toplam_yol_x += abs(fark)
                if abs(fark) > 8:
                    mevcut_yon = 1 if fark > 0 else -1
                    if son_yon != 0 and mevcut_yon != son_yon:
                        yon_degisimleri += 1
                    son_yon = mevcut_yon
            
            genislik_x = max(x_degerleri) - min(x_degerleri)
            if yon_degisimleri >= 6 and (toplam_yol_x / max(1.0, genislik_x)) > 2.5:
                logger.info(">> [JEST] Karalama: Ekran temizlendi! (Geri almak için ↶ butonu)")
                # Karalama lekesi olmadan önceki temiz stroke'lardan yedek görsel üret
                if self.tum_stroke_noktalari:
                    self.son_silinen_resim = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
                    self.son_silinen_stroke_noktalari = [list(pts) for pts in self.tum_stroke_noktalari]
                self.ekrani_temizle(yedekle=False)
                return True

        return False

    def _arka_planda_enter_bas(self, adet=1):
        time.sleep(0.05)
        try:
            if self.tam_ekran_mi and self.son_hedef_hwnd and user32.IsWindow(self.son_hedef_hwnd):
                user32.SetForegroundWindow(self.son_hedef_hwnd)
                time.sleep(0.05)
            kb = keyboard.Controller()
            for _ in range(adet):
                kb.press(keyboard.Key.enter)
                kb.release(keyboard.Key.enter)
                time.sleep(0.03)
            logger.info(f">> [Auto-Enter] Hedef uygulamaya {adet} adet Enter tuşu basıldı.")
        except Exception as e:
            logger.error(f"Auto-Enter Hatası: {e}")

    def fare_birakildi(self, event):
        if self.boyutlandiriliyor:
            self.boyutlandiriliyor = False
            self.tamponu_temizle()
            self.ekrani_temizle(yedekle=False)
            return

        if self.surukleniyor:
            self.surukleniyor = False
            return

        if not self.kalem_basili:
            return

        self.kalem_basili = False
        self.son_x, self.son_y = None, None
        self.son_yazma_zamani = time.time()

        if self.jestleri_kontrol_et():
            self.aktif_noktalar = []
            return

        # Tekil dokunuşları (noktaları) güçlendir
        if len(self.aktif_noktalar) == 1:
            p = self.aktif_noktalar[0]
            self.aktif_noktalar = [
                foundation.Point(p.x, p.y),
                foundation.Point(p.x + 1.0, p.y + 1.0),
                foundation.Point(p.x, p.y + 2.0)
            ]
        elif len(self.aktif_noktalar) == 2:
            p1 = self.aktif_noktalar[0]
            p2 = self.aktif_noktalar[1]
            if abs(p1.x - p2.x) < 2 and abs(p1.y - p2.y) < 2:
                self.aktif_noktalar.append(foundation.Point(p2.x + 1.0, p2.y + 1.0))

        if len(self.aktif_noktalar) >= 2:
            try:
                stroke = self.stroke_builder.create_stroke(self.aktif_noktalar)
                self.stroke_container.add_stroke(stroke)
                self.tum_stroke_noktalari.append(list(self.aktif_noktalar))
            except Exception as e:
                logger.error(f"[Stroke Hatası]: {e}")

        self.aktif_noktalar = []

    def aninda_donustur(self):
        if not self.isleniyor:
            self.tetikle_donusturme()

    def tetikle_donusturme(self):
        # Çizim bayrağı kapalıysa işlem yapma
        if not self.cizim_yapildi:
            return

        strokes_to_process = self.stroke_container
        
        ters_resim = ImageChops.invert(self.image)
        bbox = ters_resim.getbbox()

        if bbox:
            self.isleniyor = True
            islem_resmi = self.image.copy()
            
            # Tam ekran modundaysa kapat, Mini Pad modundaysa açık kalıp içi temizlensin
            if self.tam_ekran_mi:
                self.yazma_modu_aktif = False
                self.root.withdraw()
            
            # Dönüşüm başladığı anda eski geri alma tamponu temizlenir (eski çizimlerin hortlamasını engeller)
            self.tamponu_temizle()
            self.ekrani_temizle(yedekle=False)
            threading.Thread(target=self.metne_donustur, args=(strokes_to_process, islem_resmi, bbox), daemon=True).start()
        else:
            # Resimde gerçek mürekkep bulunamadıysa döngüyü durdurmak için bayrağı kapat
            self.cizim_yapildi = False

    def zamanlayici_dongusu(self):
        """Arka plan zamanlayıcısı - Boşta dururken %0 CPU tüketir, çizim varsa root.after ile tetikler."""
        while True:
            time.sleep(0.2)
            suan = time.time()
            if self.yazma_modu_aktif and self.cizim_yapildi and not self.kalem_basili and not self.isleniyor and not self.surukleniyor:
                if (suan - self.son_yazma_zamani) > self.bekleme_suresi:
                    # Thread-safe çağrı:
                    self.root.after(0, self.tetikle_donusturme)

    def metne_donustur(self, stroke_container, resim, bbox):
        metin_bulundu = False
        try:
            pad = 20
            w, h = self.mevcut_boyut()
            crop_area = (
                max(0, bbox[0] - pad),
                max(0, bbox[1] - pad),
                min(w, bbox[2] + pad),
                min(h, bbox[3] + pad)
            )
            kirpilmis = resim.crop(crop_area)

            # Yazı küçükse harf oranlarını bozmadan, orantılı ölçeklendir
            kw, kh = kirpilmis.size
            if kh < 120:
                scale = 135.0 / max(1, kh)
                target_w = max(60, int(kw * scale))
                target_h = 135
                kirpilmis = kirpilmis.resize((target_w, target_h), Image.Resampling.LANCZOS)

            # Debug kaydı (sadece DEBUG_KAYDET açıkken diske yazar)
            if DEBUG_KAYDET:
                kirpilmis.save(os.path.join(APP_DIR, "debug_son_cizim.png"))

            metin = None

            # 1. Aşama: Vision AI (Gemini) Hibrit Tanıma
            if self.ai_modu_aktif and self.gemini_api_key:
                logger.info(f"[AI Vision] {self.gemini_model} modeli ile taranıyor...")
                metin = self.gemini_vision_ile_tani(kirpilmis)
                if metin:
                    logger.info(f">> [AI Vision Başarılı] ({len(metin)} karakter tanındı)")
                else:
                    logger.info(">> [AI Fallback] Çevrimdışı yerel motora geçiliyor...")

            # 2. Aşama: Windows Ink (100% Offline Yerel Motor)
            if not metin:
                logger.info("[Windows Ink (Offline)] Yerel motor ile el yazısı tanınıyor...")
                async def run_recognition():
                    return await self.ink_container.recognize_async(stroke_container, inking.InkRecognitionTarget.ALL)

                results = asyncio.run(run_recognition())

                kelimeler = []
                turkce_harfler = set("çğıöşüÇĞİÖŞÜ")

                if results:
                    for res in results:
                        candidates = list(res.get_text_candidates())
                        if candidates:
                            secilen = candidates[0].strip()
                            for cand in candidates[:4]:
                                c_strip = cand.strip()
                                if any(ch in turkce_harfler for ch in c_strip) and not any(ch in turkce_harfler for ch in secilen):
                                    secilen = c_strip
                                    break
                            kelimeler.append(secilen)

                metin = " ".join(kelimeler).strip()

            if metin:
                metin_bulundu = True
                # Özel not içeriğini diske sızdırmadan yalnızca başarı ve uzunluk logla
                logger.info(f">> [DÖNÜŞÜM BAŞARILI]: {len(metin)} karakter aktarılıyor.")
                self.root.after(0, lambda: self.panoya_ve_dosyaya_aktar(metin))
            else:
                logger.warning("[Uyarı] Metin algılanamadı.")

        except Exception as e:
            logger.error(f"[Tanıma Hatası]: {e}")
            self.root.after(0, lambda: self.alt_cubuk_gecici_mesaj("⚠️ Tanıma sırasında bir hata oluştu."))
        finally:
            if not metin_bulundu:
                # Yarış durumunu önlemek için ÖNCE isleniyor kapatılır, ardından sayaç boşaltılır
                self.isleniyor = False
                if self.bekleyen_yeni_satir > 0:
                    adet = self.bekleyen_yeni_satir
                    self.bekleyen_yeni_satir = 0
                    for _ in range(adet):
                        self.dosyaya_yeni_satir_ekle()
                    if self.otomatik_enter:
                        threading.Thread(target=self._arka_planda_enter_bas, args=(adet,), daemon=True).start()

    def panoya_ve_dosyaya_aktar(self, metin):
        try:
            pano_basarili = False
            # Kilitlenmeye karşı korumalı pano aktarımı
            for _ in range(3):
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(metin)
                    self.root.update()
                    pano_basarili = True
                    logger.info(">> [Pano] Metin panoya kopyalandı! (Ctrl + V)")
                    break
                except Exception:
                    time.sleep(0.04)

            if not pano_basarili:
                logger.error("[Pano Hatası] Metin panoya yazılamadı! Eski pano içeriğinin sızmaması için otomatik yapıştırma atlandı.")
                self.alt_cubuk_gecici_mesaj("⚠️ Pano kopyalanamadı! Yapıştırma iptal edildi.")

            self.dosyaya_kaydet(metin)

            # Yarış durumunu önlemek için ÖNCE isleniyor kapatılır, bekleyen Enter sayacı alınır
            enter_adet = self.bekleyen_yeni_satir
            self.bekleyen_yeni_satir = 0
            self.isleniyor = False

            if enter_adet > 0:
                for _ in range(enter_adet):
                    self.dosyaya_yeni_satir_ekle()

            # Ped üzerinde gösterilmek üzere son 2 metni güncelle
            self.son_metinler.append(metin)
            if len(self.son_metinler) > 2:
                self.son_metinler = self.son_metinler[-2:]

            if self.yazma_modu_aktif:
                self.root.after(0, self.butonlari_ciz)

            # Sıralı yapıştırma ve Enter: Ctrl+V ve Enter tek bir thread'de sırayla basılır (asla yarış durumu oluşmaz)
            gonderilecek_enter = enter_adet if self.otomatik_enter else 0
            if self.otomatik_yapistir and pano_basarili:
                threading.Thread(target=self._arka_planda_yapistir_ve_enter, args=(gonderilecek_enter,), daemon=True).start()
            elif not self.otomatik_yapistir and gonderilecek_enter > 0:
                threading.Thread(target=self._arka_planda_enter_bas, args=(gonderilecek_enter,), daemon=True).start()

        finally:
            self.isleniyor = False

    def _arka_planda_yapistir_ve_enter(self, enter_adet=0):
        time.sleep(0.12)
        try:
            # Yalnızca tam ekran modundaysa hedef uygulamayı öne getir
            if self.tam_ekran_mi and self.son_hedef_hwnd and user32.IsWindow(self.son_hedef_hwnd):
                user32.SetForegroundWindow(self.son_hedef_hwnd)
                time.sleep(0.08)

            kb = keyboard.Controller()
            with kb.pressed(keyboard.Key.ctrl):
                kb.press('v')
                kb.release('v')
            logger.info(">> [Auto-Type] Metin doğrudan aktif pencerenize yapıştırıldı!")

            if enter_adet > 0:
                time.sleep(0.06)
                for _ in range(enter_adet):
                    kb.press(keyboard.Key.enter)
                    kb.release(keyboard.Key.enter)
                    time.sleep(0.03)
                logger.info(f">> [Auto-Type] Bekleyen {enter_adet} adet yeni satır için Enter tuşu basıldı.")
        except Exception as e:
            logger.error(f"Auto-Type / Enter Hatası: {e}")

    def dosyaya_yeni_satir_ekle(self):
        try:
            dosya_yolu = self.aktif_defter_dosyasi
            with open(dosya_yolu, "a", encoding="utf-8") as f:
                f.write("\n")
            logger.info(f">> [Dosya] Alt satıra geçildi: '{dosya_yolu}'")
        except Exception as e:
            logger.error(f"[Satır Ekleme Hatası]: {e}")

    def dosyaya_kaydet(self, metin):
        try:
            dosya_yolu = self.aktif_defter_dosyasi
            suan_ts = time.time()
            bugun = time.strftime("%Y-%m-%d")
            saat = time.strftime("%H:%M")
            gecen_sure = suan_ts - self.son_kayit_zamani

            dosya_dolu = os.path.exists(dosya_yolu) and os.path.getsize(dosya_yolu) > 0

            is_todo = (self.aktif_defter_adi == "Yapılacaklar")
            is_bullet = metin.startswith(("-", "*", "•", "1.", "2.", "3.", "4.", "5.")) or metin.lower().startswith("madde")

            if is_todo and not metin.startswith(("[ ]", "[x]", "- [ ]")):
                metin = f"[ ] {metin}"

            if bugun != self.son_kayit_tarihi:
                tarih_str = time.strftime("%d.%m.%Y")
                baslik = f"{'='*45}\n📅 {tarih_str} - {self.aktif_defter_adi}\n{'='*45}\n\n"
                if dosya_dolu:
                    eklenecek = f"\n\n{baslik}[{saat}] {metin}"
                else:
                    eklenecek = f"{baslik}[{saat}] {metin}"
                self.son_kayit_tarihi = bugun

            elif is_todo or is_bullet:
                eklenecek = f"\n{metin}"

            elif gecen_sure > 30:
                eklenecek = f"\n\n[{saat}] {metin}"

            else:
                if metin.startswith((".", ",", "!", "?", ":", ";")):
                    eklenecek = metin
                else:
                    eklenecek = f" {metin}"

            with open(dosya_yolu, "a", encoding="utf-8") as f:
                f.write(eklenecek)

            self.son_kayit_zamani = suan_ts
            logger.info(f">> [Dosya] Not '{self.aktif_defter_adi}' defterine kaydedildi.")
        except Exception as e:
            logger.error(f"[Dosya Kayıt Hatası]: {e}")

    def ekrani_temizle(self, yedekle=True):
        """Ekranı temizler. yedekle=True ise temizlenen çizim geri alma (Undo) için saklanır."""
        if yedekle and self.cizim_yapildi and self.tum_stroke_noktalari:
            try:
                self.son_silinen_resim = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
                self.son_silinen_stroke_noktalari = [list(pts) for pts in self.tum_stroke_noktalari]
            except Exception:
                pass

        self.canvas.delete("all")
        w, h = self.mevcut_boyut()
        self.image = Image.new("RGB", (w, h), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.stroke_container = inking.InkStrokeContainer()
        self.aktif_noktalar = []
        self.tum_stroke_noktalari = []
        self.cizim_yapildi = False  # Çizim temizlendi, boşta çalışma durduruldu
        self.son_yazma_zamani = time.time()
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def programi_kapat(self):
        logger.info("Program tamamen kapatılıyor...")
        if hasattr(self, 'hotkey_listener'):
            self.hotkey_listener.stop()
        if hasattr(self, 'tray_icon'):
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()
        os._exit(0)


if __name__ == "__main__":
    root = tk.Tk()
    app = ArkaPlanNotDonusturucu(root)
    root.mainloop()