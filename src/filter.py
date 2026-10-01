"""
InkScribe Pro - Titreme Önleme ve Kalem Yumuşatma Filtresi (Jitter & Tremor Filter)
Düşük maliyetli grafik tabletlerdeki (VEIKK, XP-Pen, Huion vb.) sensör gürültüsünü,
el titremesini ve mikro-sapmaları hıza duyarlı dinamik alçak geçiren filtre
(Adaptive Low-Pass / 1-Euro mantığı) ile ortadan kaldırır.
"""
import math
import time
from collections import namedtuple

Point = namedtuple("Point", ["x", "y"])


class TitremeFiltresi:
    """
    Kalem vuruşundaki titremeleri ve sensör parazitlerini temizler.

    Özellikler:
    - Deadband (Ölü Bölge): Kalem sabit dururken veya çok ufak titrerken oluşan mikro-sıçramaları eler.
    - Hıza Duyarlı Yumuşatma (Adaptive Smoothing):
      * Yavaş yazarken: Titremeleri yok etmek için güçlü yumuşatma uygular (temiz harf kıvrımları).
      * Hızlı yazarken: Gecikmeyi (latency) sıfıra indirir; kalemin ucu anında ve kesintisiz takip edilir.
    - Tükenmez Kalem Hissi: Çizgi kırıklıklarını önler, OCR ve Windows Ink motoruna pürüzsüz vektör iletir.
    """

    def __init__(self, aktif=True, min_mesafe=1.2, min_alfa=0.28, maks_alfa=0.92, hiz_esigi=160.0):
        self.aktif = bool(aktif)
        self.min_mesafe = float(min_mesafe)
        self.min_alfa = float(min_alfa)
        self.maks_alfa = float(maks_alfa)
        self.hiz_esigi = float(hiz_esigi)

        self.son_ham_x = None
        self.son_ham_y = None
        self.son_filtrelenmis_x = None
        self.son_filtrelenmis_y = None
        self.son_zaman = None

    def sifirla(self):
        """Vuruş bittiğinde filtre durumunu sıfırlar."""
        self.son_ham_x = None
        self.son_ham_y = None
        self.son_filtrelenmis_x = None
        self.son_filtrelenmis_y = None
        self.son_zaman = None

    def baslat(self, x, y, t=None):
        """Yeni bir vuruş başladığında ilk noktayı kaydeder."""
        if t is None:
            t = time.time()
        self.son_ham_x = float(x)
        self.son_ham_y = float(y)
        self.son_filtrelenmis_x = float(x)
        self.son_filtrelenmis_y = float(y)
        self.son_zaman = float(t)
        return Point(self.son_filtrelenmis_x, self.son_filtrelenmis_y)

    def filtrele(self, x, y, t=None):
        """
        Gelen ham koordinatları filtreler.
        Eğer hareket mikro-titreme eşiğinin altındaysa None döner (gürültü elenir).
        Aksi takdirde filtrelenmiş (pürüzsüz) Point döner.
        """
        if not self.aktif:
            return Point(float(x), float(y))

        if self.son_filtrelenmis_x is None:
            return self.baslat(x, y, t)

        if t is None:
            t = time.time()

        x = float(x)
        y = float(y)

        # 1. Mesafe Kontrolü (Mikro Sensör Gürültüsü / Titreme Eşiği)
        ham_dx = x - self.son_ham_x
        ham_dy = y - self.son_ham_y
        ham_mesafe = math.hypot(ham_dx, ham_dy)

        if ham_mesafe < self.min_mesafe:
            # Çok küçük titreme, gereksiz testere dişi dalgalanmayı önlemek için yutulur
            return None

        # 2. Hız Hesabı (piksel / saniye)
        dt = max(1e-4, float(t) - float(self.son_zaman))
        hiz = ham_mesafe / dt

        # 3. Dinamik Alfa Katsayısı (Hıza göre uyarlanır)
        # Yavaşken alfa küçülür (güçlü yumuşatma), hızlandıkça alfa büyür (0 gecikme)
        hiz_orani = min(1.0, hiz / self.hiz_esigi)
        alfa = self.min_alfa + hiz_orani * (self.maks_alfa - self.min_alfa)

        filtrelenmis_x = alfa * x + (1.0 - alfa) * self.son_filtrelenmis_x
        filtrelenmis_y = alfa * y + (1.0 - alfa) * self.son_filtrelenmis_y

        self.son_ham_x = x
        self.son_ham_y = y
        self.son_filtrelenmis_x = filtrelenmis_x
        self.son_filtrelenmis_y = filtrelenmis_y
        self.son_zaman = t

        return Point(filtrelenmis_x, filtrelenmis_y)
