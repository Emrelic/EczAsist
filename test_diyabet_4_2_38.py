# -*- coding: utf-8 -*-
"""Akıl testleri — SUT 4.2.38 + 4.2.74 diyabet motoru.

Her yolak için en az 1 UYGUN + 1 UYGUN_DEĞİL + 1 ŞÜPHELİ senaryosu.
+ Çapraz kombi yasakları + DeMorgan + sessizlik edge case.

Karar Defteri (2026-05-24): S1=A, S2=C, S3=A, S4=A, S5=A, S6=A, S7=A, S8=A.
"""

from recete_kontrol.diyabet_4_2_38 import (
    diyabet_kontrol_4_2_38, yolak_belirle,
)
from recete_kontrol.base_kontrol import KontrolSonucu


def _ilac(ad='', etkin='', rapor='', teshis=None, brans='endokrinoloji',
           rapor_brans='endokrinoloji', diger_ilac=None, heyet=None,
           hasta_ilac_gecmisi=None, hasta_kilo=None, hasta_boy=None,
           hasta_yasi=None, hasta_tc=''):
    """Test fixture: ilac_sonuc dict üretici."""
    return {
        'ilac_adi': ad,
        'etkin_madde': etkin,
        'atc_kodu': '',
        'rapor_metni': rapor,
        'recete_teshisleri': teshis or [],
        'doktor_uzmanligi': brans,
        'rapor_doktor_uzmanligi': rapor_brans,
        'recete_ilaclari': [{'ad': x} for x in (diger_ilac or [])],
        'heyet_doktorlari': [{'brans': b} for b in (heyet or [])],
        'hasta_ilac_gecmisi': (
            [{'ad': x} for x in hasta_ilac_gecmisi]
            if hasta_ilac_gecmisi else []),
        'hasta_kilo': hasta_kilo,
        'hasta_boy': hasta_boy,
        'hasta_yasi': hasta_yasi,
        'hasta_tc': hasta_tc,
        'gecmis_rapor_metinleri': [],
    }


def _test(adi, ilac_sonuc, beklenen_yolak, beklenen_sonuc):
    """Tek test çalıştır, sonuç + yolak kontrol."""
    yolak = yolak_belirle(ilac_sonuc)
    rapor = diyabet_kontrol_4_2_38(ilac_sonuc)
    yolak_ok = (yolak == beklenen_yolak)
    sonuc_ok = (rapor.sonuc == beklenen_sonuc)
    icon = 'OK' if (yolak_ok and sonuc_ok) else 'FAIL'
    print(f'  [{icon}] {adi}')
    print(f'    yolak: {yolak} (beklenen: {beklenen_yolak})  '
          f'sonuc: {rapor.sonuc.name} (beklenen: {beklenen_sonuc.name})')
    if not (yolak_ok and sonuc_ok):
        nedenler = [s for s in rapor.sartlar
                    if s.durum.name in ('YOK', 'KONTROL_EDILEMEDI')][:3]
        for s in nedenler:
            print(f'      [{s.durum.name}] {s.ad}: {s.neden}')
    return yolak_ok and sonuc_ok


def main():
    basarili = 0
    toplam = 0

    print('\n=== Y1 - Met/Sulfo/Akarboz/Insan insulin (Fikra 1) ===')
    toplam += 1
    if _test('Y1 metformin -> UYGUN',
              _ilac(ad='GLUKOFEN', etkin='METFORMIN'),
              'Y1', KontrolSonucu.UYGUN):
        basarili += 1

    print('\n=== Y2 - Repaglinid/Nateglinid (Fikra 2) ===')
    toplam += 1
    if _test('Y2 repaglinid endo -> UYGUN',
              _ilac(ad='NOVONORM', etkin='REPAGLINID', brans='endokrinoloji'),
              'Y2', KontrolSonucu.UYGUN):
        basarili += 1
    toplam += 1
    if _test('Y2 repaglinid kardiyolog -> UYGUN',
              _ilac(ad='NOVONORM', etkin='REPAGLINID', brans='kardiyoloji'),
              'Y2', KontrolSonucu.UYGUN):
        basarili += 1

    print('\n=== Y3 - Analog insulin/Pioglitazon (Fikra 3) ===')
    toplam += 1
    if _test('Y3 pioglitazon aile hekimi -> UYGUN_DEGIL',
              _ilac(ad='ACTOS', etkin='PIOGLITAZON',
                     brans='aile hekimligi', rapor_brans=''),
              'Y3', KontrolSonucu.UYGUN_DEGIL):
        basarili += 1
    toplam += 1
    if _test('Y3 pioglitazon endo -> UYGUN',
              _ilac(ad='ACTOS', etkin='PIOGLITAZON', brans='endokrinoloji'),
              'Y3', KontrolSonucu.UYGUN):
        basarili += 1

    print('\n=== Y4 - DPP-4 (Fikra 4) ===')
    toplam += 1
    if _test('Y4 sitagliptin endo + met max yet. -> UYGUN',
              _ilac(ad='JANUVIA', etkin='SITAGLIPTIN', brans='endokrinoloji',
                     rapor=('Metformin maksimum tolere doz yetersiz '
                            'glisemik kontrol')),
              'Y4', KontrolSonucu.UYGUN):
        basarili += 1
    toplam += 1
    if _test('Y4 sitagliptin + GLP-1 (Ozempic) -> UYGUN_DEGIL (KY4.1)',
              _ilac(ad='JANUVIA', etkin='SITAGLIPTIN', brans='endokrinoloji',
                     rapor='Metformin max doz yetersiz glisemik',
                     diger_ilac=['OZEMPIC']),
              'Y4', KontrolSonucu.UYGUN_DEGIL):
        basarili += 1

    print('\n=== Y5 - Eksenatid (Fikra 5) ===')
    toplam += 1
    if _test('Y5 eksenatid full-fit -> UYGUN',
              _ilac(ad='BYETTA', etkin='EKSENATID',
                     teshis=['E11.9'], brans='endokrinoloji',
                     hasta_kilo=110, hasta_boy=170,
                     rapor=('Tip 2 diyabet. Akut pankreatit oykusu yok. '
                            'Metformin maksimum tolere doz yetersiz glisemik '
                            'kontrol saglanamamistir. Tedavi baslangicinda '
                            'BMI 38')),
              'Y5', KontrolSonucu.UYGUN):
        basarili += 1
    toplam += 1
    if _test('Y5 eksenatid + DPP-4 birlikte -> UYGUN_DEGIL (KY5.1)',
              _ilac(ad='BYETTA', etkin='EKSENATID',
                     teshis=['E11.9'], brans='endokrinoloji',
                     hasta_kilo=110, hasta_boy=170,
                     rapor=('Tip 2 DM. Pankreatit yok. Metformin max yet. '
                            'BMI 38'),
                     diger_ilac=['JANUVIA']),
              'Y5', KontrolSonucu.UYGUN_DEGIL):
        basarili += 1
    toplam += 1
    if _test('Y5 eksenatid - BMI verisi yok -> SARTLI/SUPHELI',
              _ilac(ad='BYETTA', etkin='EKSENATID',
                     teshis=['E11.9'], brans='endokrinoloji',
                     rapor='Tip 2 DM. Pankreatit yok. Met max yet.'),
              'Y5', KontrolSonucu.SARTLI_UYGUN):
        basarili += 1

    print('\n=== Y6 - SGLT-2 DM (Fikra 6) ===')
    toplam += 1
    if _test('Y6 dapa endo + met max yet. -> UYGUN',
              _ilac(ad='FORZIGA', etkin='DAPAGLIFLOZIN',
                     teshis=['E11.9'], brans='endokrinoloji',
                     rapor='Metformin maksimum tolere doz yetersiz glisemik kontrol'),
              'Y6', KontrolSonucu.UYGUN):
        basarili += 1
    # 2026-05-24 demote kuralı: rapor metni klinik şart ibaresini içermiyor
    # ve hastanın geçmiş raporlarında da yok (cache boş, EOS test ortamında
    # erişilemez → None) → atom KE'den YOK'a düşer → sonuç UYGUN_DEGIL.
    # RUKEN AVCI/CELAL HAKAN/FİDAN DOĞAN tipi pilot vakalar buraya düşer.
    toplam += 1
    if _test('Y6 dapa endo, rapor klinik ibare yok, gecmis bos -> UYGUN_DEGIL',
              _ilac(ad='FORZIGA', etkin='DAPAGLIFLOZIN',
                     teshis=['E11.9'], brans='endokrinoloji',
                     rapor='Tip 2 diabetes mellitus. HbA1c %8.5. Tedaviye devam.',
                     hasta_tc='99999999998'),  # bypass cache'te yok
              'Y6', KontrolSonucu.UYGUN_DEGIL):
        basarili += 1

    print('\n=== Y7 - Soliqua (Fikra 7) ===')
    toplam += 1
    if _test('Y7 Soliqua full-fit -> UYGUN (sure 1yil bilgi-grup, hesap disi)',
              _ilac(ad='SOLIQUA', etkin='INSULIN GLARJIN/LIKSISENATID',
                     teshis=['E11.9'], brans='endokrinoloji',
                     hasta_kilo=105, hasta_boy=165, hasta_yasi=55,
                     heyet=['endokrinoloji'],
                     hasta_ilac_gecmisi=['METFORMIN'],
                     rapor=('Tip 2 DM yetiskin. Akut pankreatit yok. '
                            'Yetersiz glisemik kontrol. Metformin + diyet/'
                            'egzersiz. BMI 39 tedavi baslangicinda')),
              'Y7', KontrolSonucu.UYGUN):
        basarili += 1
    toplam += 1
    if _test('Y7 Soliqua + DPP-4 -> UYGUN_DEGIL (KY7.1)',
              _ilac(ad='SOLIQUA', etkin='INSULIN GLARJIN/LIKSISENATID',
                     teshis=['E11.9'], brans='endokrinoloji',
                     hasta_kilo=105, hasta_boy=165, hasta_yasi=55,
                     heyet=['endokrinoloji'],
                     hasta_ilac_gecmisi=['METFORMIN'],
                     rapor=('Tip 2 DM yetiskin. Pankreatit yok. Yetersiz '
                            'glisemik. Metformin diyet egzersiz. BMI 39'),
                     diger_ilac=['TRAJENTA']),
              'Y7', KontrolSonucu.UYGUN_DEGIL):
        basarili += 1

    print('\n=== Y8 - Glyxambi (Fikra 8) ===')
    toplam += 1
    if _test('Y8 Glyxambi full-fit -> UYGUN',
              _ilac(ad='GLYXAMBI', etkin='EMPAGLIFLOZIN/LINAGLIPTIN',
                     brans='endokrinoloji',
                     hasta_ilac_gecmisi=['METFORMIN', 'JARDIANCE'],
                     rapor='Met+empa altyapisina ragmen yetersiz glisemik kontrol'),
              'Y8', KontrolSonucu.UYGUN):
        basarili += 1
    toplam += 1
    if _test('Y8 Glyxambi - hasta gecmisi yok -> SARTLI/SUPHELI (S4=A)',
              _ilac(ad='GLYXAMBI', etkin='EMPAGLIFLOZIN/LINAGLIPTIN',
                     brans='endokrinoloji',
                     rapor='Yetersiz glisemik kontrol'),
              'Y8', KontrolSonucu.SARTLI_UYGUN):
        basarili += 1
    toplam += 1
    if _test('Y8 Glyxambi + GLP-1 -> UYGUN_DEGIL (KY8.3)',
              _ilac(ad='GLYXAMBI', etkin='EMPAGLIFLOZIN/LINAGLIPTIN',
                     brans='endokrinoloji',
                     hasta_ilac_gecmisi=['METFORMIN', 'JARDIANCE'],
                     rapor='Yetersiz glisemik kontrol',
                     diger_ilac=['OZEMPIC']),
              'Y8', KontrolSonucu.UYGUN_DEGIL):
        basarili += 1

    print('\n=== Y9 - Kapsam disi GLP-1 ===')
    toplam += 1
    if _test('Y9 Ozempic -> UYGUN_DEGIL (kapsam disi)',
              _ilac(ad='OZEMPIC', etkin='SEMAGLUTID'),
              'Y9_KAPSAM_DISI', KontrolSonucu.UYGUN_DEGIL):
        basarili += 1

    print('\n=== Y_KY - SGLT-2 / Kalp Yetmezligi (SUT 4.2.74-1) ===')
    toplam += 1
    if _test('Y_KY dapa KY full-fit -> UYGUN',
              _ilac(ad='FORZIGA', etkin='DAPAGLIFLOZIN',
                     teshis=['I50.0'], brans='kardiyoloji',
                     heyet=['kardiyoloji'],
                     hasta_ilac_gecmisi=['COVERSYL', 'CONCOR', 'ALDACTONE'],
                     rapor=('Kronik kalp yetersizligi. EF %35. NYHA sinif III. '
                            'eGFR 50')),
              'Y_KY', KontrolSonucu.UYGUN):
        basarili += 1
    toplam += 1
    if _test('Y_KY dapa kardiyolog YOK -> UYGUN_DEGIL',
              _ilac(ad='FORZIGA', etkin='DAPAGLIFLOZIN',
                     teshis=['I50.0'], brans='ic hastaliklari',
                     heyet=['ic hastaliklari'],
                     hasta_ilac_gecmisi=['COVERSYL', 'CONCOR', 'ALDACTONE'],
                     rapor='Kalp yetersizligi EF %35 NYHA III eGFR 50'),
              'Y_KY', KontrolSonucu.UYGUN_DEGIL):
        basarili += 1
    toplam += 1
    if _test('Y_KY dapa EF parse edilemez -> SARTLI/SUPHELI',
              _ilac(ad='FORZIGA', etkin='DAPAGLIFLOZIN',
                     teshis=['I50.0'], brans='kardiyoloji',
                     heyet=['kardiyoloji'],
                     hasta_ilac_gecmisi=['COVERSYL', 'CONCOR', 'ALDACTONE'],
                     rapor='Kalp yetersizligi NYHA III eGFR 50'),
              'Y_KY', KontrolSonucu.SARTLI_UYGUN):
        basarili += 1
    # FİKRET DALGIÇ (TC: 43240373848, 28.04.2026) — bozuk yazımlı rapor pilot vakası:
    # "EF<%40", "(NYHA ) sınıf II-IV)", "eGFR değeri >25", "ACE inhibitörü /arb +beta bloker +mra tedavisi"
    # Bu format parse fix sonrası (EF <-operatör, NYHA pencere, eGFR lazy window, rapor lafzı KY1c) çözülür.
    toplam += 1
    if _test('Y_KY FİKRET DALGIÇ bozuk yazım -> SARTLI (heyet teyit)',
              _ilac(ad='FORZIGA 10MG 28 FILM TABLET',
                     etkin='DAPAGLIFLOZIN 10 MG O',
                     teshis=[], brans='kardiyoloji',
                     heyet=['kardiyoloji'],
                     rapor=('Hastada düşük enfeksiyon fraksiyonlu (EF<%40 )'
                            'SAMPTOMATİK (NYHA ) sınıf II-IV) kronik kalp '
                            'yetmezliği mevcuttur. hasta halşen standart tedavi '
                            'olan ACE inhibitörü /arb +beta bloker +mra tedavisi '
                            'almaktadır. Hstanın eGFR değeri >25 m/dk /1.73 m2 '
                            'dir.')),
              'Y_KY', KontrolSonucu.UYGUN):
        basarili += 1

    print('\n=== Y_KBH - SGLT-2 / Kronik Bobrek Hastaligi (SUT 4.2.74-2) ===')
    toplam += 1
    if _test('Y_KBH dapa KBH full-fit -> UYGUN',
              _ilac(ad='FORZIGA', etkin='DAPAGLIFLOZIN',
                     teshis=['N18.3'], brans='nefroloji',
                     heyet=['nefroloji'],
                     diger_ilac=['COVERSYL'],
                     rapor=('Kronik bobrek hastaligi. Persistan proteinuri '
                            '3 ay. ACR 250 mg/g. eGFR 40. RAAS-I kullanim')),
              'Y_KBH', KontrolSonucu.UYGUN):
        basarili += 1
    toplam += 1
    if _test('Y_KBH dapa nefrolog YOK -> UYGUN_DEGIL',
              _ilac(ad='FORZIGA', etkin='DAPAGLIFLOZIN',
                     teshis=['N18.3'], brans='ic hastaliklari',
                     heyet=['ic hastaliklari'],
                     diger_ilac=['COVERSYL'],
                     rapor=('Kronik bobrek hastaligi persistan proteinuri 3 ay '
                            'ACR 250 eGFR 40')),
              'Y_KBH', KontrolSonucu.UYGUN_DEGIL):
        basarili += 1

    # ══════════════════════════════════════════════════════════════════════
    # REAL-WORLD vakalar — rapor lafzı parser robustness (32 reçete pilot)
    # 2026-05-24 — kullanıcı paylaşımı (Y4/Y6 SGLT-2 + DPP-4 + Y3b nokturnal)
    # ══════════════════════════════════════════════════════════════════════
    print('\n=== Y6 / Y4 — Real-world rapor lafzı parser robustness ===')

    # Helper: rapor lafzı testleri (parser-only, Y6.1/Y4.1 atomu VAR mı?)
    from recete_kontrol.diyabet_4_2_38 import atom_metformin_sulfo_max_yetersiz
    from recete_kontrol.base_kontrol import SartDurumu

    parser_vakalari = [
        # 12 SGLT-2 vakası (Y6)
        ('SGLT2 ELIF "SULFANURE TOLERE EDILEBILEN MAKSIMUM DOZ ... KONTROLU SAGLANAMAMISTIR"',
         'METFORMIN VE SULFANURE TOLERE EDILEBILEN MAKSIMUM DOZ TEDAVISI ILE GLUKOZ KONTROLU SAGLANAMAMISTIR.'),
        ('SGLT2 ADEM "MAX. KULLANIM DOZUNDA" (max arasi kelime)',
         'METFORMIN VE SULFONILURELERIN MAX. KULLANIM DOZUNDA YETERLI GLISEMIK KONTROL SAGLANAMAMISTIR.'),
        ('SGLT2 NIYAZI tire-kirmasi "sulfoni-lurelerin maximum doz-larda kont-rol"',
         'Metformin veya sulfoni-lurelerin maximum doz-larda yeterli glisemik kont-rol saglanmamistir'),
        ('SGLT2 HAFIZE "maximum oranda" + "kontrolu saglanama"',
         'metformin veya sulfonilurelerin maximum oranda tolere edilebilir dozlarinda yeterli glisemik kontrolu saglanamamistir'),
        ('SGLT2 MUZAFFER "kan sekeri yeterince dusurulemedi" (tibben esdeger)',
         'maksimum doz sulfonilure ve/veya metformin tedavisine ragmen kan sekeri yeterince dusurulemedi.'),
        # 5 JANUMET vakası (Y4 DPP-4 + Met kombi)
        ('Y4 MEHMET_SIDDIK "kan sekeri regulasyonu saglanama"',
         'metformin ve sulfonilurelerin maksimum tolere edilebilir dozuna ragmen kan sekeri regulasyonu saglanamamistir'),
        # 9 GALVUS vakası (Y4)
        ('Y4 RUKEN "tolere EDEBILIR" (edilebilir typo)',
         'metformin ve/veya sulfonilulerin maksimum tolere edebilir dozlarinda yeterli glisemik kontrol saglanmamistir.'),
        ('Y4 KUDUSE2 "GLISEMIK KONTROL ELDE EDILMEMIS"',
         'METFORMIN VE DIGER SULFONILURELERIN MAXIMUM TOLERE EDILEBILIR DOZLARINA RAGMEN GLISEMIK KONTROL ELDE EDILMEMISTIR'),
        ('Y4 AZIZ typo "MAXSIMIMUM TOLERA EDILEBILECEK"',
         'METFORMIN VEYA SULFONILURENININ MAXSIMIMUM TOLERA EDILEBILECEK DOZUNU KULLANMASINA RAGMEN YETERLI GLISEMIK KONTROL SAGLANAMAMISTIR'),
        ('Y4 PERIZADE "MAKSIMUM DOZLARINDA" (tolere edilebilir lafzi yok)',
         'KARAR:METFORMIN VE/VEYA SULFONILURELERIN MAKSIMUM DOZLARINDA YETERLI GLISEMIK KONTROL SAGLANAMAMISTIR.'),
        # Negatif kontrol — UNZULE rapora yok metformin lafzı yok, KE bekleniyor
        ('NEGATIF UNZULE (metformin lafzi YOK → KE beklenir)',
         'HASTANIN MONOTERAPI ILE KAN BASINCI YETERLI ORANDA KONTROL ALTINA ALINAMAMISTIR.'),
    ]
    for ad, rapor_metni in parser_vakalari:
        toplam += 1
        s = atom_metformin_sulfo_max_yetersiz({'rapor_metni': rapor_metni})
        is_negatif = ad.startswith('NEGATIF')
        beklenen = SartDurumu.KONTROL_EDILEMEDI if is_negatif else SartDurumu.VAR
        ok = (s.durum == beklenen)
        icon = 'OK' if ok else 'FAIL'
        print(f'  [{icon}] {ad}')
        if not ok:
            print(f'    durum: {s.durum.name} (beklenen: {beklenen.name})')
            print(f'    neden: {s.neden}')
        if ok:
            basarili += 1

    # Y3b nokturnal/gece hipoglisemi parser
    from recete_kontrol.diyabet_4_2_38 import atom_labil_hipo_regulasyon
    print('\n=== Y3b — Nokturnal/gece hipoglisemi parser ===')
    hipo_vakalari = [
        ('"NOKTURNAL HIPOGLISEMI RISKI MEVCUTTUR" (MEHMET SAHIL)',
         'DIGER BASAL INSULINLERDE NOKTURNAL HIPOGLISEMI RISKI MEVCUTTUR.',
         True),
        ('"gece hipoglisemi" (Turkce esdeger)',
         'Hasta gece hipoglisemi gecirmektedir.', True),
        ('"hipoglisemi geceleri" (suffix sirasi)',
         'Hipoglisemi geceleri yaygin gozlemleniyor.', True),
        ('NEGATIF: hipoglisemi/gece lafzi yok',
         'Hasta diyabet hastasi. Glisemik kontrol yetersiz.', False),
    ]
    for ad, metin, beklenen_var in hipo_vakalari:
        toplam += 1
        sartlar = atom_labil_hipo_regulasyon({'rapor_metni': metin}, grup='Test')
        hipo = next((s for s in sartlar if 'Hipoglisemi riski' in s.ad), None)
        ok = hipo is not None and (
            (hipo.durum == SartDurumu.VAR) == beklenen_var)
        icon = 'OK' if ok else 'FAIL'
        print(f'  [{icon}] {ad}')
        if not ok and hipo:
            print(f'    durum: {hipo.durum.name} (beklenen VAR={beklenen_var})')
        if ok:
            basarili += 1

    print(f'\n=== TOPLAM: {basarili}/{toplam} test gecti ===')
    return basarili == toplam


if __name__ == '__main__':
    import sys
    sys.exit(0 if main() else 1)
