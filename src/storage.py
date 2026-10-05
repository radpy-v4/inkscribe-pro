import os
import re
import time
from .config import APP_DIR, logger


def metin_ekleme_bicimlendir(metin, aktif_defter_adi, gecen_sure, saat_str="12:00", dosya_sonu=None):
    """
    Deftere kaydedilirken yapılacaklar kutusu, zaman damgası ve boşluk kurallarını biçimlendirir.
    dosya_sonu parametresi None ise (veya test ortamındaysa) standart bağımsız kurallar uygulanır.
    Gerçek dosya yazımında dosya_sonu verilmişse; Yapılacaklar defterinde son karakter '\n' değilse
    kelimeler aynı satırda aralarına boşlukla birleştirilir.
    """
    is_todo = (aktif_defter_adi == "Yapılacaklar")
    acik_todo = metin.startswith(("[ ]", "[x]", "- [ ]"))
    is_bullet = bool(re.match(r"^(\d+[.)]\s+|-\s+|[•*])", metin)) or metin.lower().startswith("madde ")

    # 1. dosya_sonu belirtilmişse gerçek dosya bağlamı kontrolü
    if dosya_sonu is not None:
        satir_basi = (dosya_sonu in ("\n", "\r"))
        if is_todo:
            if satir_basi:
                if not acik_todo and not is_bullet:
                    return f"[ ] {metin}"
                return metin
            else:
                if acik_todo or is_bullet:
                    return f"\n{metin}"
                elif gecen_sure > 180:
                    return f"\n[ ] {metin}"
                else:
                    return metin if metin.startswith((".", ",", "!", "?", ":", ";")) else f" {metin}"
        else:
            if is_bullet:
                return metin if satir_basi else f"\n{metin}"
            elif gecen_sure > 60:
                return f"[{saat_str}] {metin}" if satir_basi else f"\n\n[{saat_str}] {metin}"
            else:
                if metin.startswith((".", ",", "!", "?", ":", ";")):
                    return metin
                return metin if satir_basi else f" {metin}"

    # 2. dosya_sonu None ise (geriye dönük uyumlu / bağımsız birim test modu)
    if is_todo and not acik_todo and not is_bullet:
        return f"\n[ ] {metin}"
    elif is_bullet:
        return f"\n{metin}"
    elif gecen_sure > 60:
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
        """Kök dizinde kalan eski defter dosyalarını (varsa) yeni defterler/ alt klasörüne taşır."""
        if self.defterler_dizini == self.app_dir:
            return
        import shutil
        for ad, hedef_yol in self.defterler:
            dosya_adi = os.path.basename(hedef_yol)
            eski_yol = os.path.join(self.app_dir, dosya_adi)
            if os.path.exists(eski_yol) and os.path.abspath(eski_yol) != os.path.abspath(hedef_yol):
                try:
                    if not os.path.exists(hedef_yol):
                        shutil.move(eski_yol, hedef_yol)
                        logger.info(f">> [Defter Taşıma] '{dosya_adi}' -> defterler/ klasörüne taşındı.")
                    elif os.path.getsize(eski_yol) > 0 and os.path.getsize(hedef_yol) == 0:
                        shutil.move(eski_yol, hedef_yol)
                        logger.info(f">> [Defter Taşıma] Boş hedef yerine dolu '{dosya_adi}' taşındı.")
                except Exception as e:
                    logger.warning(f"[Defter Taşıma Uyarısı] '{dosya_adi}' taşınamadı: {e}")

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

    def _dosya_sonu_karakteri(self, dosya_yolu):
        """Dosyanın en son karakterini hızlıca okur (örn: '\n' veya metin harfi)."""
        if not os.path.exists(dosya_yolu) or os.path.getsize(dosya_yolu) == 0:
            return "\n"
        try:
            with open(dosya_yolu, "rb") as f:
                f.seek(-1, os.SEEK_END)
                son_byte = f.read(1)
                return son_byte.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def yeni_satir_ekle(self):
        try:
            dosya_yolu = self.aktif_defter_dosyasi
            with open(dosya_yolu, "a", encoding="utf-8") as f:
                f.write("\n")
            self.son_kayit_zamani = time.time()
            logger.info(f">> [Dosya] Alt satıra geçildi: '{dosya_yolu}'")
        except Exception as e:
            logger.error(f"[Satır Ekleme Hatası]: {e}")

    def metin_kaydet(self, metin):
        try:
            dosya_yolu = self.aktif_defter_dosyasi
            suan_ts = time.time()
            bugun = time.strftime("%Y-%m-%d")
            saat = time.strftime("%H:%M")
            gecen_sure = suan_ts - self.son_kayit_zamani if self.son_kayit_zamani > 0 else 9999

            dosya_dolu = os.path.exists(dosya_yolu) and os.path.getsize(dosya_yolu) > 0
            son_karakter = self._dosya_sonu_karakteri(dosya_yolu)

            with open(dosya_yolu, "a", encoding="utf-8") as f:
                if bugun != self.son_kayit_tarihi or not dosya_dolu:
                    tarih_str = time.strftime("%d.%m.%Y")
                    baslik = f"# InkScribe Pro - {self.aktif_defter_adi}\n\n" if not dosya_dolu else ""
                    ayrac = f"{baslik}--- {tarih_str} ---\n[{saat}] " if not dosya_dolu else f"\n\n--- {tarih_str} ---\n[{saat}] "
                    is_todo = (self.aktif_defter_adi == "Yapılacaklar")
                    icerik = f"[ ] {metin}" if is_todo and not metin.startswith(("[ ]", "[x]", "- [ ]")) else metin
                    f.write(ayrac + icerik)
                else:
                    bicimli = metin_ekleme_bicimlendir(metin, self.aktif_defter_adi, gecen_sure, saat, dosya_sonu=son_karakter)
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

    def defterler_klasorunu_ac(self):
        """Not defterlerinin toplandığı 'defterler/' klasörünü dosya yöneticisinde açar."""
        try:
            if not os.path.exists(self.defterler_dizini):
                os.makedirs(self.defterler_dizini, exist_ok=True)
            os.startfile(self.defterler_dizini)
            logger.info(f">> [Klasör] Defterler dizini açıldı: {self.defterler_dizini}")
        except Exception as e:
            logger.error(f"Defterler klasörü açılamadı: {e}")

