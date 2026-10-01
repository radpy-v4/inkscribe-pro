"""
InkScribe Pro - Mantık ve Algoritma Birim Testleri
Bu testler GUI veya fiziksel tablet donanımı gerektirmeden saf Python ortamında çalışır.
Tüm testler gerçek üretim kodu fonksiyonlarını ve sınıflarını (Gemini API mock, NotebookManager I/O, Jest algoritmaları) doğrudan sınar.
"""

import unittest
import time
import os
import sys
import io
import tempfile
import json
from collections import namedtuple
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from PIL import Image

# Repo kök dizinini sys.path'e ekle
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.gestures import karalama_jesti_mi, dikey_cizgi_jesti_mi
from src.filter import TitremeFiltresi
from src.engine import gemini_metin_ayristir, GeminiVisionRecognizer
from src.storage import metin_ekleme_bicimlendir, NotebookManager
from src.config import ConfigManager
from src.ui import ArkaPlanNotDonusturucu
from PIL import ImageDraw

Point = namedtuple("Point", ["x", "y"])


class TestInkScribeMantik(unittest.TestCase):

    def test_karalama_jesti_gercek_karalamayi_yakalar(self):
        """Aynı dar alanda ileri-geri 6+ kez karalama yapıldığında True dönmeli."""
        noktalar = []
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
        x = 100
        for i in range(20):
            x += 15
            y = 100 + (10 if i % 2 == 0 else -10)
            noktalar.append(Point(x, y))

        self.assertFalse(karalama_jesti_mi(noktalar))

    def test_dikey_cizgi_enter_algilama(self):
        """Hızlı ve dik hareket Enter olmalı, yavaş veya eğik olanlar elenmeli."""
        noktalar_enter = [Point(100, 50), Point(102, 80), Point(103, 110), Point(105, 150), Point(108, 200)]
        self.assertTrue(dikey_cizgi_jesti_mi(noktalar_enter, 0.20))

        # Yavaş çizgi
        self.assertFalse(dikey_cizgi_jesti_mi(noktalar_enter, 0.45))

        # Eğik çizgi
        noktalar_egik = [Point(100, 50), Point(120, 80), Point(140, 110), Point(160, 150), Point(180, 200)]
        self.assertFalse(dikey_cizgi_jesti_mi(noktalar_egik, 0.20))

    def test_gestures_bos_veya_yetersiz_noktada_guvenli(self):
        """Boş veya 1-2 noktalı jest girdileri exception fırlatmadan False dönmeli."""
        self.assertFalse(karalama_jesti_mi([]))
        self.assertFalse(karalama_jesti_mi([Point(10, 10)]))
        self.assertFalse(karalama_jesti_mi([Point(10, 10), Point(20, 20)]))

        self.assertFalse(dikey_cizgi_jesti_mi([], 0.1))
        self.assertFalse(dikey_cizgi_jesti_mi([Point(10, 10)], 0.1))

    def test_gemini_cok_parcali_yanit_ayristirma(self):
        """Thinking part veya çoklu parça içeren yanıtlarda KeyError vermeden metni çıkarmalı."""
        candidate = {
            'content': {
                'parts': [
                    {'thought': 'Görsel analiz ediliyor...'},
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

    def test_gemini_geveze_bulunamadi_cumlelerini_filtreler(self):
        """'Görüntüde herhangi bir el yazısı bulunamadı' gibi yanıtları None yapmalı ama gerçek 'Görüntüleme...' cümlelerini korumalı."""
        candidate_geveze = {
            'content': {'parts': [{'text': 'Görüntüde herhangi bir el yazısı bulunamadı.'}]}
        }
        self.assertIsNone(gemini_metin_ayristir(candidate_geveze))

        candidate_gercek = {
            'content': {'parts': [{'text': 'Görüntü işleme dersi notları'}]}
        }
        self.assertEqual(gemini_metin_ayristir(candidate_gercek), "Görüntü işleme dersi notları")

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

    @patch("urllib.request.urlopen")
    def test_gemini_vision_404_model_otomatik_yedek_modele_gecer(self, mock_urlopen):
        """HTTP 404 (model emekli) durumunda GeminiVisionRecognizer sıradaki yedek modele geçmeli ve config'i güncellemeli."""
        recognizer = GeminiVisionRecognizer()
        img = Image.new("RGB", (100, 100), "white")

        config_mgr = MagicMock()
        config_mgr.gemini_api_key = "TEST_KEY"
        config_mgr.ai_modu_aktif = True
        config_mgr.gemini_model = "gemini-3.5-flash"
        config_mgr.model_adaylari = ["gemini-3.5-flash", "gemini-flash-latest"]
        config_mgr.thinking_desteklemeyenler = set()
        config_mgr.gemini_timeout = 5.0
        config_mgr.gemini_toplam_butce = 8.0

        resp_basarili = MagicMock()
        resp_basarili.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "Sınav Notları"}]}}]
        }).encode("utf-8")
        resp_basarili.__enter__.return_value = resp_basarili

        # İlk çağrı 404, ikinci çağrı başarılı
        err_404 = HTTPError("url", 404, "Not Found", {}, io.BytesIO(b'{"error": "model retired"}'))
        mock_urlopen.side_effect = [err_404, resp_basarili]

        metin = recognizer.tani(img, config_mgr)

        self.assertEqual(metin, "Sınav Notları")
        self.assertEqual(config_mgr.gemini_model, "gemini-flash-latest")
        config_mgr.kaydet.assert_called()

    @patch("urllib.request.urlopen")
    def test_gemini_vision_thinking_config_desteklenmeyince_parametresiz_tekrar_dener(self, mock_urlopen):
        """Model thinkingConfig desteklemediğinde 400 hatası yakalanıp parametresiz yeniden denenmeli."""
        recognizer = GeminiVisionRecognizer()
        img = Image.new("RGB", (100, 100), "white")

        config_mgr = MagicMock()
        config_mgr.gemini_api_key = "TEST_KEY"
        config_mgr.ai_modu_aktif = True
        config_mgr.gemini_model = "gemini-3.5-flash"
        config_mgr.model_adaylari = ["gemini-3.5-flash"]
        config_mgr.thinking_desteklemeyenler = set()
        config_mgr.gemini_timeout = 5.0
        config_mgr.gemini_toplam_butce = 8.0

        resp_basarili = MagicMock()
        resp_basarili.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "Fizik Dersi"}]}}]
        }).encode("utf-8")
        resp_basarili.__enter__.return_value = resp_basarili

        err_thinking = HTTPError("url", 400, "Bad Request", {}, io.BytesIO(b'{"error": "thinkingConfig is not supported for this model"}'))
        mock_urlopen.side_effect = [err_thinking, resp_basarili]

        metin = recognizer.tani(img, config_mgr)

        self.assertEqual(metin, "Fizik Dersi")
        self.assertIn("gemini-3.5-flash", config_mgr.thinking_desteklemeyenler)
        config_mgr.kaydet.assert_called()

    @patch("urllib.request.urlopen")
    def test_gemini_vision_429_kota_asimi_yedek_modele_gecer(self, mock_urlopen):
        """HTTP 429 kota aşımında sıradaki model adayına geçilmeli."""
        recognizer = GeminiVisionRecognizer()
        img = Image.new("RGB", (100, 100), "white")

        config_mgr = MagicMock()
        config_mgr.gemini_api_key = "TEST_KEY"
        config_mgr.ai_modu_aktif = True
        config_mgr.gemini_model = "gemini-3.5-flash"
        config_mgr.model_adaylari = ["gemini-3.5-flash", "gemini-flash-latest"]
        config_mgr.thinking_desteklemeyenler = set()
        config_mgr.gemini_timeout = 5.0
        config_mgr.gemini_toplam_butce = 8.0

        resp_basarili = MagicMock()
        resp_basarili.read.return_value = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "Kota Sonrası Not"}]}}]
        }).encode("utf-8")
        resp_basarili.__enter__.return_value = resp_basarili

        err_429 = HTTPError("url", 429, "Too Many Requests", {}, io.BytesIO(b'{"error": "Rate limit exceeded"}'))
        mock_urlopen.side_effect = [err_429, resp_basarili]

        metin = recognizer.tani(img, config_mgr)

        self.assertEqual(metin, "Kota Sonrası Not")

    @patch("urllib.request.urlopen")
    def test_gemini_vision_toplam_sure_butcesi_asimi(self, mock_urlopen):
        """Toplam süre bütçesi aşıldığında diğer modeller denenmeden yerel motora aktarılmalı."""
        recognizer = GeminiVisionRecognizer()
        img = Image.new("RGB", (100, 100), "white")

        config_mgr = MagicMock()
        config_mgr.gemini_api_key = "TEST_KEY"
        config_mgr.ai_modu_aktif = True
        config_mgr.gemini_model = "gemini-3.5-flash"
        config_mgr.model_adaylari = ["gemini-3.5-flash", "gemini-flash-latest"]
        config_mgr.thinking_desteklemeyenler = set()
        config_mgr.gemini_timeout = 5.0
        config_mgr.gemini_toplam_butce = 0.005  # Çok kısa bütçe

        def _yavas_hata(*args, **kwargs):
            time.sleep(0.01)
            raise HTTPError("url", 503, "Service Unavailable", {}, io.BytesIO(b'503'))

        mock_urlopen.side_effect = _yavas_hata

        metin = recognizer.tani(img, config_mgr)
        self.assertIsNone(metin)
        # Bütçe dolduğu için ikinci model çağrılmamalı (call_count == 1)
        self.assertEqual(mock_urlopen.call_count, 1)

    def test_notebook_manager_metin_kaydet_dosyaya_formatli_yazar(self):
        """NotebookManager metinleri dosyaya zaman damgası ve defter kurallarıyla kaydetmeli."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            nb = NotebookManager(app_dir=tmp_dir)

            # 1. Genel Deftere Yazma
            nb.metin_kaydet("İlk Toplantı Notu")
            with open(nb.aktif_defter_dosyasi, "r", encoding="utf-8") as f:
                icerik = f.read()
            self.assertIn("# InkScribe Pro - Genel", icerik)
            self.assertIn("İlk Toplantı Notu", icerik)

            # 2. Yapılacaklar Defterine Yazma
            nb.defter_sec(2)
            self.assertEqual(nb.aktif_defter_adi, "Yapılacaklar")
            nb.metin_kaydet("Ekmek al")
            with open(nb.aktif_defter_dosyasi, "r", encoding="utf-8") as f:
                icerik_todo = f.read()
            self.assertIn("[ ] Ekmek al", icerik_todo)

    def test_config_manager_gecersiz_model_otomatik_yukseltme(self):
        """Eski model (örn. gemini-1.5-flash) kayıtlıysa ConfigManager otomatik gemini-3.5-flash'a güncellemeli."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = os.path.join(tmp_dir, "config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({"gemini_model": "gemini-1.5-flash", "gemini_api_key": "TEST_KEY"}, f)

            cfg = ConfigManager(app_dir=tmp_dir)
            self.assertEqual(cfg.gemini_model, "gemini-3.5-flash-lite")
            self.assertEqual(cfg.gemini_api_key, "TEST_KEY")

    def test_config_manager_dinamik_model_listesi_ve_timeout(self):
        """Kullanıcı config.json dosyasından özel model listesi ve timeout okuyabilmeli."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = os.path.join(tmp_dir, "config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({
                    "gemini_model": "custom-model-pro",
                    "model_adaylari": ["custom-model-pro", "gemini-3.5-flash"],
                    "gemini_timeout": 6.5,
                    "gemini_toplam_butce": 10.0
                }, f)

            cfg = ConfigManager(app_dir=tmp_dir)
            self.assertEqual(cfg.gemini_model, "custom-model-pro")
            self.assertEqual(cfg.model_adaylari, ["custom-model-pro", "gemini-3.5-flash"])
            self.assertEqual(cfg.gemini_timeout, 6.5)
            self.assertEqual(cfg.gemini_toplam_butce, 10.0)

    def test_gemini_no_text_ve_cumle_icindeki_yazi_yok_ayristirma(self):
        """'NO_TEXT' yanıtı None dönmeli; ancak 'Ödevde yazı yoksa not düş' gibi meşru el yazıları filtrelenmemeli."""
        # 1. NO_TEXT yanıtı
        cand_no_text = {'content': {'parts': [{'text': 'NO_TEXT'}]}}
        self.assertIsNone(gemini_metin_ayristir(cand_no_text))

        cand_quotes = {'content': {'parts': [{'text': '"NO_TEXT"'}]}}
        self.assertIsNone(gemini_metin_ayristir(cand_quotes))

        # 2. Cümle içinde 'yazı yok' geçen meşru Türkçe el yazısı
        cand_cumle = {'content': {'parts': [{'text': 'Ödevde yazı yoksa not düş'}]}}
        self.assertEqual(gemini_metin_ayristir(cand_cumle), "Ödevde yazı yoksa not düş")

    def test_notebook_manager_ayni_gun_yeniden_baslatmada_cift_tarih_yazmaz(self):
        """Uygulama aynı gün içinde tekrar başlatıldığında deftere mükerrer tarih başlığı atılmamalı."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. İlk oturum
            nb1 = NotebookManager(app_dir=tmp_dir)
            nb1.metin_kaydet("Sabah Notu")

            # 2. İkinci oturum (aynı gün yeniden başlama)
            nb2 = NotebookManager(app_dir=tmp_dir)
            nb2.metin_kaydet("Öğleden Sonra Notu")

            with open(nb1.aktif_defter_dosyasi, "r", encoding="utf-8") as f:
                icerik = f.read()

            tarih_str = time.strftime("%d.%m.%Y")
            ayrac = f"--- {tarih_str} ---"
            # Ayraç metinde tam olarak 1 kez geçmeli!
            self.assertEqual(icerik.count(ayrac), 1)
            self.assertIn("Sabah Notu", icerik)
            self.assertIn("Öğleden Sonra Notu", icerik)

    def test_config_manager_notes_dir_yonetimi(self):
        """ConfigManager notes_dir ayarını doğru yüklemeli ve varsayılan olarak app_dir kullanmalı."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg = ConfigManager(app_dir=tmp_dir)
            self.assertEqual(cfg.notes_dir, tmp_dir)

            custom_notes = os.path.join(tmp_dir, "OzelNotlar")
            cfg.notes_dir = custom_notes
            cfg.kaydet()

            cfg2 = ConfigManager(app_dir=tmp_dir)
            self.assertEqual(cfg2.notes_dir, custom_notes)


    def test_madde_isareti_ve_sayi_bosluk_kurali(self):
        """'1.5 litre süt' veya '-5 derece' madde sanılmamalı; '•Merhaba', '*Not', '1. Toplantı' ve '- Not' madde olmalı."""
        self.assertEqual(metin_ekleme_bicimlendir("1.5 litre süt", "Genel", 5), " 1.5 litre süt")
        self.assertEqual(metin_ekleme_bicimlendir("-5 derece", "Genel", 5), " -5 derece")
        self.assertEqual(metin_ekleme_bicimlendir("1. Toplantı", "Genel", 5), "\n1. Toplantı")
        self.assertEqual(metin_ekleme_bicimlendir("- Önemli Not", "Genel", 5), "\n- Önemli Not")
        self.assertEqual(metin_ekleme_bicimlendir("•e Merhaba", "Genel", 5), "\n•e Merhaba")
        self.assertEqual(metin_ekleme_bicimlendir("•Merhaba", "Genel", 5), "\n•Merhaba")
        self.assertEqual(metin_ekleme_bicimlendir("*Not", "Genel", 5), "\n*Not")

    def test_gemini_no_text_noktalama_isaretlerini_temizler(self):
        """'NO_TEXT.' veya 'NO_TEXT!' gibi sonuna noktalama gelen yanıtlar da None olarak filtrelenmeli."""
        cand_nokta = {'content': {'parts': [{'text': 'NO_TEXT.'}]}}
        self.assertIsNone(gemini_metin_ayristir(cand_nokta))

        cand_unlem = {'content': {'parts': [{'text': 'NO_TEXT!'}]}}
        self.assertIsNone(gemini_metin_ayristir(cand_unlem))

    def test_config_manager_notes_dir_gecersizse_app_dire_doner(self):
        """notes_dir geçersiz veya yazılamayan bir dizinse güvenle app_dir'e dönmeli (tüm işletim sistemlerinde)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            dosya = os.path.join(tmp_dir, "dosya.txt")
            with open(dosya, "w", encoding="utf-8") as f:
                f.write("dosya")
            cfg = ConfigManager(app_dir=tmp_dir)
            cfg.notes_dir = os.path.join(dosya, "alt_klasor")  # Dosyanın altına dizin açılamaz
            self.assertEqual(cfg.notes_dir, tmp_dir)
            self.assertTrue(cfg.notes_dir_fallback_olustu)

    def test_ai_onay_verilmedikce_gemini_cagrilmaz(self):
        """ai_onay_verildi False iken API anahtarı ve ai_modu_aktif olsa bile Gemini'ye istek atılmamalı."""
        from src.engine import RecognitionEngine
        engine = RecognitionEngine()
        engine.gemini_vision = MagicMock()
        engine.windows_ink = MagicMock()
        engine.windows_ink.recognize.return_value = "Çevrimdışı Tanıma"

        config_mgr = MagicMock()
        config_mgr.gemini_api_key = "AIzaSyTest"
        config_mgr.ai_modu_aktif = True
        config_mgr.ai_onay_verildi = False

        resim = Image.new("RGB", (100, 100), "white")
        sonuc = engine.recognize(None, resim, config_mgr)

        engine.gemini_vision.tani.assert_not_called()
        self.assertEqual(sonuc, "Çevrimdışı Tanıma")

        # Onay verildiğinde Gemini çağrılmalı
        config_mgr.ai_onay_verildi = True
        engine.gemini_vision.tani.return_value = "Online Tanıma"
        sonuc_onayli = engine.recognize(None, resim, config_mgr)
        engine.gemini_vision.tani.assert_called_once_with(resim, config_mgr)
        self.assertEqual(sonuc_onayli, "Online Tanıma")


class TestInkSessionJestAkisi(unittest.TestCase):
    """
    Gerçek ArkaPlanNotDonusturucu üretim kodunu GUI ve donanım bağımsız test eder.
    Tkinter penceresi açmadan object.__new__ ile gerçek sınıfı kurup
    gerçek metotları (jestleri_kontrol_et, fare_birakildi, _debounce_kur vb.) doğrudan sınar.
    """

    def _olustur_gercek_app(self):
        app = object.__new__(ArkaPlanNotDonusturucu)
        app.root = MagicMock()
        app.canvas = MagicMock()
        app.storage = MagicMock()
        app.config = MagicMock()
        app.engine = MagicMock()
        app.tray = MagicMock()

        app.tam_ekran_mi = False
        app.pad_genislik = 880
        app.pad_yukseklik = 420
        app.pad_x = 20
        app.pad_y = 20
        app.boyutlandiriliyor = False
        app.surukleniyor = False
        app.kalem_basili = False
        app.cizim_yapildi = False
        app.isleniyor = False
        app.yazma_modu_aktif = True
        app.bekleyen_yeni_satir = 0
        app.debounce_timer_id = None
        app.bekleme_suresi = 0.65
        app.otomatik_enter = False
        app.otomatik_yapistir = True
        app.son_x = None
        app.son_y = None
        app.son_yazma_zamani = 0
        app.stroke_baslangic_zamani = time.time()

        app.stroke_builder = None
        app.stroke_container = None
        app.titreme_filtresi = TitremeFiltresi()
        app.aktif_noktalar = []
        app.tum_stroke_noktalari = []

        app.image = Image.new("RGB", (880, 420), "white")
        app.draw = ImageDraw.Draw(app.image)

        app.buton_tiklandi_mi = MagicMock(return_value=False)
        app.butonlari_ciz = MagicMock()
        app.tamponu_temizle = MagicMock()
        return app

    def test_bos_tuvalde_dikey_cizgi_yeni_satir_ekler_donusturme_cagirmaz(self):
        """Gerçek ArkaPlanNotDonusturucu: Boş tuvalde dikey çizgi API çağırmaz, doğrudan yeni satır ekler."""
        app = self._olustur_gercek_app()
        app.tetikle_donusturme = MagicMock()

        app.aktif_noktalar = [Point(100, 50), Point(102, 80), Point(103, 110), Point(105, 160), Point(107, 220)]
        app.stroke_baslangic_zamani = time.time() - 0.15

        jest_oldu = app.jestleri_kontrol_et()

        self.assertTrue(jest_oldu)
        app.canvas.delete.assert_any_call("stroke_current")
        app.tetikle_donusturme.assert_not_called()
        app.storage.yeni_satir_ekle.assert_called_once()

    def test_dolu_tuvalde_dikey_cizgi_donusturme_tetikler_ve_jest_cizgisi_resme_girmez(self):
        """Gerçek ArkaPlanNotDonusturucu: Dolu tuvalde dikey çizgi jesti görselden ayıklanıp dönüşüm tetiklenmeli."""
        app = self._olustur_gercek_app()
        app.tetikle_donusturme = MagicMock()

        # Tuvalde önceki gerçek el yazısı vuruşu var
        app.tum_stroke_noktalari = [[Point(10, 10), Point(20, 20)]]
        app.cizim_yapildi = True

        # Jest hareketi aktif noktalara geldi ve fare_hareket gibi draw üzerine çizgi çekti
        app.aktif_noktalar = [Point(100, 50), Point(102, 80), Point(103, 110), Point(105, 160), Point(107, 220)]
        app.draw.line([100, 50, 107, 220], fill="black", width=3)
        app.stroke_baslangic_zamani = time.time() - 0.15

        jest_oldu = app.jestleri_kontrol_et()

        self.assertTrue(jest_oldu)
        app.canvas.delete.assert_called_with("stroke_current")
        app.tetikle_donusturme.assert_called_once()
        self.assertEqual(app.bekleyen_yeni_satir, 1)

        # Görüntüde dikey çizgi (100, 50 -> 107, 220) OLMAMALI, yalnız tum_stroke_noktalari bulunmalı
        pixel = app.image.getpixel((105, 160))
        self.assertEqual(pixel, (255, 255, 255))  # Beyaz olmalı!

    def test_donusum_surerken_yazilan_kelime_donusum_bitince_debounce_kurar(self):
        """Gerçek ArkaPlanNotDonusturucu: Dönüşüm sırasında yeni kelime yazılırsa, dönüşüm tamamlanınca debounce zamanlayıcısı kurulmalı."""
        app = self._olustur_gercek_app()
        app.isleniyor = True

        # Kullanıcı vuruşu tamamladı
        app.aktif_noktalar = [Point(50, 50), Point(60, 60), Point(70, 70)]
        app.kalem_basili = True
        event = MagicMock()
        event.x, event.y = 70, 70
        app.fare_birakildi(event)

        self.assertTrue(app.cizim_yapildi)
        # Dönüşüm sürdüğü için fare_birakildi zamanlayıcı kuramaz
        self.assertIsNone(app.debounce_timer_id)

        # Arka plan dönüşümü tamamlandı ve UI thread'e bilgi geldi:
        app._donusturme_tamamlandi_bos()

        # Artık isleniyor False ve _debounce_kur çalışarak root.after'ı tetikledi!
        self.assertFalse(app.isleniyor)
        self.assertTrue(app.root.after.called)
        cagri_ms = app.root.after.call_args[0][0]
        self.assertGreaterEqual(cagri_ms, 60)
        self.assertLessEqual(cagri_ms, int(app.bekleme_suresi * 1000))
        self.assertEqual(app.root.after.call_args[0][1], app._otomatik_donustur_tetikle)

    def test_debounce_gecen_sureye_gore_kalan_sureyi_hesaplar(self):
        """Kullanıcı çizimi bitireli 500ms olmuşsa debounce kalan ~150ms kurmalı; süre dolmuşsa en az 60ms kurmalı."""
        app = self._olustur_gercek_app()
        app.cizim_yapildi = True
        app.isleniyor = False
        app.bekleme_suresi = 0.65

        # 1. 0.50 saniye önce yazılmış
        app.son_yazma_zamani = time.time() - 0.50
        app._debounce_kur()
        cagri_ms = app.root.after.call_args[0][0]
        self.assertAlmostEqual(cagri_ms, 150, delta=40)

        # 2. 1.0 saniye önce yazılmış (süre çoktan dolmuş)
        app.son_yazma_zamani = time.time() - 1.0
        app._debounce_kur()
        cagri_ms_gecikmeli = app.root.after.call_args[0][0]
        self.assertEqual(cagri_ms_gecikmeli, 60)

    def test_donusum_surerken_dikey_cizgi_cizgiyi_tuvalden_ve_resimden_temizler(self):
        """Gerçek ArkaPlanNotDonusturucu: Dönüşüm sürerken gelen fiskede hem tuval hem self.image tertemiz kalmalı."""
        app = self._olustur_gercek_app()
        app.isleniyor = True

        app.aktif_noktalar = [Point(100, 50), Point(102, 80), Point(103, 110), Point(105, 160), Point(107, 220)]
        app.draw.line([100, 50, 107, 220], fill="black", width=3)
        app.stroke_baslangic_zamani = time.time() - 0.15

        jest_oldu = app.jestleri_kontrol_et()

        self.assertTrue(jest_oldu)
        app.canvas.delete.assert_called_with("stroke_current")
        self.assertEqual(app.bekleyen_yeni_satir, 1)

        # Image üzerindeki dikey çizgi silinmiş olmalı
        pixel = app.image.getpixel((105, 160))
        self.assertEqual(pixel, (255, 255, 255))

    def test_titreme_filtresi_mikro_paraziti_yutar(self):
        """Sensörün 1.2 pikselden az mikro titreşimlerinde None dönerek gürültüyü yok etmeli."""
        filtre = TitremeFiltresi(aktif=True, min_mesafe=1.5)
        p1 = filtre.baslat(100.0, 100.0, t=1.0)
        self.assertEqual(p1.x, 100.0)
        self.assertEqual(p1.y, 100.0)

        # 0.5 piksellik mikro titreşim
        p_gurultu = filtre.filtrele(100.3, 100.4, t=1.05)
        self.assertIsNone(p_gurultu)

    def test_titreme_filtresi_yavas_yazarken_yumusatir(self):
        """Yavaş çizimde dinamik alfa düşerek ani sıçramayı yumuşatmalı."""
        filtre = TitremeFiltresi(aktif=True, min_mesafe=1.0, min_alfa=0.25, maks_alfa=0.90, hiz_esigi=200.0)
        filtre.baslat(100.0, 100.0, t=1.0)

        # Yavaşça sağa 10 piksel hareket (hız = 10 px / 1.0 saniye = 10 px/s, çok yavaş)
        p = filtre.filtrele(110.0, 100.0, t=2.0)
        self.assertIsNotNone(p)
        # Filtrelenmiş X değeri ham 110 yerine yumuşatılarak ~102.5 civarında olmalı
        self.assertLess(p.x, 105.0)
        self.assertGreater(p.x, 100.5)

    def test_titreme_filtresi_hizli_cizgide_gecikmesiz_takip_eder(self):
        """Hızlı fiske veya çizgide alfa maksimuma çıkarak kalemi anında takip etmeli."""
        filtre = TitremeFiltresi(aktif=True, min_mesafe=1.0, min_alfa=0.25, maks_alfa=0.95, hiz_esigi=100.0)
        filtre.baslat(100.0, 100.0, t=1.0)

        # 0.05 saniyede 100 piksel hareket (hız = 2000 px/s, çok hızlı)
        p = filtre.filtrele(200.0, 100.0, t=1.05)
        self.assertIsNotNone(p)
        # Hızlı vuruşta nokta neredeyse doğrudan kalemin ucuna ulaşmalı
        self.assertGreater(p.x, 190.0)

    def test_titreme_filtresi_devre_disiyken_ham_koordinat_doner(self):
        """Filtre kapalıysa mikro titreşimler de dahil her nokta olduğu gibi iletilmeli."""
        filtre = TitremeFiltresi(aktif=False, min_mesafe=2.0)
        filtre.baslat(100.0, 100.0)
        p = filtre.filtrele(100.2, 100.1)
        self.assertIsNotNone(p)
        self.assertEqual(p.x, 100.2)
        self.assertEqual(p.y, 100.1)

    def test_titreme_filtresi_sifirla_hafizayi_temizler(self):
        """Vuruş bırakıldığında sifirla() hafızayı temizlemeli, yeni vuruş bağımsız başlamalı."""
        filtre = TitremeFiltresi(aktif=True)
        filtre.baslat(50.0, 50.0)
        filtre.filtrele(60.0, 60.0)
        filtre.sifirla()

        self.assertIsNone(filtre.son_filtrelenmis_x)
        self.assertIsNone(filtre.son_filtrelenmis_y)
        p_yeni = filtre.filtrele(200.0, 200.0)
        self.assertEqual(p_yeni.x, 200.0)
        self.assertEqual(p_yeni.y, 200.0)


if __name__ == "__main__":
    unittest.main()
