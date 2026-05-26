# -*- coding: utf-8 -*-
"""Akıl testi — Kullanıcının 2026-05-25'te verdiği 13 raporsuz reçete.

Hepsi Endo/IH varsayımı altında UYGUN dönmeli (paralel-yol kalıbı).
Bazıları aile hek/diğer branş ise UYGUN_DEGIL beklenir.

Raporsuz yol mantığı: SUT 4.2.38 (4) ve (6) lafzı —
"endokrinoloji uzman hekimleri ile iç hastalıkları uzman hekimlerince **veya**
bu hekimlerce düzenlenen uzman hekim raporu ile tüm hekimlerce reçete edilebilir."
"""
from recete_kontrol.diyabet_4_2_38 import diyabet_kontrol_4_2_38, yolak_belirle
from recete_kontrol.base_kontrol import KontrolSonucu


def _ilac(ad, etkin, brans='endokrinoloji', rapor='', rapor_brans=''):
    return {
        'ilac_adi': ad,
        'etkin_madde': etkin,
        'atc_kodu': '',
        'rapor_metni': rapor,
        'recete_teshisleri': ['E11.9'],
        'doktor_uzmanligi': brans,
        'rapor_doktor_uzmanligi': rapor_brans,
        'recete_ilaclari': [],
        'heyet_doktorlari': [],
        'hasta_ilac_gecmisi': [],
        'gecmis_rapor_metinleri': [],
    }


SENARYOLAR = [
    # (etiket, ilac_adi, etken, beklenen_yolak, beklenen_sonuc)
    ('NURTEN CEBECİ - JANUMET (Met+Sita) Endo raporsuz',
     'JANUMET', 'METFORMIN VE SITAGLIPTIN', 'Y4'),
    ('GÜLBAHAR HAKAN - JARDIANCE (Empa) Endo raporsuz',
     'JARDIANCE', 'EMPAGLIFLOZIN', 'Y6'),
    ('KAMER BEHREM - DAPLIG (Dapa) Endo raporsuz',
     'DAPLIG', 'DAPAGLIFLOZIN', 'Y6'),
    ('DURGÜL BİLECAN - VIDAPTIN MET (Met+Vilda) Endo raporsuz',
     'VIDAPTIN MET', 'METFORMIN VE VILDAGLIPTIN', 'Y4'),
    ('LATİF KARTAL - VIDAPTIN MET Endo raporsuz',
     'VIDAPTIN MET', 'METFORMIN VE VILDAGLIPTIN', 'Y4'),
    ('TAHİR ÖDÜNÇ - SYNJARDY (Met+Empa) Endo raporsuz',
     'SYNJARDY', 'METFORMIN VE EMPAGLIFLOZIN', 'Y6'),
    ('ABİDİN ÇELİK - JARDIANCE Endo raporsuz',
     'JARDIANCE', 'EMPAGLIFLOZIN', 'Y6'),
    ('ABİDİN ÇELİK - VIDAPTIN MET Endo raporsuz',
     'VIDAPTIN MET', 'METFORMIN VE VILDAGLIPTIN', 'Y4'),
    ('BAYRAM KARABAYIR - GALVUS (Vilda) Endo raporsuz',
     'GALVUS', 'VILDAGLIPTIN', 'Y4'),
    ('HÜSEYİN CELEP - JARDIANCE Endo raporsuz',
     'JARDIANCE', 'EMPAGLIFLOZIN', 'Y6'),
    ('SADETTİN KAVUKLU - FORZIGA (Dapa) Endo raporsuz',
     'FORZIGA', 'DAPAGLIFLOZIN', 'Y6'),
    ('HAVVA OYAN - JANUVIA (Sita) Endo raporsuz',
     'JANUVIA', 'SITAGLIPTIN', 'Y4'),
    ('HASAN KAYIK - SYNJARDY 12.5 Endo raporsuz',
     'SYNJARDY', 'METFORMIN VE EMPAGLIFLOZIN', 'Y6'),
    ('KUDUSE GÜLER - GALVUS MET Endo raporsuz',
     'GALVUS MET', 'METFORMIN VE VILDAGLIPTIN', 'Y4'),
    ('RASİM KAYIKCI - GALVUS MET Endo raporsuz',
     'GALVUS MET', 'METFORMIN VE VILDAGLIPTIN', 'Y4'),
    ('VEDAT BATIR - GALVUS MET (2x) Endo raporsuz',
     'GALVUS MET', 'METFORMIN VE VILDAGLIPTIN', 'Y4'),
    ('VEDAT BATIR - FORZIGA Endo raporsuz',
     'FORZIGA', 'DAPAGLIFLOZIN', 'Y6'),
    ('ŞERİFE ÇAMLIBEL - FORZIGA Endo raporsuz',
     'FORZIGA', 'DAPAGLIFLOZIN', 'Y6'),
    ('BEDİA AYDIN - FORZIGA Endo raporsuz',
     'FORZIGA', 'DAPAGLIFLOZIN', 'Y6'),
]


def main():
    print('=== Raporsuz reçete + Endokrinoloji hekimi (beklenen: UYGUN) ===')
    basarili = 0
    toplam = 0

    for etiket, ad, etken, yolak in SENARYOLAR:
        toplam += 1
        ilac = _ilac(ad, etken, brans='endokrinoloji')
        rap = diyabet_kontrol_4_2_38(ilac)
        ok = (rap.sonuc == KontrolSonucu.UYGUN
              and yolak_belirle(ilac) == yolak)
        icon = 'OK' if ok else 'FAIL'
        print(f'  [{icon}] {etiket}')
        print(f'    yolak: {yolak_belirle(ilac)} (bek: {yolak})  '
              f'sonuc: {rap.sonuc.name} (bek: UYGUN)')
        if not ok:
            for s in rap.sartlar or []:
                if s.durum.name in ('YOK', 'KONTROL_EDILEMEDI'):
                    print(f'      [{s.durum.name}] grup={s.grup}  {s.ad}')
        if ok:
            basarili += 1

    print(f'\n=== Endo raporsuz: {basarili}/{toplam} ===')

    # İç Hastalıkları aynı sonuç vermeli
    print('\n=== Raporsuz reçete + İç Hastalıkları hekimi (beklenen: UYGUN) ===')
    basarili2 = 0
    toplam2 = 0
    for etiket, ad, etken, yolak in SENARYOLAR[:5]:
        toplam2 += 1
        ilac = _ilac(ad, etken, brans='Iç Hastalıkları')
        rap = diyabet_kontrol_4_2_38(ilac)
        ok = (rap.sonuc == KontrolSonucu.UYGUN)
        icon = 'OK' if ok else 'FAIL'
        print(f'  [{icon}] {etiket} (IH)  sonuc: {rap.sonuc.name}')
        if ok:
            basarili2 += 1
    print(f'\n=== IH raporsuz: {basarili2}/{toplam2} ===')

    # Negatif test: pratisyen + rapor yok → UYGUN_DEGIL
    print('\n=== Negatif: Pratisyen + rapor yok → UYGUN_DEGIL ===')
    basarili3 = 0
    toplam3 = 0
    for etiket, ad, etken, yolak in SENARYOLAR[:3]:
        toplam3 += 1
        ilac = _ilac(ad, etken, brans='Pratisyen Hekim', rapor_brans='')
        rap = diyabet_kontrol_4_2_38(ilac)
        ok = (rap.sonuc == KontrolSonucu.UYGUN_DEGIL)
        icon = 'OK' if ok else 'FAIL'
        print(f'  [{icon}] {etiket} (Pratisyen)  sonuc: {rap.sonuc.name} (bek: UYGUN_DEGIL)')
        if ok:
            basarili3 += 1
    print(f'\n=== Pratisyen + rapor yok: {basarili3}/{toplam3} ===')

    # ── Y5 (Eksenatid/BYETTA) İLK vs DEVAM alt-dispatcher ─────────────────
    # SUT 4.2.38(5)/c: ilk reçete rapor şartı yok, SADECE endokrinoloji yazar
    # (1 kutu). Devam reçete 6 ay/1 yıl endo raporu + endo/iç hast yazar.
    # Alt-dispatcher: hasta_ilac_gecmisi'nde BYETTA varsa devam, yoksa ilk.
    print('\n=== Y5 Eksenatid (BYETTA) ilk reçete vs devam alt-dispatcher ===')
    Y5_RAPOR_LAFIZ = (
        'Tip 2 diyabet hastasi. Akut pankreatit oykusu yoktur. '
        'Metformin ve sulfonilurelerin maksimum tolere edilebilir '
        'dozlarinda yeterli glisemik kontrol saglanamamistir. '
        'BMI 38 tedavi baslangicinda.'
    )

    def _y5_ilac(brans, rapor_brans='', byetta_gecmiste=False, rapor=Y5_RAPOR_LAFIZ):
        return {
            'ilac_adi': 'BYETTA 10 MCG/0.04 ML',
            'etkin_madde': 'EKSENATID',
            'atc_kodu': '',
            'rapor_metni': rapor,
            'recete_teshisleri': ['E11.9'],
            'doktor_uzmanligi': brans,
            'rapor_doktor_uzmanligi': rapor_brans,
            'recete_ilaclari': [],
            'heyet_doktorlari': [],
            'hasta_ilac_gecmisi': (
                [{'ad': 'BYETTA', 'etkin_madde': 'EKSENATID'}]
                if byetta_gecmiste else []),
            'gecmis_rapor_metinleri': [],
            'hasta_kilo': 110, 'hasta_boy': 170, 'hasta_yasi': 55,
        }

    Y5_VAKALAR = [
        # (etiket, brans, rapor_brans, byetta_gecmiste, beklenen_sonuc)
        ('İLK reçete - endo hekim - BYETTA geçmişte YOK',
         'endokrinoloji', '', False, KontrolSonucu.UYGUN),
        ('İLK reçete - iç hast hekim (yetkisiz!) - BYETTA geçmişte YOK',
         'Iç Hastalıkları', '', False, KontrolSonucu.UYGUN_DEGIL),
        ('DEVAM reçete - iç hast hekim - endo rapor branşı - BYETTA geçmişte',
         'Iç Hastalıkları', 'endokrinoloji', True, KontrolSonucu.UYGUN),
        ('DEVAM reçete - endo hekim - rapor branşı yok - BYETTA geçmişte',
         'endokrinoloji', '', True, KontrolSonucu.UYGUN),
        ('DEVAM reçete - aile hekimi - rapor aile hek - BYETTA geçmişte (yetkisiz)',
         'aile hekimligi', 'aile hekimligi', True, KontrolSonucu.UYGUN_DEGIL),
    ]
    basarili4 = 0
    toplam4 = 0
    for etiket, brans, rb, gecmis, beklenen in Y5_VAKALAR:
        toplam4 += 1
        ilac = _y5_ilac(brans, rapor_brans=rb, byetta_gecmiste=gecmis)
        rap = diyabet_kontrol_4_2_38(ilac)
        ok = (rap.sonuc == beklenen and yolak_belirle(ilac) == 'Y5')
        icon = 'OK' if ok else 'FAIL'
        print(f'  [{icon}] {etiket}')
        print(f'    sonuc: {rap.sonuc.name} (bek: {beklenen.name})')
        if not ok:
            for s in rap.sartlar or []:
                if s.durum.name in ('YOK', 'KONTROL_EDILEMEDI'):
                    print(f'      [{s.durum.name}] grup={s.grup}  {s.ad}')
        if ok:
            basarili4 += 1
    print(f'\n=== Y5 ilk/devam alt-dispatcher: {basarili4}/{toplam4} ===')

    tum_basarili = basarili + basarili2 + basarili3 + basarili4
    tum_toplam = toplam + toplam2 + toplam3 + toplam4
    print(f'\n=== TOPLAM: {tum_basarili}/{tum_toplam} ===')


if __name__ == '__main__':
    main()
