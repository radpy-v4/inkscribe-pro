import tkinter as tk
from PIL import Image, ImageDraw, ImageChops, ImageTk
import threading
import time
import os
import ctypes
try:
    from pynput import keyboard
except ImportError:
    keyboard = None
try:
    import winrt.windows.ui.input.inking as inking
    import winrt.windows.foundation as foundation
    Point = foundation.Point
except ImportError:
    inking = None
    foundation = None
    class Point:
        def __init__(self, x, y):
            self.x = float(x)
            self.y = float(y)


from .config import APP_DIR, DEBUG_KAYDET, logger, ConfigManager
from .gestures import karalama_jesti_mi, dikey_cizgi_jesti_mi
from .storage import NotebookManager
from .engine import RecognitionEngine
from .tray import TrayManager

user32 = ctypes.windll.user32


class ArkaPlanNotDonusturucu:
    """Grafik tabletler ve dokunmatik ekranlar için çift modlu el yazısı arayüzü ve iş akışı kontrolcüsü."""

    def __init__(self, root):
        self.root = root

        # Modüller
        self.config = ConfigManager(APP_DIR)
        self.storage = NotebookManager(APP_DIR)
        self.engine = RecognitionEngine()
        self.tray = TrayManager(self)

        # Ekran boyutları
        self.ekran_genislik = self.root.winfo_screenwidth()
        self.ekran_yukseklik = self.root.winfo_screenheight()

        # Çift Mod Ayarları: Yüzen Mini Pad (Varsayılan) ve Tam Ekran
        self.tam_ekran_mi = False
        self.pad_genislik = 880
        self.pad_yukseklik = 420
        self.pad_x = max(20, self.ekran_genislik - 910)
        self.pad_y = max(20, self.ekran_yukseklik - 480)
        self.boyutlandiriliyor = False

        # Başlangıç pencere konfigürasyonu
        self.root.overrideredirect(True)
        self.root.lift()
        self.root.wm_attributes("-topmost", True)
        self.pencere_boyutunu_guncelle()

        # Windows Ink Vuruş Konteynerleri
        self.stroke_builder = inking.InkStrokeBuilder() if inking else None
        self.stroke_container = inking.InkStrokeContainer() if inking else None
        self.aktif_noktalar = []
        self.tum_stroke_noktalari = []
        self.stroke_baslangic_zamani = 0

        # Zamanlayıcı ve durum bayrakları
        self.son_yazma_zamani = time.time()
        self.bekleme_suresi = 0.65
        self.kalem_basili = False
        self.isleniyor = False
        self.yazma_modu_aktif = False
        self.surukleniyor = False
        self.cizim_yapildi = False
        self.bekleyen_yeni_satir = 0

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

        if keyboard is not None:
            self.hotkey_listener = keyboard.GlobalHotKeys({
                '<f8>': _f8_tetiklendi,
                '<f9>': lambda: self.root.after(0, self.toggle_tam_ekran)
            })
            self.hotkey_listener.start()
        else:
            self.hotkey_listener = None

        # Sistem Tepsisi
        self.tray.baslat()

        logger.info("[3/3] Dinleyici aktif!")
        logger.info("      [F8] = Not Pedini Göster/Gizle")
        logger.info("      [F9] = Yüzen Mini Pad / Tam Ekran Değiştir")
        logger.info("      [↶ / Ctrl+Z] = Silinen Çizimi Geri Al")
        logger.info("      Jestler: Karalama = Temizle, Dikey Çizgi = Enter / Yeni Satır.")

        # Arka Plan Zamanlayıcısı
        threading.Thread(target=self.zamanlayici_dongusu, daemon=True).start()

    def noactivate_ayarla(self):
        """Mini Pad modunda klavye odağını çalmayı engeller (WS_EX_NOACTIVATE)."""
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
        self.config.ai_modu_aktif = not self.config.ai_modu_aktif
        self.config.kaydet()
        durum = "⚡ Açık (Online Hibrit)" if self.config.ai_modu_aktif else "💻 Kapalı (Sadece Çevrimdışı)"
        logger.info(f">> [Vision AI Modu] {durum}")
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

    def programi_kapat(self):
        logger.info("Tablet Not Alıcı kapatılıyor...")
        self.tray.durdur()
        self.hotkey_listener.stop()
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
            self.tray.notify(mesaj, "VEIKK Not Alıcı Pro")
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

        if self.tam_ekran_mi:
            self._buton_ciz(w - 55, 15, 40, 32, "✕", "#ef4444", "kapat", bg_renk="#7f1d1d")
            self._buton_ciz(w - 105, 15, 42, 32, "⛶", "#94a3b8", "mod_degistir", bg_renk="#334155")
            self._buton_ciz(w - 155, 15, 42, 32, "↶", "#38bdf8", "geri_al", bg_renk="#0369a1")
            self._buton_ciz(w - 215, 15, 52, 32, "Temizle", "#f59e0b", "temizle", bg_renk="#78350f")
            return

        # Yüzen Mini Pad Üst Başlık Çubuğu
        self.canvas.create_rectangle(0, 0, w, 42, fill="#1e293b", outline="", tags="ui_buton")
        self.canvas.create_text(
            14, 21,
            text="✍️ INKSCRIBE PRO",
            fill="#38bdf8", anchor="w", font=("Segoe UI", 10, "bold"), tags="ui_buton"
        )

        bx = 160
        for i, (ad, _) in enumerate(self.storage.defterler):
            aktif = (i == self.storage.aktif_defter_index)
            kutu_bg = "#0284c7" if aktif else "#334155"
            yazi_renk = "#ffffff" if aktif else "#94a3b8"
            bw = len(ad) * 8 + 16
            self._buton_ciz(bx, 8, bw, 26, ad, yazi_renk, f"defter_{i}", bg_renk=kutu_bg, font_size=8)
            bx += bw + 6

        # Sağ Üst Aksiyon Butonları
        ai_icon = "⚡ AI: Açık" if self.config.ai_modu_aktif else "💻 AI: Kapalı"
        ai_bg = "#065f46" if self.config.ai_modu_aktif else "#374151"
        ai_renk = "#34d399" if self.config.ai_modu_aktif else "#9ca3af"
        self._buton_ciz(w - 280, 8, 75, 26, ai_icon, ai_renk, "toggle_ai", bg_renk=ai_bg, font_size=8)

        self._buton_ciz(w - 195, 8, 32, 26, "↶", "#38bdf8", "geri_al", bg_renk="#0369a1", font_size=10)
        self._buton_ciz(w - 155, 8, 55, 26, "Temizle", "#f59e0b", "temizle", bg_renk="#78350f", font_size=8)
        self._buton_ciz(w - 92, 8, 36, 26, "⛶", "#94a3b8", "mod_degistir", bg_renk="#334155", font_size=10)
        self._buton_ciz(w - 48, 8, 36, 26, "✕", "#ef4444", "kapat", bg_renk="#7f1d1d", font_size=10)

        # Alt Bilgi Çubuğu
        fy1 = h - 44
        self.canvas.create_rectangle(0, fy1, w, h, fill="#0b1120", outline="#1e293b", width=1, tags="ui_buton")

        sonlar = self.storage.son_satirlari_oku(2)
        onizleme_metni = "  |  ".join(sonlar) if sonlar else "Henüz bu deftere not alınmadı."
        self.canvas.create_text(
            14, fy1 + 22,
            text=f"Son: {onizleme_metni}",
            fill="#64748b", anchor="w", font=("Segoe UI", 9), tags="ui_buton"
        )

        # Yeniden Boyutlandırma Tutamacı (Sağ Alt Köşe)
        self.canvas.create_line(w - 6, h - 16, w - 16, h - 6, fill="#64748b", width=2, tags="ui_buton")
        self.canvas.create_line(w - 6, h - 11, w - 11, h - 6, fill="#64748b", width=2, tags="ui_buton")
        self.canvas.create_line(w - 6, h - 6, w - 6, h - 6, fill="#64748b", width=2, tags="ui_buton")

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
                    if komut == "kapat":
                        self.yazma_modunu_kapat()
                    elif komut == "temizle":
                        self.ekrani_temizle(yedekle=True)
                    elif komut == "geri_al":
                        self.geri_al()
                    elif komut == "mod_degistir":
                        self.toggle_tam_ekran()
                    elif komut == "toggle_ai":
                        self.toggle_ai_modu()
                    elif komut.startswith("defter_"):
                        idx = int(komut.split("_")[1])
                        self.defter_sec(idx)
                    return True
        return False

    def ekrani_temizle(self, yedekle=True):
        if yedekle and self.cizim_yapildi and self.tum_stroke_noktalari:
            self.son_silinen_resim = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
            self.son_silinen_stroke_noktalari = [list(pts) for pts in self.tum_stroke_noktalari]

        self.canvas.delete("all")
        self.canvas_bg_photo = None
        w, h = self.mevcut_boyut()
        self.image = Image.new("RGB", (w, h), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.stroke_container = inking.InkStrokeContainer() if inking else None
        self.tum_stroke_noktalari = []
        self.cizim_yapildi = False
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def fare_basildi(self, event):
        if self.buton_tiklandi_mi(event.x, event.y):
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

        self.kalem_basili = True
        self.cizim_yapildi = True
        self.son_x, self.son_y = event.x, event.y
        self.son_yazma_zamani = time.time()
        self.stroke_baslangic_zamani = time.time()

        self.aktif_noktalar = [Point(float(event.x), float(event.y))]

        r = 1.5 if not self.tam_ekran_mi else 2.5
        self.draw.ellipse([event.x - r, event.y - r, event.x + r, event.y + r], fill="black")

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

            self.aktif_noktalar.append(Point(float(event.x), float(event.y)))

        self.son_x, self.son_y = event.x, event.y
        self.son_yazma_zamani = time.time()

    def jestleri_kontrol_et(self):
        gecen_sure = time.time() - self.stroke_baslangic_zamani

        # 1. Hızlı dikey çizgi (Enter / Yeni Satır)
        if dikey_cizgi_jesti_mi(self.aktif_noktalar, gecen_sure):
            logger.info(">> [JEST] Hızlı Dikey Çizgi: Enter (Yeni Satır)!")
            if self.tum_stroke_noktalari:
                self.son_silinen_resim = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
                self.son_silinen_stroke_noktalari = [list(pts) for pts in self.tum_stroke_noktalari]

            if self.isleniyor:
                self.bekleyen_yeni_satir += 1
                logger.info(f">> [JEST Sıralama] Dönüşüm sürdüğü için yeni satır yanıttan sonraya sıraya alındı (Bekleyen: {self.bekleyen_yeni_satir}).")
            else:
                self.storage.yeni_satir_ekle()
                if self.otomatik_enter:
                    threading.Thread(target=self._arka_planda_enter_bas, daemon=True).start()

            self.ekrani_temizle(yedekle=False)
            return True

        # 2. Karalama ile Silme Jesti (Scratch-out)
        if karalama_jesti_mi(self.aktif_noktalar):
            logger.info(">> [JEST] Karalama: Ekran temizlendi! (Geri almak için ↶ butonu)")
            if self.tum_stroke_noktalari:
                self.son_silinen_resim = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
                self.son_silinen_stroke_noktalari = [list(pts) for pts in self.tum_stroke_noktalari]
            self.ekrani_temizle(yedekle=False)
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
        self.son_x, self.son_y = None, None
        self.son_yazma_zamani = time.time()

        if self.jestleri_kontrol_et():
            self.aktif_noktalar = []
            return

        # Tekil dokunuşları güçlendir
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

        self.aktif_noktalar = []

    def aninda_donustur(self):
        if not self.isleniyor:
            self.tetikle_donusturme()

    def tetikle_donusturme(self):
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

    def zamanlayici_dongusu(self):
        while True:
            time.sleep(0.2)
            suan = time.time()
            if self.yazma_modu_aktif and self.cizim_yapildi and not self.kalem_basili and not self.isleniyor and not self.surukleniyor:
                if (suan - self.son_yazma_zamani) > self.bekleme_suresi:
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
                self.isleniyor = False
                if self.bekleyen_yeni_satir > 0:
                    adet = self.bekleyen_yeni_satir
                    self.bekleyen_yeni_satir = 0
                    for _ in range(adet):
                        self.storage.yeni_satir_ekle()
                    if self.otomatik_enter:
                        threading.Thread(target=self._arka_planda_enter_bas, args=(adet,), daemon=True).start()

    def panoya_ve_dosyaya_aktar(self, metin):
        try:
            pano_basarili = False
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
                logger.error("[Pano Hatası] Metin panoya yazılamadı! Güvenlik nedeniyle otomatik yapıştırma atlandı.")
                self.alt_cubuk_gecici_mesaj("⚠️ Pano kopyalanamadı! Yapıştırma iptal edildi.")

            self.storage.metin_kaydet(metin)

            enter_adet = self.bekleyen_yeni_satir
            self.bekleyen_yeni_satir = 0
            self.isleniyor = False

            if enter_adet > 0:
                for _ in range(enter_adet):
                    self.storage.yeni_satir_ekle()

            if self.yazma_modu_aktif:
                self.root.after(0, self.butonlari_ciz)

            gonderilecek_enter = enter_adet if self.otomatik_enter else 0
            if self.otomatik_yapistir and pano_basarili:
                threading.Thread(target=self._arka_planda_yapistir_ve_enter, args=(gonderilecek_enter,), daemon=True).start()
            elif not self.otomatik_yapistir and gonderilecek_enter > 0:
                threading.Thread(target=self._arka_planda_enter_bas, args=(gonderilecek_enter,), daemon=True).start()

        finally:
            self.isleniyor = False

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

    def _arka_planda_yapistir_ve_enter(self, enter_adet=0):
        time.sleep(0.12)
        try:
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


def main():
    root = tk.Tk()
    app = ArkaPlanNotDonusturucu(root)
    root.mainloop()


if __name__ == "__main__":
    main()
