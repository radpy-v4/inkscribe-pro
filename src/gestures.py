"""
TabletNotAlici - Jest Algılama Algoritmaları (Gestures)
Donanımdan bağımsız saf algoritmalar içerir.
"""


def karalama_jesti_mi(noktalar):
    """
    Çizilen hareketin karalama (scratch-out) ile ekranı temizleme jesti olup olmadığını belirler.
    Aynı dar bölgede (span_x) ileri-geri salınım yoğunluğunu (total path / span) kontrol eder.
    Bitişik el yazısı (örn: 'mmm', 'minimum') gibi doğal yazıları elemek için korumalıdır.
    """
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


def dikey_cizgi_jesti_mi(noktalar, gecen_sure, dy_min=70, dx_max=45):
    """
    Hızlı ve dik bir aşağı çizginin Enter (Yeni Satır) jesti olup olmadığını belirler.
    Daha doğal el hareketi toleransına sahiptir (< 0.65 saniye).
    """
    if len(noktalar) < 3 or gecen_sure >= 0.65:
        return False

    p_ilk = noktalar[0]
    p_son = noktalar[-1]
    dy = p_son.y - p_ilk.y
    dx = abs(p_son.x - p_ilk.x)

    return dy > dy_min and dx < dx_max and (dy / max(1.0, dx)) > 2.2


def enter_kancasi_jesti_mi(noktalar, gecen_sure, scale=1.0):
    """
    Klasik Enter Kancası (↵ / ↲) jesti:
    Yukarıdan aşağıya inip ardından sola doğru uzanan köşe/kanca hareketi.
    Klavyedeki Enter simgesine dayanır; doğal el yazısı harfleriyle (l, i, 1, L) asla karışmaz.
    """
    if len(noktalar) < 4 or gecen_sure >= 1.2 or gecen_sure < 0.02:
        return False

    p_ilk = noktalar[0]
    p_son = noktalar[-1]

    # Dinamik DPI ölçekli eşikler (küçük ve hızlı el hareketlerini de yakalar)
    min_asagi_inme = 25.0 * scale
    min_sola_donus = 16.0 * scale

    y_degerleri = [p.y for p in noktalar]
    x_degerleri = [p.x for p in noktalar]

    y_max = max(y_degerleri)
    x_max = max(x_degerleri)
    idx_y_max = y_degerleri.index(y_max)

    # 1. Belirgin dikey iniş kontrolü (Aşağı hareket)
    dy_down = y_max - p_ilk.y
    if dy_down < min_asagi_inme:
        return False

    # 2. Belirgin sola dönüş kontrolü (Sola hareket)
    # Bitiş noktası en sağdaki köşeden belirgin şekilde solda olmalı
    dx_left = x_max - p_son.x
    if dx_left < min_sola_donus:
        return False

    # Bitiş noktası başlangıç noktasının çok sağında bitemez ('L' harfi gibi sağa dönemez!)
    if p_son.x > p_ilk.x + (6.0 * scale):
        return False

    # 3. Sıralama kontrolü: En dip nokta vuruşun en başında olamaz (aşağı inip sola dönülmeli)
    if idx_y_max == 0:
        return False

    # 4. Sol kuyruğun yukarı aşırı kıvrılmaması (J veya U harfini önleme)
    if (y_max - p_son.y) > (dy_down * 0.75):
        return False

    return True


def sagdan_sola_cizgi_jesti_mi(noktalar, gecen_sure, scale=1.0):
    """
    Sağdan Sola Yatay Çizgi (←) jesti:
    Sağdan sola doğru hızlı ve belirgin bir çizgi çekme hareketi (Geri Al / Sil).
    """
    if len(noktalar) < 3 or gecen_sure >= 0.85 or gecen_sure < 0.02:
        return False

    p_ilk = noktalar[0]
    p_son = noktalar[-1]

    # Sağdan sola doğru olmalı
    dx = p_ilk.x - p_son.x
    min_dx = 38.0 * scale
    if dx < min_dx:
        return False

    y_degerleri = [p.y for p in noktalar]
    y_span = max(y_degerleri) - min(y_degerleri)
    dy = abs(p_son.y - p_ilk.y)

    # Dikey sapma yatay mesafenin yarısından az olmalı (yatay baskın çizgi)
    if y_span > dx * 0.65 or dy > dx * 0.50:
        return False

    # İleri-geri zikzak olmamalı (tek yönlü sola hareket)
    x_degerleri = [p.x for p in noktalar]
    saga_donusler = sum(1 for i in range(1, len(x_degerleri)) if x_degerleri[i] - x_degerleri[i - 1] > 8.0 * scale)
    if saga_donusler > 1:
        return False

    return True


def soldan_saga_cizgi_jesti_mi(noktalar, gecen_sure, scale=1.0):
    """
    Soldan Sağa Yatay Çizgi (→) jesti:
    Soldan sağa doğru hızlı ve belirgin bir çizgi çekme hareketi (Tab Tuşu).
    Form alanları veya tablo hücreleri arasında klavyeye dokunmadan ilerlemeyi sağlar.
    """
    if len(noktalar) < 3 or gecen_sure >= 0.85 or gecen_sure < 0.02:
        return False

    p_ilk = noktalar[0]
    p_son = noktalar[-1]

    # Soldan sağa doğru olmalı
    dx = p_son.x - p_ilk.x
    min_dx = 38.0 * scale
    if dx < min_dx:
        return False

    y_degerleri = [p.y for p in noktalar]
    y_span = max(y_degerleri) - min(y_degerleri)
    dy = abs(p_son.y - p_ilk.y)

    # Dikey sapma yatay mesafenin yarısından az olmalı (yatay baskın çizgi)
    if y_span > dx * 0.65 or dy > dx * 0.50:
        return False

    # İleri-geri zikzak olmamalı (tek yönlü sağa hareket)
    x_degerleri = [p.x for p in noktalar]
    sola_donusler = sum(1 for i in range(1, len(x_degerleri)) if x_degerleri[i - 1] - x_degerleri[i] > 8.0 * scale)
    if sola_donusler > 1:
        return False

    return True
