import threading
from PIL import Image, ImageDraw
from .config import logger
try:
    import pystray
    _pystray_err = None
except Exception as _e:
    pystray = None
    _pystray_err = _e
    logger.warning(f"[Tepsi] pystray import edilemedi: {_e}")


class TrayManager:
    """Windows sistem tepsisi simgesi (System Tray) ve sağ tık menüsünü yönetir."""

    def __init__(self, app_controller):
        self.app = app_controller
        self.tray_icon = None

    def icon_gorseli_uret(self):
        icon_img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(icon_img)
        d.rounded_rectangle([4, 4, 60, 60], radius=12, fill="#0f172a", outline="#38bdf8", width=3)
        d.polygon([(46, 14), (50, 18), (24, 48), (16, 48), (16, 40)], fill="#38bdf8")
        d.polygon([(16, 48), (14, 52), (20, 50)], fill="#f59e0b")
        return icon_img

    def baslat(self):
        if pystray is None:
            logger.warning("[Tepsi] pystray modülü yüklü olmadığı için sistem tepsisi başlatılamadı.")
            return

        icon_img = self.icon_gorseli_uret()

        menu = pystray.Menu(
            pystray.MenuItem("✍️ Not Pedi (F8)", lambda icon, item: self.app.root.after(0, self.app.yazma_modunu_ac)),
            pystray.MenuItem("⛶ Tam Ekran / Mini Pad (F9)", lambda icon, item: self.app.root.after(0, self.app.toggle_tam_ekran)),
            pystray.MenuItem("↶ Son Çizimi Geri Al", lambda icon, item: self.app.root.after(0, self.app.geri_al)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🎯 Aktarım Hedefi", pystray.Menu(
                pystray.MenuItem("🎯 Hem Ekran Hem TXT (Çift)", lambda icon, item: self.app.root.after(0, lambda: self.app.cikis_hedefi_degistir("cift")), checked=lambda item: self.app.cikis_hedefi == "cift", radio=True),
                pystray.MenuItem("🖥️ Sadece Ekran (İmlece Yaz)", lambda icon, item: self.app.root.after(0, lambda: self.app.cikis_hedefi_degistir("ekran")), checked=lambda item: self.app.cikis_hedefi == "ekran", radio=True),
                pystray.MenuItem("📝 Sadece TXT (Sessiz Defter)", lambda icon, item: self.app.root.after(0, lambda: self.app.cikis_hedefi_degistir("txt")), checked=lambda item: self.app.cikis_hedefi == "txt", radio=True),
            )),
            pystray.MenuItem("⏱️ Yazma Bekleme Süresi", pystray.Menu(
                pystray.MenuItem("🐇 Hızlı (1.5 sn)", lambda icon, item: self.app.root.after(0, lambda: self.app.bekleme_suresi_ayarla(1.5)), checked=lambda item: abs(self.app.bekleme_suresi - 1.5) < 0.1, radio=True),
                pystray.MenuItem("⚖️ Normal (2.5 sn)", lambda icon, item: self.app.root.after(0, lambda: self.app.bekleme_suresi_ayarla(2.5)), checked=lambda item: abs(self.app.bekleme_suresi - 2.5) < 0.1, radio=True),
                pystray.MenuItem("🐢 Rahat (3.5 sn - Önerilen)", lambda icon, item: self.app.root.after(0, lambda: self.app.bekleme_suresi_ayarla(3.5)), checked=lambda item: abs(self.app.bekleme_suresi - 3.5) < 0.1, radio=True),
                pystray.MenuItem("🛋️ Çok Rahat (5.0 sn)", lambda icon, item: self.app.root.after(0, lambda: self.app.bekleme_suresi_ayarla(5.0)), checked=lambda item: abs(self.app.bekleme_suresi - 5.0) < 0.1, radio=True),
                pystray.MenuItem("✋ Manuel (Sadece [↵ Gönder] ile)", lambda icon, item: self.app.root.after(0, lambda: self.app.bekleme_suresi_ayarla(0.0)), checked=lambda item: self.app.bekleme_suresi <= 0.05, radio=True),
            )),
            pystray.MenuItem("✍️ Gezinme Jestleri (Enter ↵ / Tab ⇥)", lambda icon, item: self.app.root.after(0, self.app.toggle_navigasyon_jestleri), checked=lambda item: getattr(self.app.config, 'navigasyon_jestleri_aktif', False)),
            pystray.MenuItem("📁 Aktif Defter", pystray.Menu(
                pystray.MenuItem("📝 Genel", lambda icon, item: self.app.root.after(0, lambda: self.app.defter_sec(0)), checked=lambda item: self.app.storage.aktif_defter_index == 0),
                pystray.MenuItem("📘 Ders Notları", lambda icon, item: self.app.root.after(0, lambda: self.app.defter_sec(1)), checked=lambda item: self.app.storage.aktif_defter_index == 1),
                pystray.MenuItem("✅ Yapılacaklar", lambda icon, item: self.app.root.after(0, lambda: self.app.defter_sec(2)), checked=lambda item: self.app.storage.aktif_defter_index == 2),
                pystray.MenuItem("💡 Fikirler", lambda icon, item: self.app.root.after(0, lambda: self.app.defter_sec(3)), checked=lambda item: self.app.storage.aktif_defter_index == 3),
            )),
            pystray.MenuItem("📂 Notlar Dosyasını Aç", lambda icon, item: self.app.storage.notlar_dosyasini_ac()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚡ Vision AI (Gemini) Hibrit", lambda icon, item: self.app.root.after(0, self.app.toggle_ai_modu), checked=lambda item: self.app.config.ai_modu_aktif),
            pystray.MenuItem("📋 Otomatik İmlece Yapıştır", self.app.otomatik_yapistir_degistir, checked=lambda item: self.app.otomatik_yapistir),
            pystray.MenuItem("⏎ Otomatik Enter Tuşu", self.app.otomatik_enter_degistir, checked=lambda item: self.app.otomatik_enter),
            pystray.MenuItem("🚀 Windows Açılışında Başlat", lambda icon, item: self.app.config.baslangic_durumu_degistir(), checked=lambda item: self.app.config.baslangic_durumu_al()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Programdan Çık", lambda icon, item: self.app.root.after(0, self.app.programi_kapat))
        )

        self.tray_icon = pystray.Icon("InkScribePro", icon_img, "InkScribe Pro", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def notify(self, message, title="InkScribe Pro"):
        if self.tray_icon:
            try:
                self.tray_icon.notify(message, title)
            except Exception as e:
                logger.debug(f"Tepsi bildirimi hatası: {e}")

    def durdur(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
