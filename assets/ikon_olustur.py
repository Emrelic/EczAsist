"""
Eczasist programı için .ico dosyası üret.
PIL kullanır — çalıştırmak için: python assets/ikon_olustur.py

Tasarım: Terazi direğine spiral dolanmış yılan (Asklepios temalı).
- Yuvarlak kenarlı kare arka plan, diagonal teal gradient
- Altın terazi (direk + kol + tabaklar + taban)
- Yılan 3.5 tur spiral ile direğe sarılır
- Kafa sağ taraftan çapraz yukarı, terazinin üst noktasının yanından çıkar
- Hafif glossy parlaklık
"""

import os
import math
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eczasist.ico")
PNG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eczasist.png")

TEAL_ACIK = (38, 198, 176)
TEAL_KOYU = (0, 105, 92)
TEAL_ENKOYU = (0, 77, 64, 255)
BEYAZ = (255, 255, 255, 255)
BEYAZ_KREM = (250, 248, 240, 255)
ALTIN = (255, 200, 80, 255)
ALTIN_KOYU = (210, 150, 40, 255)
GOLGE = (0, 0, 0, 90)
KIRMIZI = (220, 60, 60, 255)


def _lerp(a, b, t):
    return int(a + (b - a) * t)


def _mix(c1, c2, t):
    return (_lerp(c1[0], c2[0], t), _lerp(c1[1], c2[1], t),
            _lerp(c1[2], c2[2], t), 255)


def _rounded_mask(boyut, radius):
    m = Image.new("L", (boyut, boyut), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        (0, 0, boyut - 1, boyut - 1), radius=radius, fill=255)
    return m


def _gradient_bg(boyut):
    img = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    px = img.load()
    for y in range(boyut):
        for x in range(boyut):
            t = (x + y) / (2 * (boyut - 1))
            px[x, y] = _mix(TEAL_ACIK, TEAL_KOYU, max(0.0, min(1.0, t)))
    return img


def _glossy(boyut, radius):
    layer = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(
        (int(boyut * 0.05), int(-boyut * 0.35),
         int(boyut * 0.95), int(boyut * 0.55)),
        fill=(255, 255, 255, 55))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=max(1, boyut // 40)))
    mask = _rounded_mask(boyut, radius)
    out = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    out.paste(layer, (0, 0), mask)
    return out


def _yilan_kafa(d, kx, ky, w, h, yon="sag"):
    d.ellipse((kx - w // 2, ky - h // 2, kx + w // 2, ky + h // 2),
              fill=BEYAZ)
    d.ellipse((kx - w // 2 + w // 10, ky - h // 2 - h // 12,
               kx + w // 2 - w // 4, ky + h // 2 - h // 4),
              fill=BEYAZ_KREM)
    goz_r = max(2, w // 10)
    gx = kx + (w // 6 if yon == "sag" else -w // 6)
    gy = ky - h // 6
    d.ellipse((gx - goz_r, gy - goz_r, gx + goz_r, gy + goz_r),
              fill=TEAL_ENKOYU)
    d.ellipse((gx - goz_r // 3, gy - goz_r + goz_r // 3,
               gx + goz_r // 3, gy - goz_r + goz_r),
              fill=BEYAZ)
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


def ikon_ciz(boyut):
    radius = max(4, int(boyut * 0.22))
    SS = 4
    B = boyut * SS

    bg = _gradient_bg(boyut)
    mask = _rounded_mask(boyut, radius)
    img = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    img.paste(bg, (0, 0), mask)
    dm = ImageDraw.Draw(img)
    cer = max(1, boyut // 64)
    dm.rounded_rectangle(
        (cer, cer, boyut - cer - 1, boyut - cer - 1),
        radius=radius - cer,
        outline=(255, 255, 255, 160),
        width=max(1, boyut // 90))

    layer = Image.new("RGBA", (B, B), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = B // 2

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

    num_turns = 3.5
    amp = int(B * 0.12)
    num_pts = 360
    baslangic_faz = 3 * math.pi / 2
    alt_y = int(B * 0.78)
    ust_y = int(B * 0.26)   # spiral son noktası kolun altında, topuza yakın

    noktalar = []
    for i in range(num_pts):
        t = i / (num_pts - 1)
        y = alt_y + (ust_y - alt_y) * t
        angle = baslangic_faz + t * num_turns * 2 * math.pi
        x = cx + int(amp * math.sin(angle))
        z = math.cos(angle)
        noktalar.append((x, y, z))

    segmentler = []
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
    stroke_kalin = y_kalin + SS * 2
    ic_kalin = max(2, SS)
    off = SS * 2

    def cizgi(seg):
        if len(seg) < 2:
            return
        d.line(seg, fill=TEAL_ENKOYU, width=stroke_kalin, joint="curve")
        d.line(seg, fill=BEYAZ, width=y_kalin, joint="curve")
        d.line(seg, fill=(0, 130, 110, 140), width=ic_kalin, joint="curve")

    # Taban
    taban_w = int(B * 0.30)
    taban_h = max(5, B // 30)
    d.rounded_rectangle(
        (cx - taban_w // 2 + off, direk_y2 - taban_h // 2 + off,
         cx + taban_w // 2 + off, direk_y2 + taban_h // 2 + off),
        radius=taban_h // 2, fill=GOLGE)
    d.rounded_rectangle(
        (cx - taban_w // 2, direk_y2 - taban_h // 2,
         cx + taban_w // 2, direk_y2 + taban_h // 2),
        radius=taban_h // 2, fill=ALTIN)

    # Arka yılan segmentleri
    for on_mu, seg in segmentler:
        if not on_mu:
            cizgi(seg)

    # Direk + topuz
    d.rectangle((direk_x1 + off, direk_y1 + off,
                 direk_x2 + off, direk_y2 + off), fill=GOLGE)
    d.rectangle((direk_x1, direk_y1, direk_x2, direk_y2), fill=ALTIN)
    d.rectangle((direk_x1, direk_y1,
                 direk_x1 + max(1, direk_kalin // 4), direk_y2),
                fill=(255, 240, 180, 255))
    top_r = direk_kalin
    d.ellipse((cx - top_r, direk_y1 - top_r,
               cx + top_r, direk_y1 + top_r), fill=ALTIN)

    # Terazi kolu (ön yılandan ÖNCE → yılan kolun üstüne biner, sarıyor gibi)
    d.rounded_rectangle(
        (kol_x1 + off, kol_y - kol_kalin // 2 + off,
         kol_x2 + off, kol_y + kol_kalin // 2 + off),
        radius=kol_kalin // 2, fill=GOLGE)
    d.rounded_rectangle(
        (kol_x1, kol_y - kol_kalin // 2,
         kol_x2, kol_y + kol_kalin // 2),
        radius=kol_kalin // 2, fill=ALTIN)

    def tabak(tx):
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

    # Kafa konumu — 45° düz çizgi, spiralin son noktasından devam.
    # Kafa topuz (denge noktası) hizasından ~boyun+kafa boyu kadar yukarıda.
    son = noktalar[-1]
    kafa_y = int(B * 0.08)
    dy = son[1] - kafa_y
    dx = dy                       # 45° → dx = dy
    kafa_x = son[0] + dx

    # Ön yılan segmentleri — son ön segmentini kafa noktası ile BİRLEŞİK çiz
    # (tek polyline → joint="curve" ile kırılmasız devam).
    son_on_idx = max(i for i, (m, _) in enumerate(segmentler) if m)
    for i, (on_mu, seg) in enumerate(segmentler):
        if on_mu:
            if i == son_on_idx:
                cizgi(seg + [(kafa_x, kafa_y)])
            else:
                cizgi(seg)

    # Kuyruk yuvarlak uç
    k0 = (noktalar[0][0], noktalar[0][1])
    r = y_kalin // 2 + SS
    d.ellipse((k0[0] - r, k0[1] - r, k0[0] + r, k0[1] + r), fill=BEYAZ)

    # Yılan kafası (boyn çizgisinin ucunda)
    _yilan_kafa(d, kafa_x, kafa_y,
                int(y_kalin * 1.9), int(y_kalin * 1.25), yon="sag")

    sahne = layer.resize((boyut, boyut), Image.LANCZOS)
    img = Image.alpha_composite(img, sahne)
    img = Image.alpha_composite(img, _glossy(boyut, radius))
    return img


def main():
    boyutlar = [16, 24, 32, 48, 64, 128, 256]
    resimler = [ikon_ciz(b) for b in boyutlar]
    resimler[0].save(
        OUT, format="ICO",
        sizes=[(b, b) for b in boyutlar],
        append_images=resimler[1:])
    resimler[-1].save(PNG, format="PNG")
    print(f"Üretildi: {OUT}")
    print(f"Üretildi: {PNG}")


if __name__ == "__main__":
    main()
