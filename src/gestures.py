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


def dikey_cizgi_jesti_mi(noktalar, gecen_sure):
    """
    Hızlı ve dik bir aşağı çizginin Enter (Yeni Satır) jesti olup olmadığını belirler.
    Hızlı bir fiske (flick) hareketi (< 0.35 saniye, dy > 130, dx < 30) olmalıdır.
    """
    if len(noktalar) < 5 or gecen_sure >= 0.35:
        return False

    p_ilk = noktalar[0]
    p_son = noktalar[-1]
    dy = p_son.y - p_ilk.y
    dx = abs(p_son.x - p_ilk.x)

    return dy > 130 and dx < 30 and (dy / max(1.0, dx)) > 4.0
