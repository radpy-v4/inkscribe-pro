import threading
from PIL import Image, ImageDraw
try:
    import pystray
except ImportError:
    pystray = None
from .config import logger


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

        self.tray_icon = pystray.Icon("TabletNotAlici", icon_img, "VEIKK Tablet Not Alıcı Pro", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def notify(self, message, title="VEIKK Not Alıcı Pro"):
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
