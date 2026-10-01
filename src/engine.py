import io
import time
import json
import base64
import asyncio
import urllib.request
import urllib.error
from PIL import Image
from .config import logger
try:
    import winrt.windows.ui.input.inking as inking
except Exception as _e:
    inking = None
    logger.warning(f"[Windows Ink] winrt import edilemedi: {_e}")


def gemini_metin_ayristir(candidate):
    """Gemini API aday yanıtından temiz Türkçe metni ayıklar."""
    finish_reason = candidate.get('finishReason', '')
    if finish_reason and finish_reason != 'STOP':
        logger.warning(f"[AI Vision] Sıradışı finishReason: {finish_reason}")

    content_obj = candidate.get('content', {})
    parts_list = content_obj.get('parts', [])
    txt = ''.join(p.get('text', '') for p in parts_list if isinstance(p, dict)).strip()

    if txt.startswith("```") and txt.endswith("```"):
        lines = txt.split("\n")
        txt = "\n".join(lines[1:-1]).strip() if len(lines) >= 3 else txt.replace("```", "").strip()

    # Modelin 'NO_TEXT' veya tam reddetme/açıklama yanıtlarını filtrele
    temiz_kod = txt.strip().strip("`'\".,!?:; \n\r\t").upper()
    if temiz_kod == "NO_TEXT":
        return None

    txt_lower = txt.strip().lower()
    # "yazı yok" tek başına aranmaz (örn: "Ödevde yazı yoksa not düş" meşru yazıdır)
    # Yalnızca bariz red ve açıklama cümleleri filtrelenir
    geveze_kaliplar = (
        "herhangi bir el yazısı", "el yazısı bulunamadı", "el yazısı göremiyorum",
        "metin bulunamadı", "metin göremiyorum", "okunabilir bir metin yok",
        "görselde el yazısı yok", "yazı bulunamadı", "görselde yazı yok"
    )
    if any(k in txt_lower for k in geveze_kaliplar):
        return None

    return txt if txt else None


class WindowsInkRecognizer:
    """100% Çevrimdışı, Donanım Hızlandırmalı Yerel Windows Ink El Yazısı Motoru."""

    def __init__(self):
        if not inking:
            logger.warning("[Windows Ink] winrt modülü bulunamadı. Offline motor devre dışı.")
            self.ink_container = None
            self.secilen_motor_adi = "Mevcut Değil"
            return

        logger.info("[1/3] Windows Yerel El Yazısı Tanıma Motoru (Windows Ink) başlatılıyor...")
        self.ink_container = inking.InkRecognizerContainer()
        self.secilen_motor_adi = "Varsayılan"

        try:
            for r in self.ink_container.get_recognizers():
                name = r.name.lower()
                if "turkish" in name or "türk" in name or name.startswith("tr-") or name == "tr":
                    self.ink_container.set_default_recognizer(r)
                    self.secilen_motor_adi = r.name
                    break
        except Exception as e:
            logger.warning(f"[Windows Ink] Dil tanıyıcı listesi taranırken istisna ({e}). Varsayılan motor devrede.")
        logger.info(f"[2/3] El yazısı motoru hazır: {self.secilen_motor_adi} (100% Çevrimdışı & Donanım Hızlandırmalı)")

    def recognize(self, stroke_container):
        if not inking or not self.ink_container or not stroke_container:
            return None
        async def run_recognition():
            return await self.ink_container.recognize_async(stroke_container, inking.InkRecognitionTarget.ALL)

        results = asyncio.run(run_recognition())
        kelimeler = []
        turkce_harfler = set("çğıöşüÇĞİÖŞÜ")

        if results:
            for res in results:
                candidates = list(res.get_text_candidates())
                if candidates:
                    secilen = candidates[0].strip()
                    for cand in candidates[:4]:
                        c_strip = cand.strip()
                        if any(ch in turkce_harfler for ch in c_strip) and not any(ch in turkce_harfler for ch in secilen):
                            secilen = c_strip
                            break
                    kelimeler.append(secilen)

        return " ".join(kelimeler).strip() if kelimeler else None


class GeminiVisionRecognizer:
    """Google Gemini Vision REST API İstemcisi - Model Yedekleme & Hata Korumalı."""

    def tani(self, kirpilmis_resim, config_mgr):
        ai_onay = getattr(config_mgr, 'ai_onay_verildi', False)
        if not config_mgr.gemini_api_key or not config_mgr.ai_modu_aktif or not ai_onay:
            return None

        try:
            w, h = kirpilmis_resim.size
            if w > 650:
                h = max(1, int(h * (650 / w)))
                w = 650
                kirpilmis_resim = kirpilmis_resim.resize((w, h), Image.Resampling.BILINEAR)

            buf = io.BytesIO()
            kirpilmis_resim.convert("RGB").save(buf, format="JPEG", quality=78)
            b64_data = base64.b64encode(buf.getvalue()).decode('utf-8')

            headers = {
                'Content-Type': 'application/json',
                'X-goog-api-key': config_mgr.gemini_api_key
            }

            timeout = float(getattr(config_mgr, 'gemini_timeout', 5.0))

            def _model_cagrisi(model_adi, gonderi_verisi, call_timeout):
                url = f'https://generativelanguage.googleapis.com/v1beta/models/{model_adi}:generateContent'
                r = urllib.request.Request(url, data=json.dumps(gonderi_verisi).encode('utf-8'), headers=headers)
                with urllib.request.urlopen(r, timeout=call_timeout) as resp:
                    return json.loads(resp.read().decode())

            denenecek_modeller = [config_mgr.gemini_model] + [m for m in config_mgr.model_adaylari if m != config_mgr.gemini_model]
            model_404_aldi = False
            baslangic_zamani = time.time()
            toplam_butce = getattr(config_mgr, 'gemini_toplam_butce', 8.0)

            for index, m_adi in enumerate(denenecek_modeller):
                gecen_sure = time.time() - baslangic_zamani
                kalan_butce = toplam_butce - gecen_sure
                if index > 0 and kalan_butce <= 0.2:
                    logger.warning(f"[AI Vision] Toplam {toplam_butce}s süre bütçesi doldu. Yerel Windows Ink motoruna geçiliyor...")
                    break
                cagri_timeout = min(float(config_mgr.gemini_timeout), max(0.1, kalan_butce))

                payload = {
                    'contents': [{
                        'parts': [
                            {'text': 'Sadece bu görseldeki Türkçe el yazısını oku. Görselde hiçbir el yazısı veya metin yoksa sadece "NO_TEXT" yaz. Başka hiçbir açıklama yapma:'},
                            {
                                'inline_data': {
                                    'mime_type': 'image/jpeg',
                                    'data': b64_data
                                }
                            }
                        ]
                    }],
                    'generationConfig': {
                        'temperature': 0.0,
                        'maxOutputTokens': 500
                    }
                }
                if m_adi not in config_mgr.thinking_desteklemeyenler:
                    payload['generationConfig']['thinkingConfig'] = {
                        'thinkingBudget': 0
                    }

                try:
                    res = _model_cagrisi(m_adi, payload, cagri_timeout)
                except urllib.error.HTTPError as http_err:
                    hata_metni = http_err.read().decode('utf-8', errors='ignore')

                    if http_err.code in (404, 410):
                        logger.warning(f"[AI Vision] '{m_adi}' modeli bulunamadı/emekli edilmiş (HTTP {http_err.code}).")
                        if m_adi == config_mgr.gemini_model:
                            model_404_aldi = True
                        continue

                    if http_err.code in (429, 503):
                        sebep = "hız/kota aşımı (HTTP 429)" if http_err.code == 429 else "sunucu aşırı yoğunluğu (HTTP 503)"
                        logger.warning(f"[AI Vision] '{m_adi}' {sebep} nedeniyle yanıt veremedi. Sıradaki model deneniyor...")
                        continue

                    if ("thinking" in hata_metni.lower() or "invalid_argument" in hata_metni.lower() or http_err.code == 400) and 'thinkingConfig' in payload.get('generationConfig', {}):
                        logger.info(f"[AI Vision] '{m_adi}' için thinkingConfig desteklenmiyor, önbelleğe alınıp parametresiz deneniyor...")
                        config_mgr.thinking_desteklemeyenler.add(m_adi)
                        config_mgr.kaydet()
                        kopya_payload = dict(payload)
                        kopya_payload['generationConfig'] = dict(payload['generationConfig'])
                        kopya_payload['generationConfig'].pop('thinkingConfig', None)
                        kalan_butce = toplam_butce - (time.time() - baslangic_zamani)
                        if kalan_butce <= 0.2:
                            logger.warning(f"[AI Vision] Toplam {toplam_butce}s süre bütçesi doldu. Yerel Windows Ink motoruna geçiliyor...")
                            return None
                        retry_timeout = min(float(config_mgr.gemini_timeout), max(0.1, kalan_butce))
                        try:
                            res = _model_cagrisi(m_adi, kopya_payload, retry_timeout)
                        except urllib.error.HTTPError as retry_err:
                            retry_hata = retry_err.read().decode('utf-8', errors='ignore')
                            logger.error(f"[AI Vision API Hatası]: HTTP {retry_err.code} - {retry_hata}")
                            return None
                    else:
                        logger.error(f"[AI Vision API Hatası]: HTTP {http_err.code} ({m_adi}) - {hata_metni}")
                        return None
                except (urllib.error.URLError, TimeoutError) as net_err:
                    is_timeout = isinstance(net_err, TimeoutError) or isinstance(getattr(net_err, 'reason', None), TimeoutError) or "timed out" in str(net_err).lower()
                    if is_timeout:
                        logger.warning(f"[AI Vision] '{m_adi}' {cagri_timeout:.1f}s zaman aşımına uğradı. Sıradaki model deneniyor...")
                        continue
                    logger.warning(f"[AI Vision Ağ Hatası] '{m_adi}': {net_err}")
                    break

                if res and 'candidates' in res and res['candidates']:
                    candidate = res['candidates'][0]
                    txt = gemini_metin_ayristir(candidate)
                    if txt:
                        if model_404_aldi and m_adi != config_mgr.gemini_model:
                            logger.info(f">> [Model Otomatik Güncellendi] Eski model kapandığı için yeni varsayılan model: {m_adi}")
                            config_mgr.gemini_model = m_adi
                            config_mgr.kaydet()
                        return txt

        except Exception as e:
            logger.warning(f"[Vision AI Hızlı Geçiş]: ({e}), yerel motora aktarılıyor...")
        return None


class RecognitionEngine:
    """Windows Ink ve Gemini Vision'ı koordine eden Hibrit Tanıma Motoru."""

    def __init__(self):
        self.windows_ink = WindowsInkRecognizer()
        self.gemini_vision = GeminiVisionRecognizer()

    def recognize(self, stroke_container, kirpilmis_pil_resim, config_mgr):
        metin = None

        # 1. Aşama: Vision AI (Gemini) Hibrit Tanıma (Kullanıcı gizlilik onayı şartı aranır)
        ai_onay = getattr(config_mgr, 'ai_onay_verildi', False)
        if config_mgr.ai_modu_aktif and config_mgr.gemini_api_key and ai_onay:
            logger.info(f"[AI Vision] {config_mgr.gemini_model} modeli ile taranıyor...")
            metin = self.gemini_vision.tani(kirpilmis_pil_resim, config_mgr)
            if metin:
                logger.info(f">> [AI Vision Başarılı] ({len(metin)} karakter tanındı)")
            else:
                logger.info(">> [AI Fallback] Çevrimdışı yerel motora geçiliyor...")

        # 2. Aşama: Windows Ink (100% Offline Yerel Motor)
        if not metin:
            logger.info("[Windows Ink (Offline)] Yerel motor ile el yazısı tanınıyor...")
            metin = self.windows_ink.recognize(stroke_container)

        return metin
