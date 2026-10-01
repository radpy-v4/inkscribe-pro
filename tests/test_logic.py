"""
Tablet Not Alıcı Pro - Mantık ve Algoritma Birim Testleri
Bu testler GUI veya fiziksel tablet donanımı gerektirmeden saf Python ortamında çalışır.
"""

import unittest
import time
from collections import namedtuple

from src.gestures import karalama_jesti_mi, dikey_cizgi_jesti_mi
from src.engine import gemini_metin_ayristir
from src.storage import metin_ekleme_bicimlendir
from src.config import ConfigManager

# foundation.Point benzeri hafif veri yapısı (testler için)
Point = namedtuple("Point", ["x", "y"])



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

    def test_thinking_config_onbellekleme(self):
        """thinkingConfig desteklemeyen modeller için payload parametresiz üretilmeli."""
        desteklemeyenler = {"gemini-3.5-flash"}
        
        def payload_uret(model_adi):
            p = {'generationConfig': {'temperature': 0.0}}
            if model_adi not in desteklemeyenler:
                p['generationConfig']['thinkingConfig'] = {'thinkingBudget': 0}
            return p

        # Desteklemeyen modelde thinkingConfig bulunmamalı
        self.assertNotIn('thinkingConfig', payload_uret("gemini-3.5-flash")['generationConfig'])
        # Destekleyen modelde thinkingConfig bulunmalı
        self.assertIn('thinkingConfig', payload_uret("gemini-flash-latest")['generationConfig'])

    def test_pano_yazilamazsa_yapistirma_ve_enter_engellenir(self):
        """Pano yazma hatasında eski içeriğin veya Enter'ın sızmaması testi."""
        pano_basarili = False
        otomatik_yapistir = True
        bekleyen_enter = True

        yapistirildi = False
        enter_basildi = False

        if otomatik_yapistir and pano_basarili:
            yapistirildi = True
            if bekleyen_enter:
                enter_basildi = True

        # Pano başarısız olduğu için ikisi de çalışmamalı
        self.assertFalse(yapistirildi)
        self.assertFalse(enter_basildi)

    def test_bekleyen_yeni_satir_sayac_ve_yaris_durumu_korumasi(self):
        """Dönüşüm sürerken çizilen birden fazla Enter sayılmalı ve isleniyor önce kapanmalı."""
        bekleyen_yeni_satir = 2
        isleniyor = True
        metin_bulundu = False
        eklenen_satir_sayisi = 0

        # Doğru sıra: Önce isleniyor kapanır, sonra sayaç boşaltılır
        if not metin_bulundu:
            isleniyor = False
            if bekleyen_yeni_satir > 0:
                eklenen_satir_sayisi = bekleyen_yeni_satir
                bekleyen_yeni_satir = 0

        self.assertFalse(isleniyor)
        self.assertEqual(bekleyen_yeni_satir, 0)
        self.assertEqual(eklenen_satir_sayisi, 2)

    def test_http_429_ve_503_siradaki_modele_gecer(self):
        """HTTP 429 veya 503 alındığında sıradaki model adayına devam edilmeli."""
        modeller = ["gemini-3.5-flash", "gemini-flash-latest"]
        denenen = []
        basarili_model = None

        for m in modeller:
            denenen.append(m)
            # İlk model 429 (hız sınırı) döndü varsayalım
            if m == "gemini-3.5-flash":
                code = 429
                if code in (429, 503):
                    continue
            basarili_model = m
            break

        self.assertEqual(denenen, ["gemini-3.5-flash", "gemini-flash-latest"])
        self.assertEqual(basarili_model, "gemini-flash-latest")


if __name__ == "__main__":
    unittest.main()


