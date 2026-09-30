import tkinter as tk
from PIL import Image, ImageDraw, ImageChops
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
from pynput import keyboard
import pystray

# Windows Yerel Türkçe El Yazısı Tanıma API'si (Windows Ink Recognition)
import winrt.windows.ui.input.inking as inking
import winrt.windows.foundation as foundation

REG_STARTUP_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_APP_NAME = "TabletNotAlici"

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
        self.root.overrideredirect(True) # Menü çubuğunu gizle
        self.root.lift()
        self.root.wm_attributes("-topmost", True)
        self.pencere_boyutunu_guncelle()

        print("[1/3] Windows Yerel El Yazısı Tanıma Motoru (Windows Ink) başlatılıyor...")
        self.ink_container = inking.InkRecognizerContainer()
        self.stroke_builder = inking.InkStrokeBuilder()
        self.stroke_container = inking.InkStrokeContainer()
        self.aktif_noktalar = []
        self.stroke_baslangic_zamani = 0

        # Türkçe el yazısı tanıyıcısını seç
        motor_adi = "Varsayılan"
        for r in self.ink_container.get_recognizers():
            if "türkiye" in r.name.lower() or "turkish" in r.name.lower() or "tr" in r.name.lower():
                self.ink_container.set_default_recognizer(r)
                motor_adi = r.name
                break
        print(f"[2/3] El yazısı motoru hazır: {motor_adi} (100% Çevrimdışı & Donanım Hızlandırmalı)")

        self.son_yazma_zamani = time.time()
        self.bekleme_suresi = 0.65  # Hızlı algılama süresi (0.65 saniye)
        self.kalem_basili = False
        self.isleniyor = False
        self.yazma_modu_aktif = False
        self.surukleniyor = False

        # Akıllı metin akışı takibi
        self.son_kayit_zamani = 0
        self.son_kayit_tarihi = ""

        # Yetenekler
        self.otomatik_yapistir = True

        # Çoklu Defterler
        self.defterler = [
            ("Genel", "notlar.txt"),
            ("Ders Notları", "ders_notlari.txt"),
            ("Yapılacaklar", "yapilacaklar.txt"),
            ("Fikirler", "fikirler.txt")
        ]
        self.aktif_defter_index = 0

        # Gemini Vision Hibrit Ayarları
        dizin = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.config_dosyasi = os.path.join(dizin, "config.json")
        if not os.path.exists(self.config_dosyasi) and os.path.exists("config.json"):
            self.config_dosyasi = os.path.abspath("config.json")

        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        self.ai_modu_aktif = True
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

        # Kısayol Tuşları
        self.root.bind("<Escape>", lambda e: self.yazma_modunu_kapat())
        self.root.bind("<Return>", lambda e: self.aninda_donustur())
        self.root.bind("<Shift-Escape>", lambda e: self.programi_kapat())

        # Başlangıçta pencereyi gizle
        self.root.withdraw()

        # Global Kısayol Dinleyicisi
        self.hotkey_listener = keyboard.GlobalHotKeys({
            '<f8>': lambda: self.root.after(0, self.toggle_yazma_modu),
            '<f9>': lambda: self.root.after(0, self.toggle_tam_ekran)
        })
        self.hotkey_listener.start()

        # Sistem Tepsisi
        self.tepsi_simgesi_olustur()

        print("[3/3] Dinleyici aktif!")
        print("      [F8] = Not Pedini Göster/Gizle")
        print("      [F9] = Yüzen Mini Pad / Tam Ekran Değiştir")
        print("      Jestler: Karalama = Temizle, Hızlı Dikey Çizgi = Enter / Yeni Satır.")

        # Zamanlayıcı döngüsü
        threading.Thread(target=self.zamanlayici_dongusu, daemon=True).start()

    def mevcut_boyut(self):
        if self.tam_ekran_mi:
            return self.ekran_genislik, self.ekran_yukseklik
        return self.pad_genislik, self.pad_yukseklik

    def pencere_boyutunu_guncelle(self):
        """Moda göre pencere boyutunu ve saydamlığını ayarlar."""
        if self.tam_ekran_mi:
            self.root.geometry(f"{self.ekran_genislik}x{self.ekran_yukseklik}+0+0")
            self.root.wm_attributes("-alpha", 0.30)
            if hasattr(self, 'canvas'):
                self.canvas.config(bg="#111111", highlightthickness=0)
        else:
            self.root.geometry(f"{self.pad_genislik}x{self.pad_yukseklik}+{self.pad_x}+{self.pad_y}")
            self.root.wm_attributes("-alpha", 0.92) # Yüzen ped şık koyu cam görünümünde
            if hasattr(self, 'canvas'):
                self.canvas.config(bg="#0f172a", highlightthickness=2, highlightbackground="#38bdf8")

    def toggle_tam_ekran(self):
        """Mini Pad ve Tam Ekran arasında geçiş yapar."""
        self.tam_ekran_mi = not self.tam_ekran_mi
        self.pencere_boyutunu_guncelle()
        self.ekrani_temizle()
        mod_adi = "Tam Ekran" if self.tam_ekran_mi else "Yüzen Mini Pad"
        print(f">> [Mod Değişti] {mod_adi}")

    @property
    def aktif_defter_adi(self):
        return self.defterler[self.aktif_defter_index][0]

    @property
    def aktif_defter_dosyasi(self):
        return self.defterler[self.aktif_defter_index][1]

    def sonraki_deftere_gec(self):
        self.aktif_defter_index = (self.aktif_defter_index + 1) % len(self.defterler)
        self.son_kayit_zamani = 0
        print(f">> [Defter] Aktif: {self.aktif_defter_adi}")
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def defter_sec(self, index):
        self.aktif_defter_index = index
        self.son_kayit_zamani = 0
        print(f">> [Defter] Aktif: {self.aktif_defter_adi}")
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def yapilandirmayi_yukle(self):
        try:
            if os.path.exists(self.config_dosyasi):
                with open(self.config_dosyasi, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.gemini_api_key = cfg.get("gemini_api_key", self.gemini_api_key)
                    self.ai_modu_aktif = cfg.get("ai_modu_aktif", self.ai_modu_aktif)
                    print(f">> [Config] Yüklendi ({self.config_dosyasi}) - AI Modu: {self.ai_modu_aktif}")
            else:
                self.yapilandirmayi_kaydet()
        except Exception as e:
            print(f"[Config Hatası]: {e}")

    def yapilandirmayi_kaydet(self):
        try:
            cfg = {
                "gemini_api_key": self.gemini_api_key,
                "ai_modu_aktif": self.ai_modu_aktif,
                "aciklama": "ai_modu_aktif true iken internet varsa Gemini Vision modeli kullanilir, internet yoksa veya baglanti yavaslarsa aninda offline Windows Ink motoruna duser."
            }
            with open(self.config_dosyasi, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Config Kayıt Hatası]: {e}")

    def toggle_ai_modu(self, icon=None, item=None):
        self.ai_modu_aktif = not self.ai_modu_aktif
        self.yapilandirmayi_kaydet()
        durum = "⚡ Açık (Online Hibrit)" if self.ai_modu_aktif else "💻 Kapalı (Sadece Çevrimdışı)"
        print(f">> [Vision AI Modu] {durum}")
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def gemini_vision_ile_tani(self, kirpilmis_resim):
        if not self.gemini_api_key or not self.ai_modu_aktif:
            return None
        
        try:
            # Boyutu en fazla 650px yap ve JPEG olarak sıkıştır (veri transferini 10 kat hızlandırır)
            w, h = kirpilmis_resim.size
            if w > 650:
                h = max(1, int(h * (650 / w)))
                w = 650
                kirpilmis_resim = kirpilmis_resim.resize((w, h), Image.Resampling.BILINEAR)

            buf = io.BytesIO()
            kirpilmis_resim.convert("RGB").save(buf, format="JPEG", quality=75)
            b64_data = base64.b64encode(buf.getvalue()).decode('utf-8')
            
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
                    'maxOutputTokens': 50
                }
            }

            url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self.gemini_api_key}'
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            # 1.6 sn zaman aşımı: Eğer ağ gecikirse kullanıcıyı bekletmeden anında Windows Ink'e aktarır
            with urllib.request.urlopen(req, timeout=1.6) as resp:
                res = json.loads(resp.read().decode())
                if 'candidates' in res and res['candidates']:
                    txt = res['candidates'][0]['content']['parts'][0]['text'].strip()
                    if txt.startswith("```") and txt.endswith("```"):
                        lines = txt.split("\n")
                        txt = "\n".join(lines[1:-1]).strip() if len(lines) >= 3 else txt.replace("```", "").strip()
                    if txt and not txt.lower().startswith("görüntüde") and not txt.lower().startswith("bu görselde"):
                        return txt

        except Exception as e:
            print(f"[Vision AI Hızlı Geçiş]: Ağ gecikmesi veya zaman aşımı ({e}), yerel motora aktarılıyor...")
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
                calisan_exe = os.path.abspath(sys.argv[0])
                winreg.SetValueEx(key, REG_APP_NAME, 0, winreg.REG_SZ, f'"{calisan_exe}"')
                print(f">> [Windows Başlangıç] Eklendi: {calisan_exe}")
            else:
                try:
                    winreg.DeleteValue(key, REG_APP_NAME)
                    print(">> [Windows Başlangıç] Kaldırıldı.")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[Kayıt Defteri Hatası]: {e}")

    def otomatik_yapistir_degistir(self, icon=None, item=None):
        self.otomatik_yapistir = not self.otomatik_yapistir
        durum = "Açık" if self.otomatik_yapistir else "Kapalı"
        print(f">> [Auto-Type] Otomatik Yapıştırma: {durum}")

    def tepsi_simgesi_olustur(self):
        icon_img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(icon_img)
        d.rounded_rectangle([4, 4, 60, 60], radius=12, fill="#0f172a", outline="#38bdf8", width=3)
        d.polygon([(46, 14), (50, 18), (24, 48), (16, 48), (16, 40)], fill="#38bdf8")
        d.polygon([(16, 48), (14, 52), (20, 50)], fill="#f59e0b")

        menu = pystray.Menu(
            pystray.MenuItem("✍️ Not Pedi (F8)", lambda icon, item: self.root.after(0, self.yazma_modunu_ac)),
            pystray.MenuItem("⛶ Tam Ekran / Mini Pad (F9)", lambda icon, item: self.root.after(0, self.toggle_tam_ekran)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📁 Aktif Defter", pystray.Menu(
                pystray.MenuItem("📝 Genel", lambda icon, item: self.defter_sec(0), checked=lambda item: self.aktif_defter_index == 0),
                pystray.MenuItem("📘 Ders Notları", lambda icon, item: self.defter_sec(1), checked=lambda item: self.aktif_defter_index == 1),
                pystray.MenuItem("✅ Yapılacaklar", lambda icon, item: self.defter_sec(2), checked=lambda item: self.aktif_defter_index == 2),
                pystray.MenuItem("💡 Fikirler", lambda icon, item: self.defter_sec(3), checked=lambda item: self.aktif_defter_index == 3),
            )),
            pystray.MenuItem("📂 Notlar Dosyasını Aç", lambda icon, item: self.notlar_dosyasini_ac()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚡ Vision AI (Gemini) Hibrit", lambda icon, item: self.root.after(0, self.toggle_ai_modu), checked=lambda item: self.ai_modu_aktif),
            pystray.MenuItem("📋 Otomatik İmlece Yapıştır", self.otomatik_yapistir_degistir, checked=lambda item: self.otomatik_yapistir),
            pystray.MenuItem("🚀 Windows Açılışında Başlat", self.baslangic_durumu_degistir, checked=lambda item: self.baslangic_durumu_al()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Programdan Çık", lambda icon, item: self.root.after(0, self.programi_kapat))
        )

        self.tray_icon = pystray.Icon("TabletNotAlici", icon_img, "VEIKK Tablet Not Alıcı Pro", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def notlar_dosyasini_ac(self):
        dosya_yolu = os.path.abspath(self.aktif_defter_dosyasi)
        if not os.path.exists(dosya_yolu):
            with open(dosya_yolu, "w", encoding="utf-8") as f:
                f.write(f"# VEIKK VK640 - {self.aktif_defter_adi}\n\n")
        try:
            os.startfile(dosya_yolu)
        except Exception as e:
            print(f"Dosya açma hatası: {e}")

    def butonlari_ciz(self):
        """Üst kontrol çubuğunu ve butonları çizer."""
        self.canvas.delete("ui_eleman")
        w, _ = self.mevcut_boyut()
        bar_h = 42

        # Mini Pad modunda şık üst taşıma başlığı (koyu lacivert şerit)
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
        self.canvas.create_rectangle(sag_x - 215, y, sag_x - 130, y + h, fill="#f59e0b", outline="", tags=("ui_eleman", "btn_temizle"))
        self.canvas.create_text(sag_x - 172, y + 15, text="🗑 Temizle", fill="white", font=("Arial", 9, "bold"), tags=("ui_eleman", "btn_temizle"))

        # [✓ Dönüştür] Butonu
        self.canvas.create_rectangle(sag_x - 315, y, sag_x - 220, y + h, fill="#10b981", outline="", tags=("ui_eleman", "btn_donustur"))
        self.canvas.create_text(sag_x - 267, y + 15, text="✓ Dönüştür", fill="white", font=("Arial", 9, "bold"), tags=("ui_eleman", "btn_donustur"))

        # [📁 Defter Rozeti]
        defter_metni = f"📁 {self.aktif_defter_adi}"
        defter_w = max(110, len(defter_metni) * 8 + 20)
        btn_sol = sag_x - 325 - defter_w
        self.canvas.create_rectangle(btn_sol, y, sag_x - 325, y + h, fill="#3b82f6", outline="", tags=("ui_eleman", "btn_defter"))
        self.canvas.create_text(btn_sol + (defter_w // 2), y + 15, text=defter_metni, fill="white", font=("Arial", 9, "bold"), tags=("ui_eleman", "btn_defter"))

        # [⚡ AI Modu Rozeti / Butonu]
        ai_metni = "⚡ AI: Açık" if self.ai_modu_aktif else "💻 Offline"
        ai_renk = "#8b5cf6" if self.ai_modu_aktif else "#475569"
        ai_w = 95
        ai_sol = btn_sol - 10 - ai_w
        self.canvas.create_rectangle(ai_sol, y, btn_sol - 10, y + h, fill=ai_renk, outline="", tags=("ui_eleman", "btn_ai"))
        self.canvas.create_text(ai_sol + (ai_w // 2), y + 15, text=ai_metni, fill="white", font=("Arial", 9, "bold"), tags=("ui_eleman", "btn_ai"))

        # Sağ alt köşe boyutlandırma simgesi (Mini modda sağ alttan çekip büyütülebilir)
        if not self.tam_ekran_mi:
            _, h_win = self.mevcut_boyut()
            self.canvas.create_line(w - 18, h_win - 6, w - 6, h_win - 18, fill="#64748b", width=2, tags="ui_eleman")
            self.canvas.create_line(w - 12, h_win - 6, w - 6, h_win - 12, fill="#64748b", width=2, tags="ui_eleman")
            self.canvas.create_line(w - 6, h_win - 6, w - 6, h_win - 6, fill="#64748b", width=2, tags="ui_eleman")

    def buton_tiklandi_mi(self, x, y):
        w, _ = self.mevcut_boyut()
        sag_x = w - 10

        defter_metni = f"📁 {self.aktif_defter_adi}"
        defter_w = max(110, len(defter_metni) * 8 + 20)
        btn_sol = sag_x - 325 - defter_w
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
            elif sag_x - 215 <= x <= sag_x - 130:
                self.ekrani_temizle()
                return True
            elif sag_x - 315 <= x <= sag_x - 220:
                self.aninda_donustur()
                return True
            elif btn_sol <= x <= sag_x - 325:
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
        self.ekrani_temizle()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.butonlari_ciz()
        mod = "Tam Ekran" if self.tam_ekran_mi else "Yüzen Mini Pad"
        print(f"\n>> [{mod.upper()} AÇIK] Aktif Defter: {self.aktif_defter_adi}")

    def yazma_modunu_kapat(self):
        self.yazma_modu_aktif = False
        self.root.withdraw()
        self.ekrani_temizle()
        print("<< [NOT PEDİ GİZLENDİ] Masaüstüne dönüldü.")

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

        # 4. Çizim başlatma (y > 42 ise çizim alanıdır)
        self.kalem_basili = True
        self.son_x, self.son_y = event.x, event.y
        self.son_yazma_zamani = time.time()
        self.stroke_baslangic_zamani = time.time()
        
        self.aktif_noktalar = [foundation.Point(float(event.x), float(event.y))]

        r = 1.5 if not self.tam_ekran_mi else 2.5
        self.draw.ellipse([event.x - r, event.y - r, event.x + r, event.y + r], fill="black")

    def fare_hareket(self, event):
        # Pencere boyutlandırma hareketi
        if self.boyutlandiriliyor:
            dw = event.x_root - self._resize_start_x
            dh = event.y_root - self._resize_start_y
            self.pad_genislik = max(550, self._orig_w + dw)
            self.pad_yukseklik = max(280, self._orig_h + dh)
            self.pencere_boyutunu_guncelle()
            self.ekrani_temizle()
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

        # Hızlı dikey çizgi (Enter / Yeni Satır)
        if nokta_sayisi >= 4 and gecen_sure < 0.45:
            p_ilk = self.aktif_noktalar[0]
            p_son = self.aktif_noktalar[-1]
            dy = p_son.y - p_ilk.y
            dx = abs(p_son.x - p_ilk.x)
            if dy > 110 and dx < 40:
                print(">> [JEST] Hızlı Dikey Çizgi: Enter (Yeni Satır)!")
                self.dosyaya_yeni_satir_ekle()
                self.ekrani_temizle()
                return True

        # Karalama ile Silme Jesti (Scratch-out)
        if nokta_sayisi >= 10:
            x_degerleri = [p.x for p in self.aktif_noktalar]
            yon_degisimleri = 0
            son_yon = 0
            for i in range(1, len(x_degerleri)):
                fark = x_degerleri[i] - x_degerleri[i - 1]
                if abs(fark) > 8:
                    mevcut_yon = 1 if fark > 0 else -1
                    if son_yon != 0 and mevcut_yon != son_yon:
                        yon_degisimleri += 1
                    son_yon = mevcut_yon
            
            if yon_degisimleri >= 5:
                print(">> [JEST] Karalama: Ekran temizlendi!")
                self.ekrani_temizle()
                return True

        return False

    def fare_birakildi(self, event):
        if self.boyutlandiriliyor:
            self.boyutlandiriliyor = False
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
            except Exception as e:
                print(f"[Stroke Hatası]: {e}")

        self.aktif_noktalar = []

    def aninda_donustur(self):
        if not self.isleniyor:
            self.tetikle_donusturme()

    def tetikle_donusturme(self):
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
            
            self.ekrani_temizle()
            threading.Thread(target=self.metne_donustur, args=(strokes_to_process, islem_resmi, bbox), daemon=True).start()

    def zamanlayici_dongusu(self):
        while True:
            time.sleep(0.2)
            suan = time.time()
            if self.yazma_modu_aktif and not self.kalem_basili and not self.isleniyor and not self.surukleniyor:
                if (suan - self.son_yazma_zamani) > self.bekleme_suresi:
                    self.tetikle_donusturme()

    def metne_donustur(self, stroke_container, resim, bbox):
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

            # Eger yazi kucuk veya basik kalmissa dikey oranini ferahlat ve cozunurlugu artir
            kw, kh = kirpilmis.size
            if kh < 130:
                scale = 140.0 / max(1, kh)
                target_w = max(100, int(kw * scale))
                target_h = 140
                aspect = kw / max(1, kh)
                if aspect > 4.5:
                    target_h = int(target_h * 1.35)  # %35 dikey genisletme ile harf kollarini ve gozlerini acar
                kirpilmis = kirpilmis.resize((target_w, target_h), Image.Resampling.LANCZOS)

            kirpilmis.save(os.path.abspath("debug_son_cizim.png"))

            metin = None

            # 1. Aşama: Vision AI (Gemini) Hibrit Tanıma
            if self.ai_modu_aktif and self.gemini_api_key:
                print("\n[AI Vision] Gemini modeli ile taranıyor...")
                metin = self.gemini_vision_ile_tani(kirpilmis)
                if metin:
                    print(f">> [AI Vision Başarılı] '{metin}'")
                else:
                    print(">> [AI Fallback] Çevrimdışı yerel motora geçiliyor...")

            # 2. Aşama: Windows Ink (100% Offline Yerel Motor)
            if not metin:
                print("\n[Windows Ink (Offline)] Yerel motor ile el yazısı tanınıyor...")
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
                print("=========================================")
                print(f"[DÖNÜŞTÜRÜLEN METİN]:\n{metin}")
                print("=========================================")
                self.root.after(0, lambda: self.panoya_ve_dosyaya_aktar(metin))
            else:
                print("[Uyarı] Metin algılanamadı.")

        except Exception as e:
            print(f"[Tanıma Hatası]: {e}")
        finally:
            self.isleniyor = False

    def panoya_ve_dosyaya_aktar(self, metin):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(metin)
            self.root.update()
            print(">> [Pano] Metin panoya kopyalandı! (Ctrl + V)")
        except Exception as e:
            print(f"Pano Hatası: {e}")

        self.dosyaya_kaydet(metin)

        if self.otomatik_yapistir:
            threading.Thread(target=self._arka_planda_yapistir, daemon=True).start()

    def _arka_planda_yapistir(self):
        time.sleep(0.12)
        try:
            kb = keyboard.Controller()
            with kb.pressed(keyboard.Key.ctrl):
                kb.press('v')
                kb.release('v')
            print(">> [Auto-Type] Metin doğrudan aktif pencerenize yapıştırıldı!")
        except Exception as e:
            print(f"Auto-Type Hatası: {e}")

    def dosyaya_yeni_satir_ekle(self):
        try:
            dosya_yolu = os.path.abspath(self.aktif_defter_dosyasi)
            with open(dosya_yolu, "a", encoding="utf-8") as f:
                f.write("\n")
            print(f">> [Dosya] Alt satıra geçildi: '{dosya_yolu}'")
        except Exception as e:
            print(f"[Satır Ekleme Hatası]: {e}")

    def dosyaya_kaydet(self, metin):
        try:
            dosya_yolu = os.path.abspath(self.aktif_defter_dosyasi)
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
            print(f">> [Dosya] Not '{self.aktif_defter_adi}' defterine kaydedildi: '{dosya_yolu}'")
        except Exception as e:
            print(f"[Dosya Kayıt Hatası]: {e}")

    def ekrani_temizle(self):
        self.canvas.delete("all")
        w, h = self.mevcut_boyut()
        self.image = Image.new("RGB", (w, h), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.stroke_container = inking.InkStrokeContainer()
        self.aktif_noktalar = []
        self.son_yazma_zamani = time.time()
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def programi_kapat(self):
        print("Program tamamen kapatılıyor...")
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