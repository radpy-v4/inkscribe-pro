import os
import re
import time
from .config import APP_DIR, logger


def metin_ekleme_bicimlendir(metin, aktif_defter_adi, gecen_sure, saat_str="12:00", dosya_sonu=None):
    """Format recognition output according to the active notebook's conventions."""
    is_todo = (aktif_defter_adi == "Yapılacaklar")
    acik_todo = metin.startswith(("[ ]", "[x]", "- [ ]"))
    is_bullet = bool(re.match(r"^(\d+[.)]\s+|-\s+|[•*])", metin)) or metin.lower().startswith("madde ")

    if dosya_sonu is not None:
        satir_basi = dosya_sonu in ("\n", "\r")
        if is_todo:
            if satir_basi:
                return metin if acik_todo or is_bullet else f"[ ] {metin}"
            if acik_todo or is_bullet:
                return f"\n{metin}"
            if gecen_sure > 180:
                return f"\n[ ] {metin}"
            return metin if metin.startswith((".", ",", "!", "?", ":", ";")) else f" {metin}"
        if is_bullet:
            return metin if satir_basi else f"\n{metin}"
        if gecen_sure > 60:
            return f"[{saat_str}] {metin}" if satir_basi else f"\n\n[{saat_str}] {metin}"
        if metin.startswith((".", ",", "!", "?", ":", ";")):
            return metin
        return metin if satir_basi else f" {metin}"

    if is_todo and not acik_todo and not is_bullet:
        return f"\n[ ] {metin}"
    if is_bullet:
        return f"\n{metin}"
    if gecen_sure > 60:
        return f"\n\n[{saat_str}] {metin}"
    return metin if metin.startswith((".", ",", "!", "?", ":", ";")) else f" {metin}"


class NotebookManager:
    """Manage multiple text notebooks and note-file operations."""

    def __init__(self, app_dir=APP_DIR):
        self.app_dir = app_dir
        self.defterler_dizini = os.path.join(self.app_dir, "defterler")
        try:
            os.makedirs(self.defterler_dizini, exist_ok=True)
        except Exception as e:
            logger.warning(f"[Storage] defterler dizini oluşturulamadı ({e}), app_dir kullanılacak.")
            self.defterler_dizini = self.app_dir
        self.defterler = [
            ("Genel", os.path.join(self.defterler_dizini, "notlar.txt")),
            ("Ders Notları", os.path.join(self.defterler_dizini, "ders_notlari.txt")),
            ("Yapılacaklar", os.path.join(self.defterler_dizini, "yapilacaklar.txt")),
            ("Fikirler", os.path.join(self.defterler_dizini, "fikirler.txt"))
        ]
        self._eski_dosyalari_tasi()
        self.aktif_defter_index = 0
        self.son_kayit_zamani = 0
        self.son_kayit_tarihi = self._dosyadaki_son_tarihi_bul(self.aktif_defter_dosyasi)

    def _eski_dosyalari_tasi(self):
        if self.defterler_dizini == self.app_dir:
            return
        import shutil
        for _, hedef_yol in self.defterler:
            eski_yol = os.path.join(self.app_dir, os.path.basename(hedef_yol))
            if os.path.exists(eski_yol) and os.path.abspath(eski_yol) != os.path.abspath(hedef_yol):
                try:
                    if not os.path.exists(hedef_yol) or (os.path.getsize(eski_yol) > 0 and os.path.getsize(hedef_yol) == 0):
                        shutil.move(eski_yol, hedef_yol)
                        logger.info(f">> [Defter Taşıma] '{os.path.basename(hedef_yol)}' -> defterler/ klasörüne taşındı.")
                except Exception as e:
                    logger.warning(f"[Defter Taşıma Uyarısı] '{os.path.basename(hedef_yol)}' taşınamadı: {e}")

    def _dosyadaki_son_tarihi_bul(self, dosya_yolu):
        if not os.path.exists(dosya_yolu):
            return ""
        try:
            with open(dosya_yolu, "r", encoding="utf-8") as f:
                for line in reversed(f.readlines()):
                    line = line.strip()
                    if line.startswith("--- ") and line.endswith(" ---"):
                        parts = line.replace("-", "").strip().split(".")
                        if len(parts) == 3:
                            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        except Exception:
            pass
        return ""

    @property
    def aktif_defter_adi(self):
        return self.defterler[self.aktif_defter_index][0]

    @property
    def aktif_defter_dosyasi(self):
        return self.defterler[self.aktif_defter_index][1]

    def defter_sec(self, index):
        if 0 <= index < len(self.defterler):
            self.aktif_defter_index = index
            self.son_kayit_zamani = 0
            self.son_kayit_tarihi = self._dosyadaki_son_tarihi_bul(self.aktif_defter_dosyasi)
            logger.info(f">> [Defter] Aktif: {self.aktif_defter_adi}")

    def son_satirlari_oku(self, satir_sayisi=2):
        """Read a bounded tail of the notebook instead of scanning the whole file."""
        if satir_sayisi <= 0:
            return []
        path = self.aktif_defter_dosyasi
        if not os.path.exists(path):
            return []
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                # UI preview only needs a few short lines; cap I/O regardless of file size.
                f.seek(max(0, size - 64 * 1024), os.SEEK_SET)
                data = f.read().decode("utf-8", errors="replace")
            lines = [line.strip() for line in data.splitlines()
                     if line.strip() and not line.startswith("#") and not line.startswith("---")]
            return lines[-satir_sayisi:]
        except Exception as e:
            logger.error(f"Defter okuma hatası: {e}")
            return []

    def _dosya_sonu_karakteri(self, dosya_yolu):
        if not os.path.exists(dosya_yolu) or os.path.getsize(dosya_yolu) == 0:
            return "\n"
        try:
            with open(dosya_yolu, "rb") as f:
                f.seek(-1, os.SEEK_END)
                return f.read(1).decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def yeni_satir_ekle(self):
        try:
            with open(self.aktif_defter_dosyasi, "a", encoding="utf-8") as f:
                f.write("\n")
            self.son_kayit_zamani = time.time()
            logger.info(f">> [Dosya] Alt satıra geçildi: '{self.aktif_defter_dosyasi}'")
        except Exception as e:
            logger.error(f"[Satır Ekleme Hatası]: {e}")

    def metin_kaydet(self, metin):
        try:
            path = self.aktif_defter_dosyasi
            now = time.time()
            today = time.strftime("%Y-%m-%d")
            clock = time.strftime("%H:%M")
            elapsed = now - self.son_kayit_zamani if self.son_kayit_zamani > 0 else 9999
            file_exists = os.path.exists(path) and os.path.getsize(path) > 0
            last_char = self._dosya_sonu_karakteri(path)
            with open(path, "a", encoding="utf-8") as f:
                if today != self.son_kayit_tarihi or not file_exists:
                    date_str = time.strftime("%d.%m.%Y")
                    header = f"# InkScribe Pro - {self.aktif_defter_adi}\n\n" if not file_exists else ""
                    separator = f"{header}--- {date_str} ---\n[{clock}] " if not file_exists else f"\n\n--- {date_str} ---\n[{clock}] "
                    is_todo = self.aktif_defter_adi == "Yapılacaklar"
                    content = f"[ ] {metin}" if is_todo and not metin.startswith(("[ ]", "[x]", "- [ ]")) else metin
                    f.write(separator + content)
                else:
                    f.write(metin_ekleme_bicimlendir(metin, self.aktif_defter_adi, elapsed, clock, dosya_sonu=last_char))
            self.son_kayit_zamani = now
            self.son_kayit_tarihi = today
            logger.info(f">> [Dosya] '{self.aktif_defter_adi}' defterine kaydedildi.")
        except Exception as e:
            logger.error(f"[Dosya Kayıt Hatası]: {e}")

    def notlar_dosyasini_ac(self):
        path = self.aktif_defter_dosyasi
        try:
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"# InkScribe Pro - {self.aktif_defter_adi}\n\n")
            os.startfile(path)
        except Exception as e:
            logger.error(f"Dosya açılamadı: {e}")

    def defterler_klasorunu_ac(self):
        try:
            os.makedirs(self.defterler_dizini, exist_ok=True)
            os.startfile(self.defterler_dizini)
            logger.info(f">> [Klasör] Defterler dizini açıldı: {self.defterler_dizini}")
        except Exception as e:
            logger.error(f"Defterler klasörü açılamadı: {e}")
