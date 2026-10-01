"""
Tablet Not Alıcı Pro - Mantık ve Algoritma Birim Testleri
Bu testler GUI veya fiziksel tablet donanımı gerektirmeden saf Python ortamında çalışır.
"""

import unittest
import time
from collections import namedtuple

# foundation.Point benzeri hafif veri yapısı
Point = namedtuple("Point", ["x", "y"])


def karalama_jesti_mi(noktalar):
    """hand_to_text.py içindeki karalama (scratch-out) algılama algoritması."""
    if len(noktalar) < 12:
        return False
    x_degerleri = [p.x for p in noktalar]
    yon_degisimleri = 0
    son_yon = 0
    toplam_yol_x = 0
    for i in range(1, len(x_degerleri)):
        fark = x_degerleri[i] - x_degerleri[i - 1]
        toplam_yol_x += abs(fark)
        if abs(fark) > 8:
            mevcut_yon = 1 if fark > 0 else -1
            if son_yon != 0 and mevcut_yon != son_yon:
                yon_degisimleri += 1
            son_yon = mevcut_yon

    genislik_x = max(x_degerleri) - min(x_degerleri)
    return yon_degisimleri >= 6 and (toplam_yol_x / max(1.0, genislik_x)) > 2.5


def dikey_cizgi_jesti_mi(noktalar, gecen_sure):
    """hand_to_text.py içindeki hızlı dikey çizgi (Enter) algılama algoritması."""
    if len(noktalar) < 5 or gecen_sure >= 0.35:
        return False
    p_ilk = noktalar[0]
    p_son = noktalar[-1]
    dy = p_son.y - p_ilk.y
    dx = abs(p_son.x - p_ilk.x)
    return dy > 130 and dx < 30 and (dy / max(1.0, dx)) > 4.0


def gemini_metin_ayristir(candidate):
    """Gemini API yanıtından metni güvenle ayıklama ve filtreleme algoritması."""
    content_obj = candidate.get('content', {})
    parts_list = content_obj.get('parts', [])
    txt = ''.join(p.get('text', '') for p in parts_list if isinstance(p, dict)).strip()

    if txt.startswith("```") and txt.endswith("```"):
        lines = txt.split("\n")
        txt = "\n".join(lines[1:-1]).strip() if len(lines) >= 3 else txt.replace("```", "").strip()

    if txt and not txt.lower().startswith("görüntüde") and not txt.lower().startswith("bu görselde"):
        return txt
    return None


def metin_ekleme_bicimlendir(metin, aktif_defter_adi, gecen_sure):
    """Deftere kaydedilirken boşluk ve madde imi kuralları."""
    is_todo = (aktif_defter_adi == "Yapılacaklar")
    if is_todo and not metin.startswith(("[ ]", "[x]", "- [ ]")):
        metin = f"[ ] {metin}"

    if is_todo or metin.startswith(("-", "*", "•")):
        return f"\n{metin}"
    elif gecen_sure > 30:
        return f"\n\n[12:00] {metin}"
    else:
        if metin.startswith((".", ",", "!", "?", ":", ";")):
            return metin
        else:
            return f" {metin}"


class TestTabletNotAliciMantik(unittest.TestCase):

    def test_karalama_jesti_gercek_karalamayi_yakalar(self):
        """Aynı dar alanda ileri-geri 6+ kez karalama yapıldığında True dönmeli."""
        noktalar = []
        # 100 ile 140 piksel arasında ileri-geri hızlı salınım
        x = 100
        direction = 1
        for _ in range(8):
            for _ in range(3):
                x += direction * 12
                noktalar.append(Point(x, 100))
            direction *= -1

        self.assertTrue(karalama_jesti_mi(noktalar))

    def test_bitisik_el_yazisi_karalama_sayilmaz(self):
        """Soldan sağa ilerleyen 'mmm' veya 'minimum' gibi bitişik yazılar karalama sanılmamalı."""
        noktalar = []
        # Soldan sağa doğru sürekli ilerleyen dalgalı hareket (span genişler)
        x = 100
        for i in range(20):
            x += 15  # Sağa doğru sürekli ilerliyor
            y = 100 + (10 if i % 2 == 0 else -10)
            noktalar.append(Point(x, y))

        self.assertFalse(karalama_jesti_mi(noktalar))

    def test_dikey_cizgi_enter_algilama(self):
        """Hızlı ve dik hareket Enter olmalı, yavaş veya eğik olanlar elenmeli."""
        # 1. Hızlı ve dik çizgi (dy=150, dx=10, 0.20 sn) -> True
        noktalar_enter = [Point(100, 50), Point(102, 80), Point(103, 110), Point(105, 150), Point(108, 200)]
        self.assertTrue(dikey_cizgi_jesti_mi(noktalar_enter, 0.20))

        # 2. Çok yavaş çizgi (0.45 sn) -> False
        self.assertFalse(dikey_cizgi_jesti_mi(noktalar_enter, 0.45))

        # 3. Eğik çizgi (dx fazla) -> False
        noktalar_egik = [Point(100, 50), Point(120, 80), Point(140, 110), Point(160, 150), Point(180, 200)]
        self.assertFalse(dikey_cizgi_jesti_mi(noktalar_egik, 0.20))

    def test_gemini_cok_parcali_yanit_ayristirma(self):
        """Thinking part veya çoklu parça içeren yanıtlarda KeyError vermeden metni çıkarmalı."""
        candidate = {
            'content': {
                'parts': [
                    {'thought': 'Görsel analiz ediliyor...'},  # text anahtarı yok
                    {'text': 'Merhaba Dünya'}
                ]
            }
        }
        sonuc = gemini_metin_ayristir(candidate)
        self.assertEqual(sonuc, "Merhaba Dünya")

    def test_gemini_markdown_kod_bloklarini_temizler(self):
        """```...``` ile sarılmış yanıtları saf metne dönüştürmeli."""
        candidate = {
            'content': {
                'parts': [{'text': '```\nToplantı saat 14:00\n```'}]
            }
        }
        sonuc = gemini_metin_ayristir(candidate)
        self.assertEqual(sonuc, "Toplantı saat 14:00")

    def test_gemini_konusma_cumlelerini_filtreler(self):
        """'Görüntüde el yazısı...' gibi geveze model yanıtlarını None yapmalı."""
        candidate = {
            'content': {
                'parts': [{'text': 'Görüntüde herhangi bir el yazısı bulunamadı.'}]
            }
        }
        self.assertIsNone(gemini_metin_ayristir(candidate))

    def test_yapilacaklar_defteri_kutu_ekler(self):
        """Yapılacaklar defterine yazılan metinlerin başına [ ] eklenmeli."""
        sonuc = metin_ekleme_bicimlendir("Sütü al", "Yapılacaklar", 5)
        self.assertTrue(sonuc.strip().startswith("[ ] Sütü al"))

    def test_noktalama_isaretleri_bosluksuz_eklenir(self):
        """Nokta, virgül gibi işaretlerin önüne fazladan boşluk eklenmemeli."""
        sonuc_nokta = metin_ekleme_bicimlendir(".", "Genel", 5)
        self.assertEqual(sonuc_nokta, ".")

        sonuc_kelime = metin_ekleme_bicimlendir("elma", "Genel", 5)
        self.assertEqual(sonuc_kelime, " elma")


if __name__ == "__main__":
    unittest.main()
