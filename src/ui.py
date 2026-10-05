import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageChops, ImageTk
import threading
import time
import os
import ctypes
try:
    from pynput import keyboard
except ImportError:
    keyboard = None
from .config import APP_DIR, DEBUG_KAYDET, logger, ConfigManager, setup_logging

try:
    import winrt.windows.ui.input.inking as inking
    import winrt.windows.foundation as foundation
    Point = foundation.Point
except Exception as _e:
    inking = None
    foundation = None
    logger.warning(f"[Windows Ink - UI] winrt import edilemedi: {_e}")
    class Point:
        def __init__(self, x, y):
            self.x = float(x)
            self.y = float(y)
from .gestures import karalama_jesti_mi, dikey_cizgi_jesti_mi, enter_kancasi_jesti_mi, sagdan_sola_cizgi_jesti_mi, soldan_saga_cizgi_jesti_mi
from .filter import TitremeFiltresi
from .storage import NotebookManager
from .engine import RecognitionEngine
from .tray import TrayManager

# Windows DPI Farkındalığı (Tkinter 8.6 için en kararlı mod: PROCESS_SYSTEM_DPI_AWARE = 1)
user32 = None
if hasattr(ctypes, "windll"):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    user32 = getattr(ctypes.windll, "user32", None)


def get_dpi_scale(root):
    """Monitörün DPI ölçekleme oranını hesaplar (96 DPI = 1.0, 144 DPI = 1.5, 192 DPI = 2.0)."""
    try:
        fpixels = root.winfo_fpixels('1i')
        scale = float(fpixels) / 96.0
        return max(1.0, min(scale, 3.0))
    except Exception:
        return 1.0


class ArkaPlanNotDonusturucu:
    """Grafik tabletler ve dokunmatik ekranlar için çift modlu el yazısı arayüzü ve iş akışı kontrolcüsü."""

    def __init__(self, root):
        self.root = root

        # Modüller
        self.config = ConfigManager(APP_DIR)
        self.storage = NotebookManager(self.config.notes_dir)
        self.engine = RecognitionEngine()
        self.tray = TrayManager(self)

        # Ekran boyutları ve DPI Ölçekleme
        self.ekran_genislik = self.root.winfo_screenwidth()
        self.ekran_yukseklik = self.root.winfo_screenheight()
        self.dpi_scale = get_dpi_scale(self.root)

        # Çift Mod Ayarları: Yüzen Mini Pad (Varsayılan) ve Tam Ekran
        self.tam_ekran_mi = False
        self.pad_genislik = int(880 * self.dpi_scale)
        self.pad_yukseklik = int(420 * self.dpi_scale)
        self.pad_x = max(20, self.ekran_genislik - self.pad_genislik - int(30 * self.dpi_scale))
        self.pad_y = max(20, self.ekran_yukseklik - self.pad_yukseklik - int(60 * self.dpi_scale))
        self.boyutlandiriliyor = False

        # Başlangıç pencere konfigürasyonu
        self.root.overrideredirect(True)
        self.root.lift()
        self.root.wm_attributes("-topmost", True)
        self.pencere_boyutunu_guncelle()

        # Windows Ink Vuruş Konteynerleri ve Titreme Filtresi
        self.stroke_builder = inking.InkStrokeBuilder() if inking else None
        self.stroke_container = inking.InkStrokeContainer() if inking else None
        self.titreme_filtresi = TitremeFiltresi(aktif=getattr(self.config, 'titreme_filtresi_aktif', True))
        self.aktif_noktalar = []
        self.tum_stroke_noktalari = []
        self.stroke_baslangic_zamani = 0

        # Zamanlayıcı ve durum bayrakları
        self.son_yazma_zamani = time.time()
        self.bekleme_suresi = float(getattr(self.config, 'bekleme_suresi', 3.5))
        self.kalem_basili = False
        self.isleniyor = False
        self.yazma_modu_aktif = False
        self.surukleniyor = False
        self.cizim_yapildi = False
        self.bekleyen_yeni_satir = 0
        self.bekleyen_tab = 0
        self.debounce_timer_id = None
        self.defter_menu_acik = False

        # Odak takibi ve Toast
        self.son_hedef_hwnd = None
        self.toast_timer_id = None

        # Geri Al (Undo) Tamponu
        self.son_silinen_resim = None
        self.son_silinen_stroke_noktalari = []
        self.canvas_bg_photo = None

        # Yetenekler
        self.otomatik_yapistir = True
        self.otomatik_enter = False
        self.cikis_hedefi = getattr(self.config, 'cikis_hedefi', 'cift')

        # Canvas ve görsel katman
        w, h = self.mevcut_boyut()
        self.image = Image.new("RGB", (w, h), "white")
        self.draw = ImageDraw.Draw(self.image)

        self.canvas = tk.Canvas(root, bg="#0f172a", highlightthickness=1, highlightbackground="#38bdf8", cursor="pencil")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Fare / Kalem Olayları
        self.canvas.bind("<Button-1>", self.fare_basildi)
        self.canvas.bind("<B1-Motion>", self.fare_hareket)
        self.canvas.bind("<ButtonRelease-1>", self.fare_birakildi)

        self.son_x, self.son_y = None, None

        # Klavye Kısayolları (Pencere odaklıyken)
        self.root.bind("<Escape>", lambda e: self.yazma_modunu_kapat())
        self.root.bind("<Return>", lambda e: self.aninda_donustur())
        self.root.bind("<Shift-Escape>", lambda e: self.programi_kapat())
        self.root.bind("<Control-z>", lambda e: self.geri_al())
        self.root.bind("<Control-Z>", lambda e: self.geri_al())

        # Başlangıçta pencereyi gizle
        self.root.withdraw()

        # Global Kısayol Dinleyicisi (Config ile özelleştirilebilir, IDE çakışmalarını önler)
        def _toggle_tetiklendi():
            try:
                if user32:
                    cur_hwnd = user32.GetForegroundWindow()
                    my_hwnd = self.root.winfo_id()
                    parent_hwnd = user32.GetParent(my_hwnd) if my_hwnd else None
                    if cur_hwnd and cur_hwnd not in (my_hwnd, parent_hwnd):
                        self.son_hedef_hwnd = cur_hwnd
            except Exception:
                pass
            self.root.after(0, self.toggle_yazma_modu)

        if keyboard is not None:
            hk_toggle = getattr(self.config, 'hotkey_toggle', '<f8>') or '<f8>'
            hk_full = getattr(self.config, 'hotkey_fullscreen', '<f9>') or '<f9>'
            hk_out = getattr(self.config, 'hotkey_output_mode', '<f10>') or '<f10>'
            if hk_toggle.strip().lower() == hk_full.strip().lower():
                logger.warning(f"[Hotkey Uyarısı] hotkey_toggle ve hotkey_fullscreen aynı olamaz ('{hk_toggle}'). Varsayılanlara dönülüyor.")
                hk_toggle = '<f8>'
                hk_full = '<f9>'

            def _kur_dinleyici(t_key, f_key, o_key):
                d = {
                    t_key: _toggle_tetiklendi,
                    f_key: lambda: self.root.after(0, self.toggle_tam_ekran)
                }
                if o_key and o_key.strip().lower() not in (t_key.strip().lower(), f_key.strip().lower()):
                    d[o_key] = lambda: self.root.after(0, self.cikis_hedefi_degistir)
                return keyboard.GlobalHotKeys(d)

            try:
                self.hotkey_listener = _kur_dinleyici(hk_toggle, hk_full, hk_out)
                self.hotkey_listener.start()
            except Exception as e:
                logger.warning(f"[Hotkey Hatası] '{hk_toggle}', '{hk_full}' veya '{hk_out}' geçersiz ({e}). Varsayılan '<f8>', '<f9>', '<f10>' deneniyor...")
                hk_toggle = '<f8>'
                hk_full = '<f9>'
                hk_out = '<f10>'
                try:
                    self.hotkey_listener = _kur_dinleyici(hk_toggle, hk_full, hk_out)
                    self.hotkey_listener.start()
                except Exception as ex:
                    logger.error(f"[Hotkey Kritik Hata] Global kısayol dinleyicisi başlatılamadı: {ex}")
                    self.hotkey_listener = None
        else:
            self.hotkey_listener = None

        # Sistem Tepsisi
        self.tray.baslat()

        hk_t_str = getattr(self.config, 'hotkey_toggle', '<f8>').upper().strip('<>')
        hk_f_str = getattr(self.config, 'hotkey_fullscreen', '<f9>').upper().strip('<>')
        hk_o_str = getattr(self.config, 'hotkey_output_mode', '<f10>').upper().strip('<>')
        logger.info("[3/3] Dinleyici aktif!")
        logger.info(f"      [{hk_t_str}] = Not Pedini Göster/Gizle")
        logger.info(f"      [{hk_f_str}] = Yüzen Mini Pad / Tam Ekran Değiştir")
        logger.info(f"      [{hk_o_str}] = Çıkış Modu Değiştir (Çift / Ekran / TXT)")
        logger.info("      [↶ / Buton] = Silinen Çizimi Geri Al")
        logger.info("      Jestler: Karalama = Temizle, Enter (↵), Geri Al (←), Tab (→).")

        # Başlangıçta kullanıcıya hazır Not Pedini (Mini Pad) göster
        self.root.after(150, self.yazma_modunu_ac)

        # Başlangıç denetimleri (notes_dir fallback uyarısı ve AI gizlilik onayı)
        self.root.after(400, self._baslangic_kontrolleri)

    def _baslangic_kontrolleri(self):
        """Uygulama açılışında dizin erişilebilirliği ve AI gizlilik onayı durumunu denetler."""
        if getattr(self.config, 'notes_dir_fallback_olustu', False):
            self.alt_cubuk_gecici_mesaj(
                f"⚠️ notes_dir erişilemedi! Notlar uygulama dizinine ({self.config.app_dir}) kaydediliyor.",
                sure=5.0
            )

        # Kullanıcı API anahtarı eklemiş ama henüz açık onay vermemişse sor
        if self.config.gemini_api_key and not getattr(self.config, 'ai_onay_verildi', False) and self.config.ai_modu_aktif:
            self._ai_onay_iste()

    def _ai_onay_iste(self):
        """Kullanıcıdan el yazısı görüntülerinin Google Gemini API'ye gönderilmesi için açık onay ister."""
        baslik = "InkScribe Pro - AI Bulut Tanıma Onayı"
        soru = (
            "Gemini Vision AI modu ile Türkçe el yazısı tanıma kalitesini artırabilirsiniz.\n\n"
            "GİZLİLİK VE VERİ BİLDİRİMİ:\n"
            "Bu özellik aktifken, tabletinizde yazdığınız el yazısı görsel kırpıntıları "
            "metne dönüştürülmek üzere şifreli bağlantıyla Google Cloud (Gemini API) sunucularına iletilir.\n\n"
            "El yazısı görüntülerinizin Google'a iletilmesini onaylıyor musunuz?"
        )
        try:
            onay = messagebox.askyesno(baslik, soru, icon="question", default="yes", parent=self.root)
        except Exception:
            onay = messagebox.askyesno(baslik, soru, icon="question", default="yes")

        if onay:
            self.config.ai_onay_verildi = True
            self.config.ai_modu_aktif = True
            self.config.kaydet()
            logger.info(">> [Gizlilik Onayı] Kullanıcı Gemini Vision bulut tanımayı ONAYLADI.")
            self.alt_cubuk_gecici_mesaj("✅ Gemini Vision AI aktif edildi.", sure=2.5)
            if self.yazma_modu_aktif:
                self.butonlari_ciz()
            return True
        else:
            self.config.ai_onay_verildi = False
            self.config.ai_modu_aktif = False
            self.config.kaydet()
            logger.info(">> [Gizlilik Onayı] Kullanıcı reddetti. AI Modu kapatıldı (100% Çevrimdışı Mod).")
            self.alt_cubuk_gecici_mesaj("ℹ️ AI Modu kapatıldı. Sadece çevrimdışı Windows Ink kullanılacak.", sure=3.5)
            if self.yazma_modu_aktif:
                self.butonlari_ciz()
            return False

    def noactivate_ayarla(self):
        """Mini Pad modunda klavye odağını çalmayı engeller (WS_EX_NOACTIVATE)."""
        if not user32:
            return
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
        """Tam Ekran modunda WS_EX_NOACTIVATE kaldırılır."""
        if not user32:
            return
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
        if self.tam_ekran_mi:
            self.root.geometry(f"{self.ekran_genislik}x{self.ekran_yukseklik}+0+0")
            self.root.wm_attributes("-alpha", 0.30)
            if hasattr(self, 'canvas'):
                self.canvas.config(bg="#111111", highlightthickness=0)
            self.noactivate_kaldir()
        else:
            self.root.geometry(f"{self.pad_genislik}x{self.pad_yukseklik}+{self.pad_x}+{self.pad_y}")
            self.root.wm_attributes("-alpha", 0.92)
            if hasattr(self, 'canvas'):
                self.canvas.config(bg="#0f172a", highlightthickness=2, highlightbackground="#38bdf8")
            self.noactivate_ayarla()

    def tamponu_temizle(self):
        self.son_silinen_resim = None
        self.son_silinen_stroke_noktalari = []

    def stroke_noktalarindan_resim_uret(self, stroke_listesi):
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
            else:
                for i in range(1, len(pts)):
                    draw.line([pts[i - 1].x, pts[i - 1].y, pts[i].x, pts[i].y], fill="black", width=cizgi_w)
                    draw.ellipse([pts[i].x - r, pts[i].y - r, pts[i].x + r, pts[i].y + r], fill="black")
        return img

    def toggle_tam_ekran(self):
        self.tam_ekran_mi = not self.tam_ekran_mi
        self.tamponu_temizle()
        self.pencere_boyutunu_guncelle()
        w, h = self.mevcut_boyut()
        self.image = Image.new("RGB", (w, h), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.ekrani_temizle(yedekle=False)
        mod_adi = "Tam Ekran (Saydam)" if self.tam_ekran_mi else "Yüzen Mini Pad (PIP)"
        logger.info(f">> [Mod Değişti] {mod_adi}")

    def toggle_yazma_modu(self):
        if self.yazma_modu_aktif:
            self.yazma_modunu_kapat()
        else:
            self.yazma_modunu_ac()

    def yazma_modunu_ac(self):
        self.yazma_modu_aktif = True
        self.cizim_yapildi = False
        self.pencere_boyutunu_guncelle()
        self.ekrani_temizle(yedekle=False)
        self.root.deiconify()
        self.root.lift()
        if self.tam_ekran_mi:
            self.root.focus_force()
        self.butonlari_ciz()
        mod = "Tam Ekran" if self.tam_ekran_mi else "Yüzen Mini Pad"
        logger.info(f">> [{mod.upper()} AÇIK] Aktif Defter: {self.storage.aktif_defter_adi}")

    def yazma_modunu_kapat(self):
        self.yazma_modu_aktif = False
        self.root.withdraw()
        self.ekrani_temizle(yedekle=False)
        logger.info("<< [NOT PEDİ GİZLENDİ] Masaüstüne dönüldü.")

    def defter_sec(self, index):
        self.storage.defter_sec(index)
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def toggle_ai_modu(self, icon=None, item=None):
        if not self.config.gemini_api_key:
            self.alt_cubuk_gecici_mesaj("⚠️ Gemini API anahtarı girilmemiş (config.json veya GEMINI_API_KEY).", sure=3.5)
            self.config.ai_modu_aktif = False
            self.config.kaydet()
            if self.yazma_modu_aktif:
                self.butonlari_ciz()
            return

        if not self.config.ai_modu_aktif:
            # AI açılmak isteniyor: Onay verilmemişse kullanıcıya açık onay sor
            if not getattr(self.config, 'ai_onay_verildi', False):
                onay = self._ai_onay_iste()
                if not onay:
                    return
            else:
                self.config.ai_modu_aktif = True
                self.config.kaydet()
                logger.info(">> [Vision AI Modu] ⚡ Açık (Online Hibrit)")
                self.alt_cubuk_gecici_mesaj("⚡ AI Modu: Açık (Online Hibrit)", sure=2.0)
        else:
            # AI kapatılmak isteniyor
            self.config.ai_modu_aktif = False
            self.config.kaydet()
            logger.info(">> [Vision AI Modu] 💻 Kapalı (Sadece Çevrimdışı)")
            self.alt_cubuk_gecici_mesaj("💻 AI Modu: Kapalı (100% Çevrimdışı)", sure=2.0)

        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def otomatik_yapistir_degistir(self, icon=None, item=None):
        self.otomatik_yapistir = not self.otomatik_yapistir
        durum = "Açık" if self.otomatik_yapistir else "Kapalı"
        logger.info(f">> [Auto-Type] Otomatik Yapıştırma: {durum}")

    def otomatik_enter_degistir(self, icon=None, item=None):
        self.otomatik_enter = not self.otomatik_enter
        durum = "Açık (Dikkat: Mesaj/Form/Komut gönderebilir)" if self.otomatik_enter else "Kapalı (Güvenli - Yalnızca Deftere)"
        logger.info(f">> [Auto-Enter] Otomatik Enter Tuşu: {durum}")

    def cikis_hedefi_degistir(self, yeni_hedef=None):
        sirali_modlar = ["cift", "ekran", "txt"]
        if yeni_hedef in sirali_modlar:
            self.cikis_hedefi = yeni_hedef
        else:
            idx = sirali_modlar.index(self.cikis_hedefi) if self.cikis_hedefi in sirali_modlar else 0
            self.cikis_hedefi = sirali_modlar[(idx + 1) % len(sirali_modlar)]

        self.config.cikis_hedefi = self.cikis_hedefi
        self.config.kaydet()

        mesajlar = {
            "cift": "🎯 Çıkış Modu: Hem Ekran Hem TXT (Çift)",
            "ekran": "🖥️ Çıkış Modu: Sadece Ekran (İmlece Yaz)",
            "txt": "📝 Çıkış Modu: Sadece TXT (Sessiz Defter)"
        }
        msg = mesajlar.get(self.cikis_hedefi, "Çıkış Modu Değiştirildi")
        self.alt_cubuk_gecici_mesaj(msg, sure=2.2)
        logger.info(f">> [Çıkış Modu] {msg}")

        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def bekleme_suresi_ayarla(self, yeni_sure):
        try:
            val = float(yeni_sure)
            if val <= 0.05:
                self.bekleme_suresi = 0.0
            else:
                self.bekleme_suresi = max(0.4, min(val, 5.0))
            self.config.bekleme_suresi = self.bekleme_suresi
            self.config.kaydet()
            self.butonlari_ciz()
            if self.bekleme_suresi <= 0.0:
                self.alt_cubuk_gecici_mesaj("⏱️ Manuel Gönderim: Otomatik aktarım kapalı, [↵ Gönder] ile aktarılır.", sure=3.0)
                logger.info(">> [Bekleme Süresi] Manuel moda alındı.")
            else:
                self.alt_cubuk_gecici_mesaj(f"⏱️ Yazma bekleme süresi: {self.bekleme_suresi:.1f} sn", sure=2.5)
                logger.info(f">> [Bekleme Süresi] {self.bekleme_suresi:.1f} saniye olarak güncellendi.")
        except Exception as e:
            logger.error(f"Bekleme süresi ayar hatası: {e}")

    def dongu_bekleme_suresi(self):
        """Alt çubuktaki butona basıldığında bekleme süresini döngüsel değiştirir."""
        kademeler = [1.5, 2.5, 3.5, 5.0, 0.0]
        mevcut = self.bekleme_suresi
        yeni = 3.5
        for i, k in enumerate(kademeler):
            if abs(mevcut - k) < 0.2:
                yeni = kademeler[(i + 1) % len(kademeler)]
                break
        self.bekleme_suresi_ayarla(yeni)

    def toggle_navigasyon_jestleri(self):
        """Enter, Tab ve Geri Al gezinme jestlerini açar / kapatır."""
        suanki = getattr(self.config, 'navigasyon_jestleri_aktif', False)
        self.config.navigasyon_jestleri_aktif = not suanki
        self.config.kaydet()
        durum = "Açık (Enter ↵ / Tab ⇥)" if self.config.navigasyon_jestleri_aktif else "Kapalı (Güvenli Mod - 'S' vb. harfler korunur)"
        self.alt_cubuk_gecici_mesaj(f"✍️ Gezinme Jestleri: {durum}", sure=3.0)
        logger.info(f">> [Jest Ayarı] Navigasyon jestleri {durum} yapıldı.")

    def programi_kapat(self):
        logger.info("InkScribe Pro kapatılıyor...")
        if self.tray:
            self.tray.durdur()
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
        self.root.destroy()
        os._exit(0)

    def alt_cubuk_gecici_mesaj(self, mesaj, sure=2.2):
        """Alt çubukta uyarı gösterir (Toast). Pencere gizliyse masaüstü tepsi bildirimi gönderir."""
        pencere_gorunur = False
        try:
            pencere_gorunur = self.root.winfo_viewable() and self.yazma_modu_aktif
        except Exception:
            pencere_gorunur = False

        if not pencere_gorunur:
            self.tray.notify(mesaj, "InkScribe Pro")
            return

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
            self.canvas.create_rectangle(0, fy1, w, h_win, fill="#0b1120", outline="#ef4444", width=1, tags="toast_mesaj")
            self.canvas.create_text(
                14, fy1 + 22,
                text=mesaj,
                fill="#f87171", anchor="w", font=("Segoe UI", 9, "bold"), tags="toast_mesaj"
            )
        else:
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
        """Son silinen çizimi Canvas ve Ink container'a tek kullanımlık geri yükler."""
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

            if inking and self.stroke_builder:
                self.stroke_container = inking.InkStrokeContainer()
                self.tum_stroke_noktalari = [list(pts) for pts in self.son_silinen_stroke_noktalari]
                for pts in self.tum_stroke_noktalari:
                    try:
                        stroke = self.stroke_builder.create_stroke(pts)
                        self.stroke_container.add_stroke(stroke)
                    except Exception:
                        pass
            else:
                self.stroke_container = None
                self.tum_stroke_noktalari = [list(pts) for pts in self.son_silinen_stroke_noktalari]

            self.cizim_yapildi = True
            self.son_yazma_zamani = time.time()
            self.tamponu_temizle()
            self.butonlari_ciz()
            logger.info(">> [Geri Alındı] Son çizim tuvale geri yüklendi.")
        else:
            self.alt_cubuk_gecici_mesaj("⚠️ Geri alınacak çizim bulunamadı.")

    def butonlari_ciz(self):
        self.canvas.delete("ui_buton")
        w, h = self.mevcut_boyut()

        ad, _ = self.storage.defterler[self.storage.aktif_defter_index]
        defter_ikonlar = {
            "Genel": "📝",
            "Ders Notları": "📘",
            "Yapılacaklar": "✅",
            "Fikirler": "💡"
        }
        ikon = defter_ikonlar.get(ad, "📁")
        btn_defter_txt = f"{ikon} Not Defteri ({ad}) ▾"

        if self.tam_ekran_mi:
            btn_defter_w = max(200, len(btn_defter_txt) * 7 + 26)
            self._buton_ciz(25, 15, btn_defter_w, 32, btn_defter_txt, "#38bdf8", "toggle_defter_menu", bg_renk="#0f2b48", font_size=8)
            self._buton_ciz(w - 55, 15, 40, 32, "✕", "#ef4444", "kapat", bg_renk="#7f1d1d")
            self._buton_ciz(w - 105, 15, 42, 32, "⛶", "#94a3b8", "mod_degistir", bg_renk="#334155")
            self._buton_ciz(w - 155, 15, 42, 32, "↶", "#38bdf8", "geri_al", bg_renk="#0369a1")
            self._buton_ciz(w - 215, 15, 52, 32, "Temizle", "#f59e0b", "temizle", bg_renk="#78350f")
            self._buton_ciz(w - 295, 15, 72, 32, "↵ Gönder", "#34d399", "aninda_donustur", bg_renk="#064e3b")
            self._buton_ciz(w - 355, 15, 54, 32, "Tab ⇥", "#a78bfa", "tab_bas", bg_renk="#4c1d95")

            # Tam ekran çıkış modu butonu
            hedef = getattr(self, 'cikis_hedefi', 'cift')
            if hedef == "ekran":
                h_txt, h_renk, h_bg = "🖥️ Sadece Ekran", "#34d399", "#065f46"
            elif hedef == "txt":
                h_txt, h_renk, h_bg = "📝 Sadece TXT", "#fbbf24", "#78350f"
            else:
                h_txt, h_renk, h_bg = "🎯 Çift Mod", "#38bdf8", "#0369a1"
            self._buton_ciz(w - 505, 15, 140, 32, h_txt, h_renk, "toggle_cikis_hedefi", bg_renk=h_bg, font_size=8)

            if getattr(self, 'defter_menu_acik', False):
                self._defter_popup_ciz(25, 52, btn_defter_w)
            return

        # Yüzen Mini Pad Üst Başlık Çubuğu
        self.canvas.create_rectangle(0, 0, w, 42, fill="#1e293b", outline="", tags="ui_buton")
        self.canvas.create_text(
            14, 21,
            text="✍️ INKSCRIBE PRO",
            fill="#38bdf8", anchor="w", font=("Segoe UI", 9, "bold"), tags="ui_buton"
        )

        # Aktif Defter Açılır Menü Butonu (Dropdown - Başlıktan ferah mesafede başlar)
        btn_defter_x = 175
        btn_defter_w = max(195, len(btn_defter_txt) * 7 + 22)
        # Sıkışma önleyici güvenlik sınırı (sağ butonlara çarpmaması için)
        if btn_defter_x + btn_defter_w > w - 375:
            btn_defter_w = max(130, w - 375 - btn_defter_x)
        self._buton_ciz(btn_defter_x, 8, btn_defter_w, 26, btn_defter_txt, "#38bdf8", "toggle_defter_menu", bg_renk="#0f2b48", font_size=8)

        # Sağ Üst Aksiyon Butonları (Ferah, Dokunmatik Dostu Geniş Aralıklar)
        ai_icon = "⚡ AI: Açık" if self.config.ai_modu_aktif else "💻 AI: Kapalı"
        ai_bg = "#065f46" if self.config.ai_modu_aktif else "#374151"
        ai_renk = "#34d399" if self.config.ai_modu_aktif else "#9ca3af"

        self._buton_ciz(w - 42, 8, 32, 26, "✕", "#ef4444", "kapat", bg_renk="#7f1d1d", font_size=10)
        self._buton_ciz(w - 78, 8, 32, 26, "⛶", "#94a3b8", "mod_degistir", bg_renk="#334155", font_size=10)
        self._buton_ciz(w - 134, 8, 52, 26, "Temizle", "#f59e0b", "temizle", bg_renk="#78350f", font_size=8)
        self._buton_ciz(w - 168, 8, 30, 26, "↶", "#38bdf8", "geri_al", bg_renk="#0369a1", font_size=10)
        self._buton_ciz(w - 240, 8, 68, 26, "↵ Gönder", "#34d399", "aninda_donustur", bg_renk="#064e3b", font_size=8)
        self._buton_ciz(w - 316, 8, 72, 26, ai_icon, ai_renk, "toggle_ai", bg_renk=ai_bg, font_size=8)
        self._buton_ciz(w - 366, 8, 46, 26, "Tab ⇥", "#a78bfa", "tab_bas", bg_renk="#4c1d95", font_size=8)

        # Alt Bilgi Çubuğu
        fy1 = h - 44
        self.canvas.create_rectangle(0, fy1, w, h, fill="#0b1120", outline="#1e293b", width=1, tags="ui_buton")

        # Çıkış Modu Butonu (Alt Bar - Sağ Taraf)
        hedef = getattr(self, 'cikis_hedefi', 'cift')
        if hedef == "ekran":
            h_txt, h_renk, h_bg = "🖥️ Çıkış: Sadece Ekran", "#34d399", "#065f46"
        elif hedef == "txt":
            h_txt, h_renk, h_bg = "📝 Çıkış: Sadece TXT", "#fbbf24", "#78350f"
        else:
            h_txt, h_renk, h_bg = "🎯 Çıkış: Çift (Ekran+TXT)", "#38bdf8", "#0369a1"

        btn_cikis_w = 175
        self._buton_ciz(w - btn_cikis_w - 16, fy1 + 8, btn_cikis_w, 28, h_txt, h_renk, "toggle_cikis_hedefi", bg_renk=h_bg, font_size=8)

        # Bekleme Süresi Butonu (Alt Bar - Çıkış Modunun Solu)
        sure_txt = "⏱️ Manuel" if self.bekleme_suresi <= 0.05 else f"⏱️ {self.bekleme_suresi:.1f} sn"
        btn_sure_w = 95
        self._buton_ciz(w - btn_cikis_w - 16 - btn_sure_w - 8, fy1 + 8, btn_sure_w, 28, sure_txt, "#38bdf8", "dongu_bekleme_suresi", bg_renk="#0f2b48", font_size=8)

        sonlar = self.storage.son_satirlari_oku(2)
        if hedef == "ekran":
            onizleme_metni = "Defter kaydı duraklatıldı (Yalnızca ekrana yazılıyor)"
        else:
            onizleme_metni = "  |  ".join(sonlar) if sonlar else "Henüz bu deftere not alınmadı."

        # Sol altta metin ile butonların çakışmasını engellemek için sınırla
        max_chars = max(20, int((w - btn_cikis_w - btn_sure_w - 50) / 7.5))
        if len(onizleme_metni) > max_chars:
            onizleme_metni = onizleme_metni[:max_chars - 3] + "..."

        self.canvas.create_text(
            14, fy1 + 22,
            text=f"Son: {onizleme_metni}",
            fill="#64748b" if hedef != "ekran" else "#34d399", anchor="w", font=("Segoe UI", 9), tags="ui_buton"
        )

        # Yeniden Boyutlandırma Tutamacı (Sağ Alt Köşe)
        self.canvas.create_line(w - 6, h - 16, w - 16, h - 6, fill="#64748b", width=2, tags="ui_buton")
        self.canvas.create_line(w - 6, h - 11, w - 11, h - 6, fill="#64748b", width=2, tags="ui_buton")
        self.canvas.create_line(w - 6, h - 6, w - 6, h - 6, fill="#64748b", width=2, tags="ui_buton")

        # Defter Açılır Menüsü Açıksa En Üst Katmana Çiz
        if getattr(self, 'defter_menu_acik', False):
            self._defter_popup_ciz(btn_defter_x, 38, btn_defter_w)

    def _defter_popup_ciz(self, px, py, menu_genislik=None):
        """Aktif defteri değiştirmek ve defterler klasörünü yönetmek için şık açılır kart çizer."""
        pw = max(225, menu_genislik or 225)
        defterler = self.storage.defterler
        n = len(defterler)
        row_h = 28
        header_h = 24
        actions_h = 2 * 27 + 10
        total_h = header_h + n * row_h + actions_h + 10
        px2 = px + pw
        py2 = py + total_h

        # Gölge Efekti
        self.canvas.create_rectangle(
            px + 3, py + 3, px2 + 3, py2 + 3,
            fill="#020617", outline="", tags="ui_buton"
        )
        # Menü Arka Plan Kartı
        self.canvas.create_rectangle(
            px, py, px2, py2,
            fill="#0f172a", outline="#0284c7", width=2, tags="ui_buton"
        )
        # Kart Başlığı
        self.canvas.create_text(
            px + 12, py + 13,
            text="📓 NOT DEFTERLERİ (DEFTERLER/)", fill="#94a3b8", anchor="w",
            font=("Segoe UI", 7, "bold"), tags="ui_buton"
        )

        defter_ikonlar = {
            "Genel": "📝",
            "Ders Notları": "📘",
            "Yapılacaklar": "✅",
            "Fikirler": "💡"
        }

        # Defter Seçenekleri
        cur_y = py + header_h + 2
        for i, (ad, _) in enumerate(defterler):
            aktif = (i == self.storage.aktif_defter_index)
            kutu_bg = "#0284c7" if aktif else "#1e293b"
            yazi_renk = "#ffffff" if aktif else "#cbd5e1"
            ikon = defter_ikonlar.get(ad, "📁")
            isaret = "  ✓" if aktif else ""
            etiket = f"{ikon} Not Defteri ({ad}){isaret}"

            self._buton_ciz(
                px + 6, cur_y, pw - 12, 24,
                etiket, yazi_renk, f"defter_{i}",
                bg_renk=kutu_bg, font_size=8
            )
            cur_y += row_h

        # Ayraç Çizgisi
        self.canvas.create_line(px + 6, cur_y + 3, px2 - 6, cur_y + 3, fill="#334155", width=1, tags="ui_buton")
        cur_y += 7

        # 1. Buton: Seçili Dosyayı Aç
        self._buton_ciz(
            px + 6, cur_y, pw - 12, 24,
            "📂 Bu Defteri Aç (.txt)", "#38bdf8", "dosya_ac",
            bg_renk="#1e293b", font_size=8
        )
        cur_y += 27

        # 2. Buton: Defterler Klasörünü Aç
        self._buton_ciz(
            px + 6, cur_y, pw - 12, 24,
            "📁 Defterler Klasörünü Aç", "#34d399", "klasor_ac",
            bg_renk="#064e3b", font_size=8
        )

    def _buton_ciz(self, x, y, genislik, yukseklik, metin, renk, komut, bg_renk="#1e293b", font_size=9):
        tag = f"btn_{komut}"
        self.canvas.create_rectangle(
            x, y, x + genislik, y + yukseklik,
            fill=bg_renk, outline=renk, width=1,
            tags=("ui_buton", tag)
        )
        self.canvas.create_text(
            x + genislik // 2, y + yukseklik // 2,
            text=metin, fill=renk,
            font=("Segoe UI", font_size, "bold"),
            tags=("ui_buton", tag)
        )

    def buton_tiklandi_mi(self, x, y):
        items = self.canvas.find_withtag("current")
        for item in items:
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith("btn_"):
                    komut = tag.replace("btn_", "")
                    if komut == "toggle_defter_menu":
                        self.defter_menu_acik = not getattr(self, 'defter_menu_acik', False)
                        self.butonlari_ciz()
                        return True
                    elif komut.startswith("defter_"):
                        idx = int(komut.split("_")[1])
                        self.defter_sec(idx)
                        self.defter_menu_acik = False
                        self.butonlari_ciz()
                        return True
                    elif komut == "dosya_ac":
                        self.storage.notlar_dosyasini_ac()
                        self.defter_menu_acik = False
                        self.butonlari_ciz()
                        return True
                    elif komut == "klasor_ac":
                        self.storage.defterler_klasorunu_ac()
                        self.defter_menu_acik = False
                        self.butonlari_ciz()
                        return True
                    else:
                        if getattr(self, 'defter_menu_acik', False):
                            self.defter_menu_acik = False
                            self.butonlari_ciz()

                    if komut == "kapat":
                        self.yazma_modunu_kapat()
                    elif komut == "temizle":
                        self.ekrani_temizle(yedekle=True)
                    elif komut == "geri_al":
                        self.geri_al()
                    elif komut == "aninda_donustur":
                        self.aninda_donustur()
                    elif komut == "dongu_bekleme_suresi":
                        self.dongu_bekleme_suresi()
                    elif komut == "tab_bas":
                        threading.Thread(target=self._arka_planda_tab_bas, args=(1,), daemon=True).start()
                        self.alt_cubuk_gecici_mesaj("⇥ Tab tuşu basıldı.")
                    elif komut == "mod_degistir":
                        self.toggle_tam_ekran()
                    elif komut == "toggle_ai":
                        self.toggle_ai_modu()
                    elif komut == "toggle_cikis_hedefi":
                        self.cikis_hedefi_degistir()
                    return True
        return False

    def ekrani_temizle(self, yedekle=True):
        if self.debounce_timer_id:
            try:
                self.root.after_cancel(self.debounce_timer_id)
            except Exception:
                pass
            self.debounce_timer_id = None

        if yedekle and self.cizim_yapildi and self.tum_stroke_noktalari:
            self.son_silinen_resim = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
            self.son_silinen_stroke_noktalari = [list(pts) for pts in self.tum_stroke_noktalari]

        self.canvas.delete("all")
        self.canvas_bg_photo = None
        w, h = self.mevcut_boyut()
        self.image = Image.new("RGB", (w, h), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.stroke_container = inking.InkStrokeContainer() if inking else None
        if getattr(self, 'titreme_filtresi', None):
            self.titreme_filtresi.sifirla()
        self.tum_stroke_noktalari = []
        self.cizim_yapildi = False
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def fare_basildi(self, event):
        if self.buton_tiklandi_mi(event.x, event.y):
            return

        if getattr(self, 'defter_menu_acik', False):
            self.defter_menu_acik = False
            self.butonlari_ciz()
            if event.y <= 270 and 170 <= event.x <= 415:
                return

        w, h = self.mevcut_boyut()

        # Boyutlandırma kontrolü (Sağ alt köşe 25x25)
        if not self.tam_ekran_mi and event.x >= w - 25 and event.y >= h - 25:
            self.boyutlandiriliyor = True
            self._resize_start_x = event.x_root
            self._resize_start_y = event.y_root
            self._orig_w = self.pad_genislik
            self._orig_h = self.pad_yukseklik
            return

        # Üst bar sürükleme kontrolü (y <= 42)
        if not self.tam_ekran_mi and event.y <= 42:
            self.surukleniyor = True
            self._drag_start_x = event.x_root
            self._drag_start_y = event.y_root
            self._win_start_x = self.root.winfo_x()
            self._win_start_y = self.root.winfo_y()
            return

        # Alt çubuk tıklama engeli
        if not self.tam_ekran_mi and event.y >= h - 44:
            return

        # Mini pad modunda klavye kısayollarının (Esc, Enter, Ctrl+Z) çalışabilmesi için iç odak ver
        try:
            self.canvas.focus_set()
        except Exception:
            pass

        # Vuruş başladığında aktif debounce zamanlayıcısını durdur
        if self.debounce_timer_id:
            try:
                self.root.after_cancel(self.debounce_timer_id)
            except Exception:
                pass
            self.debounce_timer_id = None

        # Aktif hedef pencereyi kaydet (NoActivate modunda dahi tuş gönderebilmek için)
        if user32:
            try:
                cur_hwnd = user32.GetForegroundWindow()
                my_hwnd = self.root.winfo_id()
                parent_hwnd = user32.GetParent(my_hwnd) if my_hwnd else None
                if cur_hwnd and cur_hwnd not in (my_hwnd, parent_hwnd):
                    self.son_hedef_hwnd = cur_hwnd
            except Exception:
                pass

        self.kalem_basili = True
        tf = getattr(self, 'titreme_filtresi', None)
        pt = tf.baslat(event.x, event.y) if tf else Point(float(event.x), float(event.y))
        self.son_x, self.son_y = pt.x, pt.y
        self.son_yazma_zamani = time.time()
        self.stroke_baslangic_zamani = time.time()

        self.aktif_noktalar = [Point(float(pt.x), float(pt.y))]

        r = 1.5 if not self.tam_ekran_mi else 2.5
        self.draw.ellipse([pt.x - r, pt.y - r, pt.x + r, pt.y + r], fill="black")

    def fare_hareket(self, event):
        if self.boyutlandiriliyor:
            dw = event.x_root - self._resize_start_x
            dh = event.y_root - self._resize_start_y
            self.pad_genislik = max(680, self._orig_w + dw)
            self.pad_yukseklik = max(280, self._orig_h + dh)
            self.root.geometry(f"{self.pad_genislik}x{self.pad_yukseklik}+{self.pad_x}+{self.pad_y}")
            return

        if self.surukleniyor:
            dx = event.x_root - self._drag_start_x
            dy = event.y_root - self._drag_start_y
            self.pad_x = self._win_start_x + dx
            self.pad_y = self._win_start_y + dy
            self.root.geometry(f"{self.pad_genislik}x{self.pad_yukseklik}+{self.pad_x}+{self.pad_y}")
            return

        if not self.kalem_basili:
            return

        # Titreme Filtresi: Mikro sensör parazitlerini eler, hareketi pürüzsüzleştirir
        tf = getattr(self, 'titreme_filtresi', None)
        pt = tf.filtrele(event.x, event.y) if tf else Point(float(event.x), float(event.y))
        if pt is None:
            return

        cizgi_w = 3 if not self.tam_ekran_mi else 5
        r = 1.5 if not self.tam_ekran_mi else 2.5

        if self.son_x is not None and self.son_y is not None:
            self.canvas.create_line(
                self.son_x, self.son_y, pt.x, pt.y,
                fill="#00ffcc", width=cizgi_w, capstyle=tk.ROUND, joinstyle=tk.ROUND, smooth=True,
                tags=("cizim", "stroke_current")
            )
            self.draw.line([self.son_x, self.son_y, pt.x, pt.y], fill="black", width=cizgi_w)
            self.draw.ellipse([pt.x - r, pt.y - r, pt.x + r, pt.y + r], fill="black")

            self.aktif_noktalar.append(Point(float(pt.x), float(pt.y)))

        self.son_x, self.son_y = pt.x, pt.y
        self.son_yazma_zamani = time.time()

    def jestleri_kontrol_et(self):
        # 1. Karalama ile Silme Jesti (Scratch-out - Her zaman güvenli jest)
        if getattr(self.config, 'karalama_silme_aktif', True) and karalama_jesti_mi(self.aktif_noktalar):
            logger.info(">> [JEST] Karalama: Ekran temizlendi! (Geri almak için ↶ butonu)")
            self.canvas.delete("stroke_current")
            self.aktif_noktalar = []
            if self.tum_stroke_noktalari:
                self.son_silinen_resim = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
                self.son_silinen_stroke_noktalari = [list(pts) for pts in self.tum_stroke_noktalari]
            self.ekrani_temizle(yedekle=False)
            return True

        # Gezinme jestleri (Enter ↵, Tab ⇥, Geri Al ←) el yazısı harfleriyle ('S', 'l', '1', '-')
        # karışmaması için varsayılan olarak kapalıdır; yalnızca kullanıcı açtığında çalışır.
        if not getattr(self.config, 'navigasyon_jestleri_aktif', False):
            return False

        gecen_sure = time.time() - self.stroke_baslangic_zamani

        # 2. Enter / Yeni Satır Jesti (Öncelikli: Enter Kancası ↵, Yedek: Dikey Fiske)
        scale = getattr(self, 'dpi_scale', 1.0)
        dy_min = int(70 * scale)
        dx_max = int(45 * scale)

        enter_tetiklendi = False
        jest_adi = ""

        if enter_kancasi_jesti_mi(self.aktif_noktalar, gecen_sure, scale=scale):
            enter_tetiklendi = True
            jest_adi = "Enter Kancası (↵)"
        elif dikey_cizgi_jesti_mi(self.aktif_noktalar, gecen_sure, dy_min=dy_min, dx_max=dx_max):
            enter_tetiklendi = True
            jest_adi = "Dikey Çizgi"

        if enter_tetiklendi:
            logger.info(f">> [JEST] {jest_adi}: Enter (Yeni Satır)!")
            self.canvas.delete("stroke_current")
            self.aktif_noktalar = []

            # Görüntüdeki jest izini derhal sil ve yalnızca onaylanmış vuruşları koru
            self.image = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
            self.draw = ImageDraw.Draw(self.image)

            onceki_yazi_var = bool(self.tum_stroke_noktalari)

            if self.isleniyor:
                # Arka planda dönüşüm sürerken jest çekildi: sadece yeni satırı sıraya al
                self.bekleyen_yeni_satir += 1
                logger.info(f">> [JEST] Dönüşüm sürerken {jest_adi}: Yeni satır kuyruğa eklendi.")
                return True

            if onceki_yazi_var:
                # Tuvalde halihazırda yazılmış metin var:
                self.bekleyen_yeni_satir += 1
                logger.info(f">> [JEST] Yazılmış metin tespit edildi; önce metin dönüştürülecek, ardından {jest_adi} basılacak.")
                self.tetikle_donusturme()
            else:
                # Tuval boştu: doğrudan yeni satır ekle ve hedef pencereye Enter bas
                self.bekleyen_yeni_satir += 1
                adet = self.bekleyen_yeni_satir
                self.bekleyen_yeni_satir = 0
                yaz_ekrana = getattr(self, 'cikis_hedefi', 'cift') in ("cift", "ekran")
                kaydet_txt = getattr(self, 'cikis_hedefi', 'cift') in ("cift", "txt")
                if kaydet_txt:
                    for _ in range(adet):
                        self.storage.yeni_satir_ekle()
                if yaz_ekrana:
                    threading.Thread(target=self._arka_planda_enter_bas, args=(adet,), daemon=True).start()
                self.ekrani_temizle(yedekle=False)

            return True

        # 2. Geri Al Jesti (Sağdan Sola Yatay Çizgi ←)
        if sagdan_sola_cizgi_jesti_mi(self.aktif_noktalar, gecen_sure, scale=scale):
            logger.info(">> [JEST] Sağdan Sola Çizgi (←): Geri Al (Undo)!")
            self.canvas.delete("stroke_current")
            self.aktif_noktalar = []

            # Görüntüdeki jest izini sil
            self.image = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
            self.draw = ImageDraw.Draw(self.image)

            # Durum 1: Tuvalde aktif çizim varsa son vuruşu geri al
            if self.tum_stroke_noktalari:
                self.tum_stroke_noktalari.pop()
                self.image = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
                self.draw = ImageDraw.Draw(self.image)

                # Tuvali baştan çiz
                self.canvas.delete("cizim")
                cizgi_w = 3 if not self.tam_ekran_mi else 5
                for stroke in self.tum_stroke_noktalari:
                    for i in range(1, len(stroke)):
                        p1, p2 = stroke[i - 1], stroke[i]
                        self.canvas.create_line(
                            p1.x, p1.y, p2.x, p2.y,
                            fill="#00ffcc", width=cizgi_w, capstyle=tk.ROUND, joinstyle=tk.ROUND, smooth=True,
                            tags="cizim"
                        )

                # Windows Ink container senkronizasyonu
                if inking and self.stroke_builder:
                    self.stroke_container = inking.InkStrokeContainer()
                    for stroke in self.tum_stroke_noktalari:
                        try:
                            s = self.stroke_builder.create_stroke(stroke)
                            self.stroke_container.add_stroke(s)
                        except Exception:
                            pass

                if not self.tum_stroke_noktalari:
                    self.cizim_yapildi = False
                    if self.debounce_timer_id:
                        try:
                            self.root.after_cancel(self.debounce_timer_id)
                        except Exception:
                            pass
                        self.debounce_timer_id = None
                else:
                    self._debounce_kur()

                self.alt_cubuk_gecici_mesaj("↶ Son çizgi geri alındı.")
                logger.info(">> [Geri Al] Tuvaldeki son çizim vuruşu geri alındı.")
                return True

            # Durum 2: Tuvalde aktif çizim yoksa silinmiş çizimi geri yükle (veya aktif uygulamada Ctrl+Z)
            if getattr(self, 'son_silinen_resim', None):
                self.geri_al()
            else:
                threading.Thread(target=self._arka_planda_ctrl_z_bas, daemon=True).start()
                self.alt_cubuk_gecici_mesaj("↶ Geri Al (Ctrl + Z)")

            return True

        # 3. Tab Jesti (Soldan Sağa Yatay Çizgi →)
        if soldan_saga_cizgi_jesti_mi(self.aktif_noktalar, gecen_sure, scale=scale):
            logger.info(">> [JEST] Soldan Sağa Çizgi (→): Tab Tuşu!")
            self.canvas.delete("stroke_current")
            self.aktif_noktalar = []

            self.image = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
            self.draw = ImageDraw.Draw(self.image)

            onceki_yazi_var = bool(self.tum_stroke_noktalari)

            if self.isleniyor:
                self.bekleyen_tab += 1
                logger.info(">> [JEST] Dönüşüm sürerken Tab: Kuyruğa eklendi.")
                return True

            if onceki_yazi_var:
                self.bekleyen_tab += 1
                logger.info(">> [JEST] Yazılmış metin tespit edildi; önce metin dönüştürülecek, ardından Tab basılacak.")
                self.tetikle_donusturme()
            else:
                threading.Thread(target=self._arka_planda_tab_bas, args=(1,), daemon=True).start()
                self.alt_cubuk_gecici_mesaj("⇥ Tab tuşu basıldı.")

            return True

        return False

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
        if getattr(self, 'titreme_filtresi', None):
            self.titreme_filtresi.sifirla()
        self.son_x, self.son_y = None, None
        self.son_yazma_zamani = time.time()

        if self.jestleri_kontrol_et():
            self.aktif_noktalar = []
            return

        # Jest değil, normal çizim vuruşu: "stroke_current" etiketini kalıcı çizime çevir
        self.canvas.dtag("stroke_current")

        # Tekil dokunuşları güçlendir (nokta / tırnak / virgül)
        if len(self.aktif_noktalar) == 1:
            p = self.aktif_noktalar[0]
            self.aktif_noktalar = [
                Point(p.x, p.y),
                Point(p.x + 1.0, p.y + 1.0),
                Point(p.x, p.y + 2.0)
            ]
        elif len(self.aktif_noktalar) == 2:
            p1 = self.aktif_noktalar[0]
            p2 = self.aktif_noktalar[1]
            if abs(p1.x - p2.x) < 2 and abs(p1.y - p2.y) < 2:
                self.aktif_noktalar.append(Point(p2.x + 1.0, p2.y + 1.0))

        if len(self.aktif_noktalar) >= 2:
            if self.stroke_builder and self.stroke_container:
                try:
                    stroke = self.stroke_builder.create_stroke(self.aktif_noktalar)
                    self.stroke_container.add_stroke(stroke)
                except Exception as e:
                    logger.error(f"[Stroke Hatası]: {e}")
            self.tum_stroke_noktalari.append(list(self.aktif_noktalar))
            self.cizim_yapildi = True

        self.aktif_noktalar = []

        # Otomatik dönüştürme için olay tabanlı debounce zamanlayıcısı kur (Sıfır boşta CPU)
        self._debounce_kur()

    def _debounce_kur(self):
        """Çizim yapılmışsa ve arka planda aktif dönüşüm yoksa otomatik dönüştürme zamanlayıcısını kurar."""
        if self.debounce_timer_id:
            try:
                self.root.after_cancel(self.debounce_timer_id)
            except Exception:
                pass
            self.debounce_timer_id = None

        if self.cizim_yapildi and not self.isleniyor:
            if self.bekleme_suresi <= 0.05:
                # Manuel mod: otomatik dönüştürme zamanlayıcısı kurulmaz, [↵ Gönder] beklenir
                return
            gecen = time.time() - getattr(self, 'son_yazma_zamani', time.time())
            kalan_ms = int(max(0.06, self.bekleme_suresi - gecen) * 1000)
            self.debounce_timer_id = self.root.after(
                kalan_ms, self._otomatik_donustur_tetikle
            )

    def _otomatik_donustur_tetikle(self):
        self.debounce_timer_id = None
        if self.yazma_modu_aktif and self.cizim_yapildi and not self.kalem_basili and not self.isleniyor and not self.surukleniyor:
            self.tetikle_donusturme()

    def aninda_donustur(self):
        if not self.isleniyor:
            if not self.cizim_yapildi:
                yaz_ekrana = getattr(self, 'cikis_hedefi', 'cift') in ("cift", "ekran")
                kaydet_txt = getattr(self, 'cikis_hedefi', 'cift') in ("cift", "txt")
                if kaydet_txt:
                    self.storage.yeni_satir_ekle()
                if yaz_ekrana:
                    threading.Thread(target=self._arka_planda_enter_bas, args=(1,), daemon=True).start()
                self.alt_cubuk_gecici_mesaj("↵ Yeni satıra geçildi.", sure=1.5)
            else:
                self.tetikle_donusturme()

    def tetikle_donusturme(self):
        if self.debounce_timer_id:
            try:
                self.root.after_cancel(self.debounce_timer_id)
            except Exception:
                pass
            self.debounce_timer_id = None

        if not self.cizim_yapildi:
            return

        strokes_to_process = self.stroke_container
        ters_resim = ImageChops.invert(self.image)
        bbox = ters_resim.getbbox()

        if bbox:
            self.isleniyor = True
            islem_resmi = self.image.copy()

            if self.tam_ekran_mi:
                self.yazma_modu_aktif = False
                self.root.withdraw()

            self.tamponu_temizle()
            self.ekrani_temizle(yedekle=False)
            threading.Thread(target=self.metne_donustur, args=(strokes_to_process, islem_resmi, bbox), daemon=True).start()
        else:
            self.cizim_yapildi = False

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

            kw, kh = kirpilmis.size
            if kh < 120:
                scale = 135.0 / max(1, kh)
                target_w = max(60, int(kw * scale))
                target_h = 135
                kirpilmis = kirpilmis.resize((target_w, target_h), Image.Resampling.LANCZOS)

            if DEBUG_KAYDET:
                kirpilmis.save(os.path.join(APP_DIR, "debug_son_cizim.png"))

            metin = self.engine.recognize(stroke_container, kirpilmis, self.config)

            if metin:
                metin_bulundu = True
                logger.info(f">> [DÖNÜŞÜM BAŞARILI]: {len(metin)} karakter aktarılıyor.")
                self.root.after(0, lambda: self.panoya_ve_dosyaya_aktar(metin))
            else:
                logger.warning("[Uyarı] Metin algılanamadı.")

        except Exception as e:
            logger.error(f"[Tanıma Hatası]: {e}")
            self.root.after(0, lambda: self.alt_cubuk_gecici_mesaj("⚠️ Tanıma sırasında bir hata oluştu."))
        finally:
            if not metin_bulundu:
                self.root.after(0, self._donusturme_tamamlandi_bos)

    def _donusturme_tamamlandi_bos(self):
        """Metin algılanamadığında veya hata durumunda ana UI thread'inde güvenle çalışır."""
        self.isleniyor = False
        yaz_ekrana = getattr(self, 'cikis_hedefi', 'cift') in ("cift", "ekran")
        kaydet_txt = getattr(self, 'cikis_hedefi', 'cift') in ("cift", "txt")

        if self.bekleyen_yeni_satir > 0:
            adet = self.bekleyen_yeni_satir
            self.bekleyen_yeni_satir = 0
            if kaydet_txt:
                for _ in range(adet):
                    self.storage.yeni_satir_ekle()
            if yaz_ekrana:
                threading.Thread(target=self._arka_planda_enter_bas, args=(adet,), daemon=True).start()
        if self.bekleyen_tab > 0:
            adet = self.bekleyen_tab
            self.bekleyen_tab = 0
            if yaz_ekrana:
                threading.Thread(target=self._arka_planda_tab_bas, args=(adet,), daemon=True).start()
        self._debounce_kur()

    def panoya_ve_dosyaya_aktar(self, metin):
        try:
            yaz_ekrana = getattr(self, 'cikis_hedefi', 'cift') in ("cift", "ekran")
            kaydet_txt = getattr(self, 'cikis_hedefi', 'cift') in ("cift", "txt")

            pano_basarili = False
            if yaz_ekrana:
                # Aktif uygulamaya yapıştırırken kelimelerin birbirine yapışmasını önlemek için sonuna boşluk ekle
                yapistirilacak = metin if metin.endswith((" ", "\n", "\t")) else (metin + " ")

                for _ in range(3):
                    try:
                        self.root.clipboard_clear()
                        self.root.clipboard_append(yapistirilacak)
                        self.root.update()
                        pano_basarili = True
                        logger.info(">> [Pano] Metin panoya kopyalandı! (Ctrl + V)")
                        break
                    except Exception:
                        time.sleep(0.04)

                if not pano_basarili:
                    logger.error("[Pano Hatası] Metin panoya yazılamadı! Güvenlik nedeniyle otomatik yapıştırma atlandı.")
                    self.alt_cubuk_gecici_mesaj("⚠️ Pano kopyalanamadı! Yapıştırma iptal edildi.")

            if kaydet_txt:
                self.storage.metin_kaydet(metin)

            enter_adet = self.bekleyen_yeni_satir
            self.bekleyen_yeni_satir = 0
            tab_adet = self.bekleyen_tab
            self.bekleyen_tab = 0
            self.isleniyor = False

            if kaydet_txt and enter_adet > 0:
                for _ in range(enter_adet):
                    self.storage.yeni_satir_ekle()

            if self.yazma_modu_aktif:
                self.root.after(0, self.butonlari_ciz)

            if yaz_ekrana:
                # Kullanıcı jest yaptıysa enter_adet basılır. Genel otomatik_enter açıksa en az 1 enter basılır.
                gonderilecek_enter = enter_adet + (1 if (self.otomatik_enter and enter_adet == 0) else 0)
                if self.otomatik_yapistir and pano_basarili:
                    threading.Thread(target=self._arka_planda_yapistir_ve_enter, args=(gonderilecek_enter, tab_adet), daemon=True).start()
                else:
                    if gonderilecek_enter > 0:
                        threading.Thread(target=self._arka_planda_enter_bas, args=(gonderilecek_enter,), daemon=True).start()
                    if tab_adet > 0:
                        threading.Thread(target=self._arka_planda_tab_bas, args=(tab_adet,), daemon=True).start()

        finally:
            self.isleniyor = False
            self.root.after(0, self._debounce_kur)

    def _arka_planda_enter_bas(self, adet=1):
        if keyboard is None:
            return
        time.sleep(0.05)
        try:
            if user32 and self.son_hedef_hwnd and user32.IsWindow(self.son_hedef_hwnd):
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

    def _arka_planda_yapistir_ve_enter(self, enter_adet=0, tab_adet=0):
        if keyboard is None:
            return
        time.sleep(0.12)
        try:
            if user32 and self.son_hedef_hwnd and user32.IsWindow(self.son_hedef_hwnd):
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

            if tab_adet > 0:
                time.sleep(0.06)
                for _ in range(tab_adet):
                    kb.press(keyboard.Key.tab)
                    kb.release(keyboard.Key.tab)
                    time.sleep(0.03)
                logger.info(f">> [Auto-Type] Bekleyen {tab_adet} adet için Tab tuşu basıldı.")
        except Exception as e:
            logger.error(f"Auto-Type / Enter / Tab Hatası: {e}")

    def _arka_planda_tab_bas(self, adet=1):
        if keyboard is None:
            return
        time.sleep(0.05)
        try:
            if user32 and self.son_hedef_hwnd and user32.IsWindow(self.son_hedef_hwnd):
                user32.SetForegroundWindow(self.son_hedef_hwnd)
                time.sleep(0.05)
            kb = keyboard.Controller()
            for _ in range(adet):
                kb.press(keyboard.Key.tab)
                kb.release(keyboard.Key.tab)
                time.sleep(0.03)
            logger.info(f">> [Auto-Tab] Hedef uygulamaya {adet} adet Tab tuşu basıldı.")
        except Exception as e:
            logger.error(f"Auto-Tab Hatası: {e}")

    def _arka_planda_ctrl_z_bas(self):
        if keyboard is None:
            return
        time.sleep(0.05)
        try:
            if user32 and self.son_hedef_hwnd and user32.IsWindow(self.son_hedef_hwnd):
                user32.SetForegroundWindow(self.son_hedef_hwnd)
                time.sleep(0.05)
            kb = keyboard.Controller()
            with kb.pressed(keyboard.Key.ctrl):
                kb.press('z')
                kb.release('z')
            logger.info(">> [Auto-Undo] Hedef uygulamaya Ctrl + Z gönderildi.")
        except Exception as e:
            logger.error(f"Auto-Undo Hatası: {e}")


def main():
    setup_logging(APP_DIR)
    root = tk.Tk()
    app = ArkaPlanNotDonusturucu(root)
    root.mainloop()


if __name__ == "__main__":
    main()
