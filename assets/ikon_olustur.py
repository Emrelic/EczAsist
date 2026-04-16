"""
Eczasist programı için .ico dosyası üret.
PIL kullanır — çalıştırmak için: python assets/ikon_olustur.py
"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eczasist.ico")
PNG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eczasist.png")


def ikon_ciz(boyut: int) -> Image.Image:
    img = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Dairesel arka plan — eczane yeşili
    pad = max(1, boyut // 32)
    d.ellipse(
        (pad, pad, boyut - pad, boyut - pad),
        fill=(0, 150, 136, 255),
        outline=(255, 255, 255, 255),
        width=max(2, boyut // 32),
    )

    # Merkezde + işareti (eczane sembolü)
    kol = max(6, boyut // 5)
    kalin = max(4, boyut // 6)
    merkez = boyut // 2
    # yatay kol
    d.rounded_rectangle(
        (merkez - kol, merkez - kalin // 2,
         merkez + kol, merkez + kalin // 2),
        radius=max(1, kalin // 4),
        fill=(255, 255, 255, 255),
    )
    # dikey kol
    d.rounded_rectangle(
        (merkez - kalin // 2, merkez - kol,
         merkez + kalin // 2, merkez + kol),
        radius=max(1, kalin // 4),
        fill=(255, 255, 255, 255),
    )

    return img


def main():
    # Çoklu boyutlu ico üret
    boyutlar = [16, 24, 32, 48, 64, 128, 256]
    resimler = [ikon_ciz(b) for b in boyutlar]

    # En büyüğü referans; ICO tüm boyutları tek dosyada tutar
    resimler[0].save(
        OUT, format="ICO",
        sizes=[(b, b) for b in boyutlar],
        append_images=resimler[1:],
    )

    # PNG (dokümantasyon/link için)
    resimler[-1].save(PNG, format="PNG")

    print(f"Üretildi: {OUT}")
    print(f"Üretildi: {PNG}")


if __name__ == "__main__":
    main()
