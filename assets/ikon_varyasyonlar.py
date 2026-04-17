"""
Üç farklı ikon varyasyonu üret — sadece önizleme için PNG (256x256).
Kullanıcı seçtikten sonra ikon_olustur.py ile .ico dosyası üretilir.

Varyasyonlar:
  v1 — Yılan kıvrılmış havan + kafası tokmak + içinden E harfi
  v2 — E harfine dolanan yılan (kaduse tarzı)
  v3 — Terazi direğine dolanan yılan (adalet + sağlık)
"""

import os
import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ASSETS = os.path.dirname(os.path.abspath(__file__))

# Ortak renkler
TEAL_ACIK = (38, 198, 176)
TEAL_KOYU = (0, 105, 92)
TEAL_ENKOYU = (0, 77, 64, 255)
BEYAZ = (255, 255, 255, 255)
BEYAZ_KREM = (250, 248, 240, 255)
ALTIN = (255, 200, 80, 255)
ALTIN_KOYU = (210, 150, 40, 255)
GOLGE = (0, 0, 0, 90)
KIRMIZI = (220, 60, 60, 255)


# -------- Yardımcılar --------
def _lerp(a, b, t):
    return int(a + (b - a) * t)


def _mix(c1, c2, t):
    return (_lerp(c1[0], c2[0], t), _lerp(c1[1], c2[1], t),
            _lerp(c1[2], c2[2], t), 255)


def _rounded_mask(boyut: int, radius: int) -> Image.Image:
    m = Image.new("L", (boyut, boyut), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        (0, 0, boyut - 1, boyut - 1), radius=radius, fill=255)
    return m


def _gradient_bg(boyut: int) -> Image.Image:
    img = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    px = img.load()
    for y in range(boyut):
        for x in range(boyut):
            t = (x + y) / (2 * (boyut - 1))
            px[x, y] = _mix(TEAL_ACIK, TEAL_KOYU, max(0.0, min(1.0, t)))
    return img


def _glossy(boyut: int, radius: int) -> Image.Image:
    layer = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(
        (int(boyut * 0.05), int(-boyut * 0.35),
         int(boyut * 0.95), int(boyut * 0.55)),
        fill=(255, 255, 255, 55),
    )
    layer = layer.filter(ImageFilter.GaussianBlur(radius=max(1, boyut // 40)))
    mask = _rounded_mask(boyut, radius)
    out = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    out.paste(layer, (0, 0), mask)
    return out


def _cerceve(img: Image.Image, radius: int):
    boyut = img.size[0]
    d = ImageDraw.Draw(img)
    cer = max(1, boyut // 64)
    d.rounded_rectangle(
        (cer, cer, boyut - cer - 1, boyut - cer - 1),
        radius=radius - cer,
        outline=(255, 255, 255, 160),
        width=max(1, boyut // 90),
    )


def _baslat(boyut: int):
    """Arka planı hazırla (gradient + yuvarlak kare mask)."""
    radius = max(4, int(boyut * 0.22))
    bg = _gradient_bg(boyut)
    mask = _rounded_mask(boyut, radius)
    img = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    img.paste(bg, (0, 0), mask)
    _cerceve(img, radius)
    return img, radius


def _bitir(img: Image.Image, sahne: Image.Image, radius: int) -> Image.Image:
    img = Image.alpha_composite(img, sahne)
    img = Image.alpha_composite(img, _glossy(img.size[0], radius))
    return img


def _yilan_kafa(d: ImageDraw.ImageDraw, kx, ky, w, h, yon="sag"):
    """Basit yılan kafası — merkez (kx,ky), yön: 'sag' veya 'sol'."""
    d.ellipse((kx - w // 2, ky - h // 2, kx + w // 2, ky + h // 2),
              fill=BEYAZ)
    d.ellipse((kx - w // 2 + w // 10, ky - h // 2 - h // 12,
               kx + w // 2 - w // 4, ky + h // 2 - h // 4),
              fill=BEYAZ_KREM)
    # göz
    goz_r = max(2, w // 10)
    gx = kx + (w // 6 if yon == "sag" else -w // 6)
    gy = ky - h // 6
    d.ellipse((gx - goz_r, gy - goz_r, gx + goz_r, gy + goz_r),
              fill=TEAL_ENKOYU)
    d.ellipse((gx - goz_r // 3, gy - goz_r + goz_r // 3,
               gx + goz_r // 3, gy - goz_r + goz_r),
              fill=BEYAZ)
    # çatal dil
    dx = kx + (w // 2 if yon == "sag" else -w // 2)
    dy = ky + h // 8
    uzun = w // 2
    if yon == "sag":
        d.line((dx, dy, dx + uzun, dy + uzun // 4),
               fill=KIRMIZI, width=max(2, w // 18))
        d.line((dx + uzun * 3 // 4, dy + uzun // 4,
                dx + uzun, dy - uzun // 6),
               fill=KIRMIZI, width=max(2, w // 18))
    else:
        d.line((dx, dy, dx - uzun, dy + uzun // 4),
               fill=KIRMIZI, width=max(2, w // 18))
        d.line((dx - uzun * 3 // 4, dy + uzun // 4,
                dx - uzun, dy - uzun // 6),
               fill=KIRMIZI, width=max(2, w // 18))


# -------- Varyasyon 1: Yılan kıvrılmış havan + E --------
def v1(boyut: int = 256) -> Image.Image:
    SS = 4
    B = boyut * SS
    img, radius = _baslat(boyut)
    layer = Image.new("RGBA", (B, B), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = B // 2

    hav_w, hav_h = int(B * 0.64), int(B * 0.48)
    hav_x1 = cx - hav_w // 2
    hav_x2 = cx + hav_w // 2
    hav_y1 = int(B * 0.44)
    hav_y2 = hav_y1 + hav_h
    kalin = max(5, B // 9)

    # gölge + gövde
    d.arc((hav_x1 + SS * 3, hav_y1 + SS * 3, hav_x2 + SS * 3, hav_y2 + SS * 3),
          0, 180, fill=GOLGE, width=kalin + SS * 3)
    d.arc((hav_x1, hav_y1, hav_x2, hav_y2),
          0, 180, fill=BEYAZ, width=kalin)
    d.arc((hav_x1, hav_y1, hav_x2, hav_y2),
          0, 180, fill=(0, 120, 100, 140), width=max(2, SS))

    sag_ucx, sag_ucy = hav_x2, (hav_y1 + hav_y2) // 2
    sol_ucx, sol_ucy = hav_x1, (hav_y1 + hav_y2) // 2

    # kuyruk
    k = [
        (sag_ucx, sag_ucy),
        (sag_ucx + SS * 2, sag_ucy - kalin),
        (sag_ucx - SS * 4, sag_ucy - int(kalin * 1.8)),
        (sag_ucx - kalin, sag_ucy - int(kalin * 2.2)),
    ]
    d.line(k, fill=BEYAZ, width=int(kalin * 0.78), joint="curve")
    end = k[-1]
    r = int(kalin * 0.38)
    d.ellipse((end[0] - r, end[1] - r, end[0] + r, end[1] + r), fill=BEYAZ)

    # boyun — sol uçtan çapraz inen
    b = [
        (sol_ucx, sol_ucy),
        (sol_ucx - SS * 2, sol_ucy - int(kalin * 1.4)),
        (sol_ucx + SS * 4, sol_ucy - int(kalin * 2.6)),
        (int(cx - B * 0.22), int(B * 0.14)),
        (int(cx - B * 0.02), int(B * 0.10)),
        (int(cx + B * 0.18), int(B * 0.22)),
        (int(cx + B * 0.10), int(B * 0.40)),
    ]
    d.line(b, fill=BEYAZ, width=int(kalin * 0.82), joint="curve")

    kx, ky = b[-1]
    _yilan_kafa(d, kx, ky, int(kalin * 1.5), int(kalin * 1.0), yon="sag")

    # E harfi — altın
    e_x1 = cx - int(B * 0.14)
    e_x2 = cx + int(B * 0.08)
    e_y1 = int(B * 0.46)
    e_y2 = int(B * 0.78)
    e_kalin = max(4, B // 18)

    off = SS * 2
    d.rectangle((e_x1 + off, e_y1 + off, e_x2 + off, e_y2 + off), fill=GOLGE)

    d.rectangle((e_x1, e_y1, e_x1 + e_kalin, e_y2), fill=ALTIN)
    d.rectangle((e_x1, e_y1, e_x2, e_y1 + e_kalin), fill=ALTIN)
    mid_y = (e_y1 + e_y2) // 2
    d.rectangle(
        (e_x1, mid_y - e_kalin // 2,
         e_x2 - int(e_kalin * 0.7), mid_y + e_kalin // 2),
        fill=ALTIN)
    d.rectangle((e_x1, e_y2 - e_kalin, e_x2, e_y2), fill=ALTIN)
    d.rectangle((e_x1, e_y1, e_x1 + max(1, e_kalin // 4), e_y2),
                fill=(255, 240, 180, 255))

    sahne = layer.resize((boyut, boyut), Image.LANCZOS)
    return _bitir(img, sahne, radius)


# -------- Varyasyon 2: E harfine dolanan yılan --------
def v2(boyut: int = 256) -> Image.Image:
    SS = 4
    B = boyut * SS
    img, radius = _baslat(boyut)
    layer = Image.new("RGBA", (B, B), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = B // 2, B // 2

    # --- Büyük altın E harfi (merkezde) ---
    e_x1 = cx - int(B * 0.22)
    e_x2 = cx + int(B * 0.14)
    e_y1 = int(B * 0.18)
    e_y2 = int(B * 0.82)
    e_kalin = max(6, B // 11)

    off = SS * 3
    # gölge
    d.rectangle((e_x1 + off, e_y1 + off, e_x1 + e_kalin + off, e_y2 + off),
                fill=GOLGE)
    d.rectangle((e_x1 + off, e_y1 + off, e_x2 + off, e_y1 + e_kalin + off),
                fill=GOLGE)

    # E
    d.rectangle((e_x1, e_y1, e_x1 + e_kalin, e_y2), fill=ALTIN)
    d.rectangle((e_x1, e_y1, e_x2, e_y1 + e_kalin), fill=ALTIN)
    mid_y = (e_y1 + e_y2) // 2
    d.rectangle(
        (e_x1, mid_y - e_kalin // 2,
         e_x2 - int(e_kalin * 0.6), mid_y + e_kalin // 2),
        fill=ALTIN)
    d.rectangle((e_x1, e_y2 - e_kalin, e_x2, e_y2), fill=ALTIN)
    # parlaklık
    d.rectangle((e_x1, e_y1, e_x1 + max(2, e_kalin // 4), e_y2),
                fill=(255, 240, 180, 255))

    # --- Yılan — E'ye önden-arkadan dolanıyor ---
    # Yılan beyaz, koyu kenar çizgili (pul hissi)
    y_kalin = max(5, B // 14)

    # Yılan yolu: alttan sol arkadan E gövdesine sarılıyor, önden orta yatay çizgiyi geçiyor,
    # arkadan üst yatayı aşıyor, kafası sağ üstte dışarı uzanıyor.
    # Yolun "ön" ve "arka" kısımları ayrı çizilecek — böylece gerçekten dolanmış hissi verir.

    # ARKA KISIMLAR (E'nin arkasında kalan segmentler)
    arka_pts_1 = [
        (cx - int(B * 0.32), int(B * 0.75)),
        (cx - int(B * 0.12), int(B * 0.68)),
        (cx + int(B * 0.02), int(B * 0.55)),
        (cx + int(B * 0.18), int(B * 0.42)),
    ]
    arka_pts_2 = [
        (cx + int(B * 0.18), int(B * 0.42)),
        (cx + int(B * 0.06), int(B * 0.34)),
        (cx - int(B * 0.06), int(B * 0.30)),
        (cx - int(B * 0.16), int(B * 0.22)),
    ]
    d.line(arka_pts_1, fill=BEYAZ, width=y_kalin, joint="curve")
    d.line(arka_pts_1, fill=(0, 120, 100, 120), width=max(2, SS))
    d.line(arka_pts_2, fill=BEYAZ, width=y_kalin, joint="curve")
    d.line(arka_pts_2, fill=(0, 120, 100, 120), width=max(2, SS))

    # E'yi tekrar çiz — üst üste gelen yerlerde E önde kalsın (sadece ARKA için)
    d.rectangle((e_x1, e_y1, e_x1 + e_kalin, e_y2), fill=ALTIN)
    d.rectangle((e_x1, e_y1, e_x2, e_y1 + e_kalin), fill=ALTIN)
    d.rectangle(
        (e_x1, mid_y - e_kalin // 2,
         e_x2 - int(e_kalin * 0.6), mid_y + e_kalin // 2),
        fill=ALTIN)
    d.rectangle((e_x1, e_y2 - e_kalin, e_x2, e_y2), fill=ALTIN)
    d.rectangle((e_x1, e_y1, e_x1 + max(2, e_kalin // 4), e_y2),
                fill=(255, 240, 180, 255))

    # ÖN KISIMLAR (E'nin önünde)
    on_pts_1 = [
        (cx - int(B * 0.18), int(B * 0.80)),
        (cx - int(B * 0.05), int(B * 0.72)),
        (cx + int(B * 0.08), int(B * 0.60)),
        (cx + int(B * 0.18), int(B * 0.52)),
        (cx + int(B * 0.10), int(B * 0.46)),
        (cx - int(B * 0.06), int(B * 0.50)),
    ]
    on_pts_2 = [
        (cx - int(B * 0.10), int(B * 0.38)),
        (cx + int(B * 0.06), int(B * 0.34)),
        (cx + int(B * 0.14), int(B * 0.26)),
        (cx + int(B * 0.06), int(B * 0.16)),
        (cx - int(B * 0.08), int(B * 0.12)),
    ]
    d.line(on_pts_1, fill=BEYAZ, width=y_kalin, joint="curve")
    d.line(on_pts_1, fill=(0, 120, 100, 120), width=max(2, SS))
    d.line(on_pts_2, fill=BEYAZ, width=y_kalin, joint="curve")
    d.line(on_pts_2, fill=(0, 120, 100, 120), width=max(2, SS))

    # Kuyruk — başlangıç noktasında yuvarlak
    t0 = arka_pts_1[0]
    r = y_kalin // 2
    d.ellipse((t0[0] - r, t0[1] - r, t0[0] + r, t0[1] + r), fill=BEYAZ)

    # Kafa — en üst uç noktada
    kx, ky = on_pts_2[-1]
    _yilan_kafa(d, kx, ky, int(y_kalin * 1.8), int(y_kalin * 1.2), yon="sol")

    sahne = layer.resize((boyut, boyut), Image.LANCZOS)
    return _bitir(img, sahne, radius)


# -------- Varyasyon 3: Terazi + Yılan (sürekli spiral dolanım) --------
def v3(boyut: int = 256) -> Image.Image:
    SS = 4
    B = boyut * SS
    img, radius = _baslat(boyut)
    layer = Image.new("RGBA", (B, B), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = B // 2

    # --- Terazi ölçüleri ---
    direk_kalin = max(5, B // 22)
    direk_x1 = cx - direk_kalin // 2
    direk_x2 = cx + direk_kalin // 2
    direk_y1 = int(B * 0.16)
    direk_y2 = int(B * 0.84)

    kol_y = int(B * 0.22)
    kol_w = int(B * 0.62)
    kol_kalin = max(4, B // 28)
    kol_x1 = cx - kol_w // 2
    kol_x2 = cx + kol_w // 2

    # --- Yılan spiral path (tek sürekli eğri) ---
    # x = cx + amp * sin(θ), z = cos(θ) — z>=0 ön, z<0 arka
    num_turns = 3.5
    amp = int(B * 0.12)
    num_pts = 360
    baslangic_faz = 3 * math.pi / 2  # kuyruk sol yanda, kafa sağ yanda bitsin
    alt_y = int(B * 0.78)            # kuyruk
    ust_y = int(B * 0.26)            # spiral son → kolun altı, topuza yakın

    noktalar = []
    for i in range(num_pts):
        t = i / (num_pts - 1)
        y = alt_y + (ust_y - alt_y) * t
        angle = baslangic_faz + t * num_turns * 2 * math.pi
        x = cx + int(amp * math.sin(angle))
        z = math.cos(angle)
        noktalar.append((x, y, z))

    # Ardışık aynı işaretli z'leri tek segment olarak topla — geçiş
    # noktaları iki segmentin de uçları olur → dolanım kesintisiz görünür.
    segmentler = []  # [(on_mu, [(x,y), ...]), ...]
    mevcut = [(noktalar[0][0], noktalar[0][1])]
    isaret = noktalar[0][2] >= 0
    for n in noktalar[1:]:
        yeni = n[2] >= 0
        mevcut.append((n[0], n[1]))
        if yeni != isaret:
            segmentler.append((isaret, mevcut))
            mevcut = [(n[0], n[1])]
            isaret = yeni
    segmentler.append((isaret, mevcut))

    y_kalin = max(5, B // 17)
    stroke_kalin = y_kalin + SS * 2      # koyu dış kenar
    ic_kalin = max(2, SS)                # pul hissi için iç çizgi

    def cizgi(seg, outline=True):
        if len(seg) < 2:
            return
        if outline:
            d.line(seg, fill=TEAL_ENKOYU,
                   width=stroke_kalin, joint="curve")
        d.line(seg, fill=BEYAZ, width=y_kalin, joint="curve")
        d.line(seg, fill=(0, 130, 110, 140),
               width=ic_kalin, joint="curve")

    def cap(pt, r):
        x, y = pt
        d.ellipse((x - r, y - r, x + r, y + r), fill=BEYAZ)

    # --- Katman 1: Taban ---
    taban_w = int(B * 0.30)
    taban_h = max(5, B // 30)
    off = SS * 2
    d.rounded_rectangle(
        (cx - taban_w // 2 + off, direk_y2 - taban_h // 2 + off,
         cx + taban_w // 2 + off, direk_y2 + taban_h // 2 + off),
        radius=taban_h // 2, fill=GOLGE)
    d.rounded_rectangle(
        (cx - taban_w // 2, direk_y2 - taban_h // 2,
         cx + taban_w // 2, direk_y2 + taban_h // 2),
        radius=taban_h // 2, fill=ALTIN)

    # --- Katman 2: Arka yılan segmentleri (direk önüne kapanacak) ---
    for on_mu, seg in segmentler:
        if not on_mu:
            cizgi(seg)

    # --- Katman 3: Direk + topuz (arka yılanı kapar) ---
    d.rectangle((direk_x1 + off, direk_y1 + off,
                 direk_x2 + off, direk_y2 + off), fill=GOLGE)
    d.rectangle((direk_x1, direk_y1, direk_x2, direk_y2), fill=ALTIN)
    # direk üzerine hafif parlaklık şeridi
    d.rectangle((direk_x1, direk_y1,
                 direk_x1 + max(1, direk_kalin // 4), direk_y2),
                fill=(255, 240, 180, 255))
    # üst topuz
    top_r = direk_kalin
    d.ellipse((cx - top_r, direk_y1 - top_r,
               cx + top_r, direk_y1 + top_r), fill=ALTIN)

    # --- Katman 4: Terazi kolu + tabaklar (ön yılandan ÖNCE) ---
    d.rounded_rectangle(
        (kol_x1 + off, kol_y - kol_kalin // 2 + off,
         kol_x2 + off, kol_y + kol_kalin // 2 + off),
        radius=kol_kalin // 2, fill=GOLGE)
    d.rounded_rectangle(
        (kol_x1, kol_y - kol_kalin // 2,
         kol_x2, kol_y + kol_kalin // 2),
        radius=kol_kalin // 2, fill=ALTIN)

    def tabak(tx: int):
        d.line((tx, kol_y + kol_kalin // 2,
                tx - int(B * 0.06), kol_y + int(B * 0.12)),
               fill=ALTIN_KOYU, width=max(2, SS))
        d.line((tx, kol_y + kol_kalin // 2,
                tx + int(B * 0.06), kol_y + int(B * 0.12)),
               fill=ALTIN_KOYU, width=max(2, SS))
        kase_w = int(B * 0.22)
        kase_h = int(B * 0.10)
        kase_y = kol_y + int(B * 0.12)
        d.pieslice(
            (tx - kase_w // 2, kase_y - kase_h // 2,
             tx + kase_w // 2, kase_y + kase_h),
            start=0, end=180, fill=ALTIN)
        d.ellipse(
            (tx - kase_w // 2, kase_y - kase_h // 2 - kol_kalin // 3,
             tx + kase_w // 2, kase_y - kase_h // 2 + kol_kalin // 2),
            fill=ALTIN)

    tabak(kol_x1 + int(B * 0.04))
    tabak(kol_x2 - int(B * 0.04))

    # --- Katman 5: Kafa konumu + Ön yılan (son ön segmentle birleşik) ---
    # Spiralin son noktasından 45° eğimli düz tek polyline → kırılmasız.
    son = noktalar[-1]
    kafa_y = int(B * 0.08)
    dy = son[1] - kafa_y
    dx = dy                           # 45° → dx = dy
    kafa_x = son[0] + dx

    son_on_idx = max(i for i, (m, _) in enumerate(segmentler) if m)
    for i, (on_mu, seg) in enumerate(segmentler):
        if on_mu:
            if i == son_on_idx:
                cizgi(seg + [(kafa_x, kafa_y)])
            else:
                cizgi(seg)

    # Kuyruk yuvarlak uç
    cap((noktalar[0][0], noktalar[0][1]), y_kalin // 2 + SS)

    # Yılan kafası
    _yilan_kafa(d, kafa_x, kafa_y,
                int(y_kalin * 1.9), int(y_kalin * 1.25), yon="sag")

    sahne = layer.resize((boyut, boyut), Image.LANCZOS)
    return _bitir(img, sahne, radius)


def main():
    boyut = 256
    v1(boyut).save(os.path.join(ASSETS, "varyasyon_1_yilan_havan_E.png"))
    v2(boyut).save(os.path.join(ASSETS, "varyasyon_2_E_yilan.png"))
    v3(boyut).save(os.path.join(ASSETS, "varyasyon_3_terazi_yilan.png"))
    print("Üretildi:")
    print(" - assets/varyasyon_1_yilan_havan_E.png")
    print(" - assets/varyasyon_2_E_yilan.png")
    print(" - assets/varyasyon_3_terazi_yilan.png")


if __name__ == "__main__":
    main()
