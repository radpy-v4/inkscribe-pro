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
    Yukarıdan aşağıya inip ardından sola doğru uzanan keskin köşe/kanca hareketi.
    'S', 's', 'c', '5', '8', '?' gibi kıvrımlı el yazısı harfleriyle KESİNLİKLE karışmaz.
    """
    if len(noktalar) < 6 or gecen_sure >= 1.2 or gecen_sure < 0.05:
        return False

    p_ilk = noktalar[0]
    p_son = noktalar[-1]

    y_degerleri = [p.y for p in noktalar]
    x_degerleri = [p.x for p in noktalar]

    y_max = max(y_degerleri)
    idx_y_max = y_degerleri.index(y_max)

    # 1. 'S' Harfi ve Dalgalı Çizgi Koruması:
    # 'S' harfinde vuruş önce sola, sonra orta gövdede sağa, sonra alta sola kıvrılır.
    # Gerçek Enter kancasında ise el sadece aşağı iner ve sola döner; asla belirgin sağa gitmez!
    saga_hareket = sum(max(0.0, x_degerleri[i] - x_degerleri[i - 1]) for i in range(1, len(x_degerleri)))
    if saga_hareket > (12.0 * scale):
        return False

    # Yatay yön değişimleri kontrolü ('S' veya dalgalı eğrilerde en az 2 yön değişimi olur)
    yon_degisimleri = 0
    son_yon = 0
    for i in range(1, len(x_degerleri)):
        dx = x_degerleri[i] - x_degerleri[i - 1]
        if abs(dx) > (5.0 * scale):
            yon = 1 if dx > 0 else -1
            if son_yon != 0 and yon != son_yon:
                yon_degisimleri += 1
            son_yon = yon
    if yon_degisimleri >= 2:
        return False

    # 2. Dikey İniş ve Köşe Sıralaması
    min_asagi_inme = 35.0 * scale
    dy_down = y_max - p_ilk.y
    if dy_down < min_asagi_inme:
        return False

    # Köşe en azından vuruşun ikinci yarısında olmalı (önce aşağı inilmeli)
    if idx_y_max < len(noktalar) * 0.35:
        return False

    # İniş kolunun düzgünlüğü: Dikey iniş boyunca X sapması sınırlı olmalı
    inis_x = x_degerleri[:idx_y_max + 1]
    if (max(inis_x) - min(inis_x)) > (20.0 * scale):
        return False

    # 3. Sola Dönüş Kolu (Yatay Kol)
    min_sola_donus = 24.0 * scale
    dx_left = inis_x[-1] - p_son.x
    if dx_left < min_sola_donus:
        return False

    # Yatay kol boyunca Y sapması küçük olmalı (düz veya hafif yatay bir çizgi)
    donus_y = y_degerleri[idx_y_max:]
    if (max(donus_y) - min(donus_y)) > (16.0 * scale):
        return False

    # Sol kuyruğun yukarı aşırı kıvrılmaması (J, U, veya C harfini önleme)
    if (y_max - p_son.y) > (16.0 * scale):
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
