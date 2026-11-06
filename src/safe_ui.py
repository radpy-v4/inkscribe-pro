"""Safer application entry point and UI lifecycle safeguards.

The original UI remains in ``src.ui``; this subclass applies safety fixes to
mode changes, resize handling, consent defaults, and graceful shutdown.
"""

import tkinter as tk
from tkinter import messagebox

from PIL import ImageDraw

from . import ui


class SafeArkaPlanNotDonusturucu(ui.ArkaPlanNotDonusturucu):
    """UI controller preserving pending ink and using safe lifecycle defaults."""

    def _olcekle_noktalari(self, eski_boyut, yeni_boyut):
        """Scale stored stroke coordinates to match a changed canvas size."""
        eski_w, eski_h = eski_boyut
        yeni_w, yeni_h = yeni_boyut
        if eski_w <= 0 or eski_h <= 0:
            return
        sx, sy = yeni_w / eski_w, yeni_h / eski_h

        def scale_strokes(strokes):
            return [
                [ui.Point(float(p.x) * sx, float(p.y) * sy) for p in stroke]
                for stroke in strokes
            ]

        self.tum_stroke_noktalari = scale_strokes(self.tum_stroke_noktalari)
        self.aktif_noktalar = [
            ui.Point(float(p.x) * sx, float(p.y) * sy)
            for p in self.aktif_noktalar
        ]
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
                self.canvas.create_oval(
                    p.x - radius, p.y - radius, p.x + radius, p.y + radius,
                    fill="#00ffcc", outline="", tags="cizim"
                )
            for first, second in zip(points, points[1:]):
                self.canvas.create_line(
                    first.x, first.y, second.x, second.y,
                    fill="#00ffcc", width=line_width, capstyle=tk.ROUND,
                    joinstyle=tk.ROUND, smooth=True, tags="cizim"
                )

        self.stroke_container = ui.inking.InkStrokeContainer() if ui.inking else None
        if self.stroke_container and self.stroke_builder:
            for points in self.tum_stroke_noktalari:
                try:
                    self.stroke_container.add_stroke(
                        self.stroke_builder.create_stroke(points)
                    )
                except Exception as exc:
                    ui.logger.warning("[Ink] Vuruş yeniden oluşturulamadı: %s", exc)

        self.cizim_yapildi = bool(self.tum_stroke_noktalari)
        if self.yazma_modu_aktif:
            self.butonlari_ciz()

    def toggle_tam_ekran(self):
        """Switch modes without discarding ink waiting to be recognized."""
        old_size = self.mevcut_boyut()
        strokes = [list(points) for points in self.tum_stroke_noktalari]
        if self.aktif_noktalar:
            strokes.append(list(self.aktif_noktalar))

        # Base method changes the window mode but clears its drawing surface.
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
        """Keep the image and stored strokes in sync with live pad resizing."""
        old_size = self.mevcut_boyut()
        was_resizing = self.boyutlandiriliyor
        super().fare_hareket(event)
        new_size = self.mevcut_boyut()
        if was_resizing and old_size != new_size:
            self._olcekle_noktalari(old_size, new_size)
            self._cizimleri_yeniden_olustur()

    def _ai_onay_iste(self):
        """Require an explicit opt-in; dismissing the dialog means offline mode."""
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
            approved = messagebox.askyesno(
                title, question, icon="question", default="no", parent=self.root
            )
        except Exception:
            approved = messagebox.askyesno(
                title, question, icon="question", default="no"
            )

        if approved:
            self.config.ai_onay_verildi = True
            self.config.ai_modu_aktif = True
            self.config.kaydet()
            ui.logger.info(">> [Gizlilik Onayı] Kullanıcı Gemini Vision bulut tanımayı ONAYLADI.")
            self.alt_cubuk_gecici_mesaj("✅ Gemini Vision AI aktif edildi.", sure=2.5)
        else:
            self.config.ai_onay_verildi = False
            self.config.ai_modu_aktif = False
            self.config.kaydet()
            ui.logger.info(">> [Gizlilik Onayı] Onay verilmedi; AI kapalı.")
            self.alt_cubuk_gecici_mesaj(
                "ℹ️ AI Modu kapatıldı. Sadece çevrimdışı Windows Ink kullanılacak.",
                sure=3.5,
            )

        if self.yazma_modu_aktif:
            self.butonlari_ciz()
        return bool(approved)

    def programi_kapat(self):
        """Stop listeners and destroy Tk cleanly; avoid abrupt os._exit()."""
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
    """Launch InkScribe Pro with the safety-preserving UI controller."""
    ui.setup_logging(ui.APP_DIR)
    root = tk.Tk()
    SafeArkaPlanNotDonusturucu(root)
    root.mainloop()


if __name__ == "__main__":
    main()
