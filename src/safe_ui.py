"""Safe UI entry point and safeguards for InkScribe Pro."""

import time
import tkinter as tk
from tkinter import messagebox

from PIL import ImageDraw

from . import ui


class SafeArkaPlanNotDonusturucu(ui.ArkaPlanNotDonusturucu):
    """UI controller with conservative input defaults and preserved ink."""

    def __init__(self, root):
        super().__init__(root)
        # Risky actions remain opt-in for every startup, including existing configs.
        self.config.navigasyon_jestleri_aktif = False
        self.config.kaydet()
        self.otomatik_yapistir = False
        self.otomatik_enter = False

    def _olcekle_noktalari(self, eski_boyut, yeni_boyut):
        eski_w, eski_h = eski_boyut
        yeni_w, yeni_h = yeni_boyut
        if eski_w <= 0 or eski_h <= 0:
            return
        sx, sy = yeni_w / eski_w, yeni_h / eski_h

        def scale_strokes(strokes):
            return [[ui.Point(float(p.x) * sx, float(p.y) * sy) for p in stroke] for stroke in strokes]

        self.tum_stroke_noktalari = scale_strokes(self.tum_stroke_noktalari)
        self.aktif_noktalar = [ui.Point(float(p.x) * sx, float(p.y) * sy) for p in self.aktif_noktalar]
        if self.son_x is not None:
            self.son_x = float(self.son_x) * sx
        if self.son_y is not None:
            self.son_y = float(self.son_y) * sy

    def _cizimleri_yeniden_olustur(self):
        """Rebuild the Pillow image, canvas strokes, and Windows Ink container."""
        self.image = self.stroke_noktalarindan_resim_uret(self.tum_stroke_noktalari)
        self.draw = ImageDraw.Draw(self.image)
        self.canvas.delete("cizim")
        self.canvas.delete("stroke_current")
        line_width = 3 if not self.tam_ekran_mi else 5
        radius = 1.5 if not self.tam_ekran_mi else 2.5
        for points in self.tum_stroke_noktalari:
            if len(points) == 1:
                p = points[0]
                self.canvas.create_oval(p.x-radius, p.y-radius, p.x+radius, p.y+radius,
                                        fill="#00ffcc", outline="", tags="cizim")
            elif len(points) > 1:
                coords = [coord for p in points for coord in (p.x, p.y)]
                self.canvas.create_line(*coords, fill="#00ffcc", width=line_width,
                                        capstyle=tk.ROUND, joinstyle=tk.ROUND,
                                        smooth=True, tags="cizim")
        self.stroke_container = ui.inking.InkStrokeContainer() if ui.inking else None
        if self.stroke_container and self.stroke_builder:
            for points in self.tum_stroke_noktalari:
                try:
                    self.stroke_container.add_stroke(self.stroke_builder.create_stroke(points))
                except Exception as exc:
                    ui.logger.warning("[Ink] Vuruş yeniden oluşturulamadı: %s", exc)
        self.cizim_yapildi = bool(self.tum_stroke_noktalari)
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def toggle_tam_ekran(self):
        """Switch modes without discarding pending ink."""
        old_size = self.mevcut_boyut()
        strokes = [list(points) for points in self.tum_stroke_noktalari]
        if self.aktif_noktalar:
            strokes.append(list(self.aktif_noktalar))
        super().toggle_tam_ekran()
        new_size = self.mevcut_boyut()
        self.tum_stroke_noktalari = strokes
        self.aktif_noktalar = []
        self.kalem_basili = False
        self.son_x = self.son_y = None
        if self.titreme_filtresi:
            self.titreme_filtresi.sifirla()
        self._olcekle_noktalari(old_size, new_size)
        self._cizimleri_yeniden_olustur()
        if self.cizim_yapildi:
            self._debounce_kur()

    def fare_hareket(self, event):
        """Draw one live canvas polyline per stroke, not one item per segment."""
        if self.boyutlandiriliyor:
            old_size = self.mevcut_boyut()
            super().fare_hareket(event)
            new_size = self.mevcut_boyut()
            if old_size != new_size:
                self._olcekle_noktalari(old_size, new_size)
                self._cizimleri_yeniden_olustur()
            return
        if self.surukleniyor:
            super().fare_hareket(event)
            return
        if not self.kalem_basili:
            return
        tf = getattr(self, "titreme_filtresi", None)
        pt = tf.filtrele(event.x, event.y) if tf else ui.Point(float(event.x), float(event.y))
        if pt is None:
            return
        if self.son_x is not None and self.son_y is not None:
            width = 3 if not self.tam_ekran_mi else 5
            radius = 1.5 if not self.tam_ekran_mi else 2.5
            self.draw.line([self.son_x, self.son_y, pt.x, pt.y], fill="black", width=width)
            self.draw.ellipse([pt.x-radius, pt.y-radius, pt.x+radius, pt.y+radius], fill="black")
            self.aktif_noktalar.append(ui.Point(float(pt.x), float(pt.y)))
            coords = [coord for p in self.aktif_noktalar for coord in (p.x, p.y)]
            items = self.canvas.find_withtag("stroke_current")
            if items:
                self.canvas.coords(items[0], *coords)
            else:
                self.canvas.create_line(*coords, fill="#00ffcc", width=width,
                                        capstyle=tk.ROUND, joinstyle=tk.ROUND,
                                        smooth=True, tags=("cizim", "stroke_current"))
        self.son_x, self.son_y = pt.x, pt.y
        self.son_yazma_zamani = time.time()

    def fare_birakildi(self, event):
        """Finish resizing without clearing the user's drawing."""
        if self.boyutlandiriliyor:
            self.boyutlandiriliyor = False
            self._cizimleri_yeniden_olustur()
            return
        super().fare_birakildi(event)

    def _ai_onay_iste(self):
        """Require explicit opt-in; dismissal means offline mode."""
        title = "InkScribe Pro - AI Bulut Tanıma Onayı"
        question = (
            "Gemini Vision AI modu ile Türkçe el yazısı tanıma kalitesini artırabilirsiniz.\n\n"
            "GİZLİLİK VE VERİ BİLDİRİMİ:\n"
            "Bu özellik aktifken, tabletinizde yazdığınız el yazısı görsel kırpıntıları "
            "metne dönüştürülmek üzere şifreli bağlantıyla Google Cloud (Gemini API) "
            "sunucularına iletilir.\n\n"
            "El yazısı görüntülerinizin Google'a iletilmesini onaylıyor musunuz?"
        )
        try:
            approved = messagebox.askyesno(title, question, icon="question", default="no", parent=self.root)
        except Exception:
            approved = messagebox.askyesno(title, question, icon="question", default="no")
        self.config.ai_onay_verildi = bool(approved)
        self.config.ai_modu_aktif = bool(approved)
        self.config.kaydet()
        if approved:
            ui.logger.info(">> [Gizlilik Onayı] Kullanıcı Gemini Vision bulut tanımayı ONAYLADI.")
            self.alt_cubuk_gecici_mesaj("✅ Gemini Vision AI aktif edildi.", sure=2.5)
        else:
            ui.logger.info(">> [Gizlilik Onayı] Onay verilmedi; AI kapalı.")
            self.alt_cubuk_gecici_mesaj("ℹ️ AI Modu kapatıldı. Sadece çevrimdışı Windows Ink kullanılacak.", sure=3.5)
        if self.yazma_modu_aktif:
            self.butonlari_ciz()
        return bool(approved)

    def _hedef_pencereyi_etkinlestir(self):
        """Only permit simulated input when the captured target is still valid and foreground."""
        hwnd = self.son_hedef_hwnd
        if not ui.user32 or not hwnd:
            return False
        try:
            if not ui.user32.IsWindow(hwnd):
                return False
            if ui.user32.GetForegroundWindow() != hwnd:
                ui.user32.SetForegroundWindow(hwnd)
                time.sleep(0.08)
            return ui.user32.IsWindow(hwnd) and ui.user32.GetForegroundWindow() == hwnd
        except Exception:
            return False

    def _arka_planda_yaz_karakterleri(self, metin, enter_adet=0, tab_adet=0):
        if ui.keyboard is None or not self._hedef_pencereyi_etkinlestir():
            ui.logger.warning("[Auto-Type] Hedef pencere doğrulanamadı; metin/tuş gönderimi iptal edildi.")
            return
        try:
            controller = ui.keyboard.Controller()
            controller.type(metin)
            for _ in range(enter_adet):
                controller.press(ui.keyboard.Key.enter)
                controller.release(ui.keyboard.Key.enter)
            for _ in range(tab_adet):
                controller.press(ui.keyboard.Key.tab)
                controller.release(ui.keyboard.Key.tab)
        except Exception as exc:
            ui.logger.error("[Auto-Type] Metin gönderilemedi: %s", exc)

    def panoya_ve_dosyaya_aktar(self, metin):
        """Save notes and type Unicode directly; never replace the user's clipboard."""
        yaz_ekrana = getattr(self, "cikis_hedefi", "cift") in ("cift", "ekran")
        kaydet_txt = getattr(self, "cikis_hedefi", "cift") in ("cift", "txt")
        enter_adet = self.bekleyen_yeni_satir
        tab_adet = self.bekleyen_tab
        self.bekleyen_yeni_satir = 0
        self.bekleyen_tab = 0
        try:
            if kaydet_txt:
                self.storage.metin_kaydet(metin)
                for _ in range(enter_adet):
                    self.storage.yeni_satir_ekle()
            if yaz_ekrana:
                # Additional automatic Enter remains disabled by default; only queued explicit gestures apply.
                text_to_type = metin if metin.endswith((" ", "\n", "\t")) else metin + " "
                threading.Thread(target=self._arka_planda_yaz_karakterleri,
                                 args=(text_to_type, enter_adet, tab_adet), daemon=True).start()
            self.isleniyor = False
            if self.yazma_modu_aktif:
                self.butonlari_ciz()
        except Exception as exc:
            self.isleniyor = False
            ui.logger.error("[Aktarım Hatası]: %s", exc)
            self.alt_cubuk_gecici_mesaj("⚠️ Metin aktarılırken hata oluştu.")
        finally:
            self._debounce_kur()

    def _arka_planda_enter_bas(self, adet=1):
        self._arka_planda_yaz_karakterleri("", enter_adet=adet)

    def _arka_planda_tab_bas(self, adet=1):
        self._arka_planda_yaz_karakterleri("", tab_adet=adet)

    def _arka_planda_ctrl_z_bas(self):
        # Never send Ctrl+Z to another application from a potentially misrecognized gesture.
        ui.logger.info("[Undo] Global Ctrl+Z jesti devre dışı; başka uygulamaya tuş gönderilmedi.")

    def programi_kapat(self):
        """Stop listeners and destroy Tk cleanly."""
        if getattr(self, "_closing", False):
            return
        self._closing = True
        ui.logger.info("InkScribe Pro kapatılıyor...")
        if self.tray:
            try:
                self.tray.durdur()
            except Exception:
                pass
        listener = getattr(self, "hotkey_listener", None)
        if listener:
            try:
                listener.stop()
            except Exception:
                pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def main():
    ui.setup_logging(ui.APP_DIR)
    root = tk.Tk()
    SafeArkaPlanNotDonusturucu(root)
    root.mainloop()


if __name__ == "__main__":
    main()
