import os
import re
import time
from .config import APP_DIR, logger


def metin_ekleme_bicimlendir(metin, aktif_defter_adi, gecen_sure, saat_str="12:00"):
    """
    Deftere kaydedilirken yapılacaklar kutusu, zaman damgası ve boşluk kurallarını biçimlendirir.
    Birim testlerde saf mantık olarak test edilebilir ve metin_kaydet tarafından doğrudan kullanılır.
    """
    is_todo = (aktif_defter_adi == "Yapılacaklar")
    if is_todo and not metin.startswith(("[ ]", "[x]", "- [ ]")):
        metin = f"[ ] {metin}"

    # Madde işareti kuralı:
    # '•' ve '*' işaretleri harfe bitişik olsa da madde sayılır (örn: •Merhaba, *Not).
    # '-' ve '1.' gibi numaralar ise yalnızca sonrasında boşluk varsa madde sayılır (1.5 litre ve -5 derece korunur).
    is_bullet = bool(re.match(r"^(\d+[.)]\s+|-\s+|[•*])", metin)) or metin.lower().startswith("madde ")

    if is_todo or is_bullet:
        return f"\n{metin}"
    elif gecen_sure > 30:
        return f"\n\n[{saat_str}] {metin}"
    else:
        if metin.startswith((".", ",", "!", "?", ":", ";")):
            return metin
        else:
            return f" {metin}"


class NotebookManager:
    """Çoklu not defterlerini (.txt), zaman damgalarını ve dosya işlemlerini yönetir."""

    def __init__(self, app_dir=APP_DIR):
        self.app_dir = app_dir
        self.defterler = [
            ("Genel", os.path.join(self.app_dir, "notlar.txt")),
            ("Ders Notları", os.path.join(self.app_dir, "ders_notlari.txt")),
            ("Yapılacaklar", os.path.join(self.app_dir, "yapilacaklar.txt")),
            ("Fikirler", os.path.join(self.app_dir, "fikirler.txt"))
        ]
        self.aktif_defter_index = 0
        self.son_kayit_zamani = 0
        self.son_kayit_tarihi = self._dosyadaki_son_tarihi_bul(self.aktif_defter_dosyasi)

    def _dosyadaki_son_tarihi_bul(self, dosya_yolu):
        """Dosyadaki en son '--- DD.MM.YYYY ---' ayraç tarihini tespit eder."""
        if not os.path.exists(dosya_yolu):
            return ""
        try:
            with open(dosya_yolu, "r", encoding="utf-8") as f:
                satirlar = f.readlines()
                for line in reversed(satirlar):
                    line = line.strip()
                    if line.startswith("--- ") and line.endswith(" ---"):
                        parcalar = line.replace("-", "").strip().split(".")
                        if len(parcalar) == 3:
                            return f"{parcalar[2]}-{parcalar[1]}-{parcalar[0]}"
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
        dosya_yolu = self.aktif_defter_dosyasi
        if not os.path.exists(dosya_yolu):
            return []
        try:
            with open(dosya_yolu, "r", encoding="utf-8") as f:
                satirlar = [line.strip() for line in f if line.strip() and not line.startswith("#") and not line.startswith("---")]
                return satirlar[-satir_sayisi:] if satirlar else []
        except Exception as e:
            logger.error(f"Defter okuma hatası: {e}")
            return []

    def yeni_satir_ekle(self):
        try:
            dosya_yolu = self.aktif_defter_dosyasi
            with open(dosya_yolu, "a", encoding="utf-8") as f:
                f.write("\n")
            logger.info(f">> [Dosya] Alt satıra geçildi: '{dosya_yolu}'")
        except Exception as e:
            logger.error(f"[Satır Ekleme Hatası]: {e}")

    def metin_kaydet(self, metin):
        try:
            dosya_yolu = self.aktif_defter_dosyasi
            suan_ts = time.time()
            bugun = time.strftime("%Y-%m-%d")
            saat = time.strftime("%H:%M")
            gecen_sure = suan_ts - self.son_kayit_zamani

            dosya_dolu = os.path.exists(dosya_yolu) and os.path.getsize(dosya_yolu) > 0

            with open(dosya_yolu, "a", encoding="utf-8") as f:
                if bugun != self.son_kayit_tarihi:
                    tarih_str = time.strftime("%d.%m.%Y")
                    baslik = f"# InkScribe Pro - {self.aktif_defter_adi}\n\n" if not dosya_dolu else ""
                    ayrac = f"{baslik}--- {tarih_str} ---\n[{saat}] " if not dosya_dolu else f"\n\n--- {tarih_str} ---\n[{saat}] "
                    is_todo = (self.aktif_defter_adi == "Yapılacaklar")
                    icerik = f"[ ] {metin}" if is_todo and not metin.startswith(("[ ]", "[x]", "- [ ]")) else metin
                    f.write(ayrac + icerik)
                else:
                    bicimli = metin_ekleme_bicimlendir(metin, self.aktif_defter_adi, gecen_sure, saat)
                    f.write(bicimli)

            self.son_kayit_zamani = suan_ts
            self.son_kayit_tarihi = bugun
            logger.info(f">> [Dosya] '{self.aktif_defter_adi}' defterine kaydedildi.")
        except Exception as e:
            logger.error(f"[Dosya Kayıt Hatası]: {e}")

    def notlar_dosyasini_ac(self):
        dosya_yolu = self.aktif_defter_dosyasi
        try:
            if not os.path.exists(dosya_yolu):
                with open(dosya_yolu, "w", encoding="utf-8") as f:
                    f.write(f"# InkScribe Pro - {self.aktif_defter_adi}\n\n")
            os.startfile(dosya_yolu)
        except Exception as e:
            logger.error(f"Dosya açılamadı: {e}")
