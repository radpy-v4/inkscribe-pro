# InkScribe Pro — Kod İncelemesi ve İyileştirme Önerileri

*Kapsam: `inkscribe-pro-main.zip` (tüm `src/` modülleri, testler, CI ve build dosyaları). Test paketi çalıştırılamadı: sandbox'ta `tkinter` yok ve Windows'a özgü API'ler kullanılıyor. Pen/arayüz davranışları gerçek donanımda denenmedi; yalnızca motor ve filtre mantığı için küçük deneyler yapıldı.*

## Genel Değerlendirme

Proje düzenli. Config yazımı atomik, AI için açık onay akışı var, loglar not içeriğini yazmıyor, Gemini'den Windows Ink'e düşen yedek zincir ve jestler için testler mevcut. Sorunlar daha çok güvenlik/yan etki ve mimari tarafında.

## Öncelik 1: Gerçek Hatalar ve Riskli Davranışlar

1. **Geçersiz API anahtarı model ayarını bozuyor (doğrulandı).** `engine.py`, her HTTP 400'ü "thinkingConfig desteklenmiyor" diye yorumluyor. Gemini yanlış anahtara da 400 döndürüyor. Deneyde modelin `thinking_desteklemeyenler` listesine kalıcı eklendiği ve `config.json`'a yazıldığı görüldü. Ayrıca aynı istek boşuna iki kez gönderiliyor. Çözüm: hata gövdesinde "thinking" geçip geçmediğine bakıp yalnızca o durumda cache'e yazmak.
2. **İki farklı giriş noktası var.** Güvenlik düzeltmeleri `safe_ui.py` alt sınıfına yama olarak eklenmiş, ama `ui.py` hâlâ eski davranışta: `os._exit(0)`, AI onayında `default="yes"`, yeniden boyutlandırmada çizim kaybı. `src/__init__.py` ise `ui.main`'i dışa aktarıyor; yani `from src import main` güvensiz sürümü çalıştırır. Çözüm: düzeltmeleri doğrudan `ui.py`'ye taşıyıp `safe_ui.py`'yi kaldırmak.
3. **Gezinme jestleri varsayılan olarak açık.** `ui.py` yorumu "varsayılan kapalı" diyor, ama `ConfigManager` değeri `True` yapıyor. Tuval boşken `←` jesti başka uygulamaya Ctrl+Z gönderiyor, `↵` ve `→` ise Enter/Tab basıyor. Yanlış algılanan tek bir vuruş başka bir programda veri bozabilir. Çözüm: varsayılanı kapalı yapmak; Ctrl+Z göndermeyi kaldırmak veya ayrı bir ayara bağlamak.
4. **Pano üzerine yazılıyor ve geri yüklenmiyor.** `panoya_ve_dosyaya_aktar` kullanıcının panosunu siliyor ve el yazısı metin Win+V geçmişine düşüyor. Çözüm: panoyu yedekleyip geri yüklemek ya da metni `SendInput` ile Unicode karakter olarak yazmak.
5. **Otomatik yapıştırma ile LLM çıktısı birleşiyor.** Gemini'nin ürettiği metin doğrudan son aktif pencereye yapıştırılıyor. "Otomatik Enter" açıkken bu, terminalde komut çalıştırabilir. Çözüm: Otomatik Enter kapalı kalmalı; hedef pencerenin hâlâ aynı olduğu yapıştırmadan önce doğrulanmalı.
6. **API anahtarı `config.json`'da düz metin.** Çözüm: Windows Credential Manager (`keyring` ile DPAPI).
7. **Performans sorunları.**
   - `son_satirlari_oku` tüm not dosyasını okuyor ve `butonlari_ciz` her toast, mod ve defter değişiminde bunu çağırıyor. Dosya büyüdükçe arayüz takılır. Dosyanın sonundan okumak yeterli.
   - Her çizgi parçası ayrı bir canvas öğesi; bir sayfalık yazıda binlerce öğe oluşur. Vuruş başına tek bir polyline kullanılmalı.

## Öncelik 2: Mimari ve Tutarlılık

- **`ArkaPlanNotDonusturucu` 1450 satırlık tek sınıf.** Çizim durumu, jest makinesi, canvas çizimi, kısayollar, thread yönetimi ve tuş enjeksiyonu iç içe. Çizim oturumunu (vuruşlar, undo, debounce), çıktı gönderimini (pano/klavye) ve arayüzü ayırmak hem Tk'siz test yazmayı hem bakımı kolaylaştırır.
- **Thread güvenliği.** Tepsi menüsü bazı işlemleri doğrudan tepsi thread'inde çalıştırıyor (`otomatik_yapistir_degistir`, `baslangic_durumu_degistir`, `notlar_dosyasini_ac`). Diğerleri başka thread'den `root.after(0, ...)` çağırıyor. Tkinter bunu çoğunlukla tolere eder ama garanti vermez. Tek bir `queue.Queue` ve ana thread'de `after` ile okuma daha sağlam.
- **Undo modeli tutarsız.** `↶` düğmesi tuvalde çizim varken geri almayı reddediyor, `←` jesti ise son vuruşu siliyor. Ayrıca yalnızca tek seviye geri alma var.
- **Karalama jesti tüm tuvali siliyor.** Karalamanın kestiği vuruşları silmek (bbox kesişimi) daha doğal ve daha az yıkıcı olur.
- **Ayar tutarsızlıkları.** `bekleme_suresi` kodda 2.5, `config.example.json`'da 1.4, `ui.py` fallback'inde 3.5, tepsi menüsünde "3.5 (Önerilen)". Tek bir varsayılan belirlenmeli.
- **Model adları sabit kodlanmış.** `gemini-3.5-flash-lite` gibi adlar doğrulanamadı. "Emekli model" listesi zamanla eskiyecek ve kullanıcının seçtiği geçerli bir model sessizce başka modelle değiştirilebiliyor. Modelleri `models.list` ile dinamik almak ya da yalnızca 404/410'da yedeğe düşmek daha dayanıklı.
- Süre ölçümlerinde `time.time()` yerine `time.monotonic()` kullanılmalı.

## Öncelik 3: Tanıma Kalitesi

- **Windows Ink Türkçe sezgisi.** `recognize`, ilk 4 aday içinde Türkçe harf içeren birini tercih ediyor. "sis" yerine "şiş" gibi yanlış seçimlere yol açabilir. Bu sezgiyi kapatıp doğruluğu ölçmek mantıklı.
- **Gemini'ye giden görüntü küçük.** En fazla 650 px genişliğe BILINEAR ile küçültülüp JPEG kalite 78 ile gönderiliyor. 880 px'lik pedde yazılan geniş satırlar için yazı küçülür. PNG veya daha yüksek çözünürlük denenebilir.
- **"Geveze yanıt" filtresi alt dize arıyor.** Yanıtın herhangi bir yerinde "yazı bulunamadı" geçen gerçek bir not da atılır. Yalnızca tam eşleşme veya başlangıç eşleşmesi kontrol edilmeli.
- **Titreme filtresi.** Deneyde vuruş sonundaki gecikme ihmal edilebilir çıktı (250 px/sn'de 0.4 px). Ancak eşikler piksel cinsinden ve DPI ile ölçeklenmiyor. Tanıyıcıya filtrelenmiş yerine ham noktaları vermek, filtreyi yalnızca görüntüde kullanmak düşünülebilir.
- **Pen özellikleri.** Tk yalnızca fare olaylarını görüyor; bu yüzden basınç ve palm rejection yok. Uzun vadede Qt (`QTabletEvent`) bunu çözer.

## Öncelik 4: Build, CI ve Test

- **Güvenlik testleri CI'da çalışmıyor.** CI ve `build.ps1` yalnızca `tests/test_logic.py`'yi çalıştırıyor; `test_safety.py` hiç koşmuyor. `py_compile app.py` de yalnızca tek dosyayı derliyor. Çözüm: `pytest tests/` ve `python -m compileall src`.
- **Testler Tk'ye bağlı.** `test_logic.py`, `src.ui`'yi içe aktardığı için `tkinter` gerektiriyor; "GUI gerekmez" açıklaması tam doğru değil. Mantık ayrı bir sınıfa çıkınca bu da düzelir. 400 hatası için bir regresyon testi de eklenmeli.
- **`requirements.txt`:** sürümler sabitlenmemiş ve `pyinstaller` çalışma bağımlılıkları arasında. Bir `requirements-dev.txt` ayrılmalı.
- **`TabletNotAlici.spec`:** `upx=True` ve imzasız exe, global klavye kancasıyla birleşince antivirüs/SmartScreen yanlış pozitifi riskini artırır (tahmin; test edilmedi). UPX kapatılmalı, mümkünse exe imzalanmalı. `datas += [('src','src')]` gereksiz; `excludes` ve OCR hidden import'ları eski EasyOCR döneminden kalmış görünüyor.
- **Kısayollar bastırılmıyor.** `pynput` F8/F9/F10 tuşlarını başka uygulamalara da iletir. F10 birçok programda menü çubuğunu açar; IDE'lerde F8/F9 hata ayıklama tuşlarıdır. Varsayılanlar değiştirilmeli (örn. Ctrl+Alt+bir tuş).
- `.gitignore` içindeki `*.png`/`*.jpg`, README ekran görüntülerinin eklenmesini engelliyor.

## Önerilen Uygulama Sırası

1. 400 hatası düzeltmesi ve testi (küçük, net).
2. Gezinme jestlerini varsayılan kapalı yapmak ve Ctrl+Z gönderimini kaldırmak.
3. `safe_ui.py` düzeltmelerini `ui.py`'ye birleştirmek ve CI'a `test_safety` eklemek.
4. `son_satirlari_oku` ve canvas polyline performans düzeltmeleri.
5. Pano yedekleme/geri yükleme ve API anahtarını keyring'e taşımak.
