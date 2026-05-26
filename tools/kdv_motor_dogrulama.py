"""
KDV motoru — Botanik kasa kapatma karşılaştırma testi.
Kullanıcının Botanik Kasa Kapatma ekranından elle topladığı rakamları
kdv_analiz_yap() çıktısıyla karşılaştırır.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kdv_analiz_motoru import kdv_analiz_yap

# Botanik Kasa Kapatma ekranından ekran görüntülerinden elle çekilmiş rakamlar
# (TOPLAM CİRO, TOPLAM POS, Depo Giriş)
BOTANIK = {
    # 2025
    (2025, 1):  {"ciro": 1_530_364.39, "pos":   31_457.68, "depo_giris": 1_268_502.31},
    (2025, 2):  {"ciro":   981_543.64, "pos":  274_583.47, "depo_giris":   698_213.36},
    (2025, 3):  {"ciro": 1_197_819.24, "pos":   74_736.58, "depo_giris":   969_460.42},
    (2025, 4):  {"ciro": 1_165_880.50, "pos":  126_792.42, "depo_giris":   664_013.63},
    (2025, 5):  {"ciro": 1_264_312.17, "pos":  214_918.52, "depo_giris":   885_240.46},
    (2025, 6):  {"ciro": 1_080_438.86, "pos":  226_050.22, "depo_giris":   773_678.48},
    (2025, 7):  {"ciro": 1_061_526.99, "pos":  197_780.58, "depo_giris":   726_201.35},
    (2025, 8):  {"ciro": 1_183_857.30, "pos":  260_077.43, "depo_giris":   912_929.18},
    (2025, 9):  {"ciro": 1_239_774.68, "pos":  274_583.47, "depo_giris": 1_302_919.25},
    (2025, 10): {"ciro": 1_239_774.68, "pos":  274_583.47, "depo_giris": 1_302_919.25},
    (2025, 11): {"ciro": 1_479_425.73, "pos":  301_083.60, "depo_giris":   833_769.82},
    (2025, 12): {"ciro": 2_033_218.64, "pos":  444_826.03, "depo_giris": 1_463_524.10},
    # 2026
    (2026, 1):  {"ciro": 2_446_211.22, "pos":  513_727.39, "depo_giris": 1_562_215.76},
    (2026, 2):  {"ciro": 1_959_974.25, "pos":  393_036.74, "depo_giris": 1_942_428.04},
    (2026, 3):  {"ciro": 1_663_518.50, "pos":  422_598.43, "depo_giris": 1_139_961.33},
    (2026, 4):  {"ciro": 1_845_658.39, "pos":  333_478.10, "depo_giris":   924_833.87},
    (2026, 5):  {"ciro": 1_445_780.31, "pos":  366_865.56, "depo_giris":   901_183.35},
}

AY_ADI = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
          "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def fmt(v):
    return f"{v:>14,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct_diff(motor, botanik):
    if not botanik:
        return "—"
    diff = (motor - botanik) / botanik * 100
    return f"{diff:+5.1f}%"


def yazdir_satir(donem, motor_satis, motor_pos, motor_alim, motor_alim_kdv, b):
    if b is None:
        print(f"  {donem:>14} | {fmt(motor_satis)} |       —        | {fmt(motor_pos)} |       —        |"
              f" {fmt(motor_alim)} |       —        | {fmt(motor_alim_kdv)}")
        return
    print(f"  {donem:>14} | {fmt(motor_satis)} | {fmt(b['ciro'])} {pct_diff(motor_satis, b['ciro'])} |"
          f" {fmt(motor_pos)} | {fmt(b['pos'])} {pct_diff(motor_pos, b['pos'])} |"
          f" {fmt(motor_alim)} | {fmt(b['depo_giris'])} {pct_diff(motor_alim, b['depo_giris'])} |"
          f" {fmt(motor_alim_kdv)}")


def main():
    print("\n" + "=" * 220)
    print(f"  {'Dönem':>14} | {'Bizim Satış':>14} | {'Botanik CİRO':>14}        | "
          f"{'Bizim POS':>14} | {'Botanik POS':>14}        | "
          f"{'Bizim Alım':>14} | {'Botanik DG':>14}        | {'Alış KDV':>14}")
    print("=" * 220)

    bizim_satis_top = 0.0
    bizim_pos_top = 0.0
    bizim_alim_top = 0.0
    bizim_alim_kdv_top = 0.0
    bot_ciro_top = 0.0
    bot_pos_top = 0.0
    bot_dg_top = 0.0

    for yil in (2025, 2026):
        for ay in range(1, 13):
            anahtar = (yil, ay)
            if anahtar not in BOTANIK:
                continue
            sonuc = kdv_analiz_yap(yil, ay)
            if sonuc.hata:
                print(f"  HATA {yil}-{ay:02d}: {sonuc.hata}")
                continue

            # CİRO ile karşılaştırma için FaturaCikis hariç (Botanik CİRO'ya katmaz)
            motor_satis = sum(o.tutar for o in sonuc.elden.values()) \
                        + sum(o.tutar for o in sonuc.recete.values())
            motor_pos = sum(d.get("tutar", 0) for d in sonuc.pos_dagilim.values())
            motor_alim = sonuc.toplam_alim_tutar  # KDV dahil
            motor_alim_kdv = sonuc.toplam_alim_kdv

            b = BOTANIK[anahtar]
            yazdir_satir(f"{yil}-{ay:02d} {AY_ADI[ay][:4]}",
                         motor_satis, motor_pos, motor_alim, motor_alim_kdv, b)

            bizim_satis_top += motor_satis
            bizim_pos_top += motor_pos
            bizim_alim_top += motor_alim
            bizim_alim_kdv_top += motor_alim_kdv
            bot_ciro_top += b["ciro"]
            bot_pos_top += b["pos"]
            bot_dg_top += b["depo_giris"]

        print("-" * 220)

    print(f"  {'TOPLAM':>14} | {fmt(bizim_satis_top)} | {fmt(bot_ciro_top)} {pct_diff(bizim_satis_top, bot_ciro_top)} |"
          f" {fmt(bizim_pos_top)} | {fmt(bot_pos_top)} {pct_diff(bizim_pos_top, bot_pos_top)} |"
          f" {fmt(bizim_alim_top)} | {fmt(bot_dg_top)} {pct_diff(bizim_alim_top, bot_dg_top)} |"
          f" {fmt(bizim_alim_kdv_top)}")
    print("=" * 220)


if __name__ == "__main__":
    main()
