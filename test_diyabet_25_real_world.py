# -*- coding: utf-8 -*-
"""25 gerçek dünya reçetesi — diyabet met/sulfo/max/yetersiz parser testi.

Kullanıcı 2026-05-24 günü "diğer rapor uygun" etiketi alan ama aktif raporları
da aslında klinik şartı içeren 25 reçete bildirdi. Bu raporlardaki yazım
varyantlarının atom_metformin_sulfo_max_yetersiz tarafından parse edilmesi
gerekiyor — yani atom UYGUN dönmeli (KE+sartli değil).
"""

import sys

from recete_kontrol.diyabet_4_2_38 import atom_metformin_sulfo_max_yetersiz
from recete_kontrol.sut_motor.atomlar import SartDurumu


VAKALAR = [
    # (id, hasta, rapor_metni_aktif, beklenen_durum)
    ('39LP3E1', 'SEZAİ ÖZKAN',
     'METFORMIN VE SÜLFONİLÜRELERİN MAKSİMUN TOLERE EDİLEBİLİR DOZLARINDA '
     'YETERLİ GLİSEMİK KONTROL HASTADA SAĞLANAMAMIŞTIR',
     SartDurumu.VAR),
    ('33CUC0E', 'HAMDULLAH AKSU',
     'METFORMİN VE/ VEYA SÜLFONİLÜRE MAKSİMUM TOLERE EDİLEBİLİR DOZUNA '
     'RAĞMEN KAN ŞEKER REGÜLASYONU SAĞLANAMAMIŞTIR. HASTA KENDİ KENDİNE '
     'ŞEKER ÖLÇÜMÜ YAPABİLİR',
     SartDurumu.VAR),
    ('3A0MDCJ', 'MEHMET ÇITAK',
     'maksimal tolere edilebilir dozlarda metformin ve sülfonilüre ile '
     'regüle olmayan şeker yüksekliği',
     SartDurumu.VAR),
    ('2TYB4GA', 'MELİKE DAĞ',
     'METFORMIN VE SULFONILURELERİN YETERLİ ORANDA GLİSEMİK KONTROL '
     'SAĞLANAMAMIŞTIR.',
     SartDurumu.VAR),
    ('30RRUTR', 'MEHMET KILIÇALP',
     'METFORMIN VE SULFONILURELERİN YETERLİ ORANDA GLİSEMİK KONTROL '
     'SAĞLANAMAMIŞTIR. MONOTERAPİ İLE KAN BASINCI KONTROL ALTINA '
     'ALINAMAMIŞTIR.',
     SartDurumu.VAR),
    ('3NC6FI8', 'FADİM YÜKSEL',
     'Metformin ve Sulfonilureleri, tolere edebilecek maksimum dozlarda '
     'kullanıp yeterli glisemik kontrolü sağlayamamış. Hasta ve hasta '
     'yakını kan şekeri ölçme yeteneğine sahiptir. 1adet şeker ölçüm cihazı.',
     SartDurumu.VAR),
    ('3JVSGG2', 'EMİNE UZUN',
     'SITAGLIPTIN FOSFAT MONOHIDRAT - KANDESARTAN SILEKSETIL+HIDROKLORATIAZID '
     '- SEKER OLCUM CİHAZ ve CUBUKLARI - ATORVASTATIN KALSIYUM - '
     'MONOTERAPİ İLE KAN BASINCI REGÜLASYONU SAĞLANAMAMIŞTIR. METFORMİN VE '
     'SÜ İLE KŞ REGÜLASYONU YETERLİ DÜZEYDE SAĞLANAMAMIŞTIR.',
     SartDurumu.VAR),
    ('2YK7HF2', 'FATMA BEHREM',
     'METFORMIN VE SULFONILURELERİN YETERLİ ORANDA GLİSEMİK KONTROL '
     'SAĞLANAMAMIŞTIR. MONOTERAPİ İLE KNA BASINCI KONTROL ALTINA '
     'ALINAMAMIŞTIR',
     SartDurumu.VAR),
    ('3GO3CGD', 'AYŞEGÜL TELLİ',
     'ATENOLOL,EMPAGLIFLOZIN+METFORMIN (METFORMIN VE SULFONILÜRELERIN '
     'MAKSIMUN TOLERE EDILEBILIR KULLANIM DOZUNDA YETERLI GLISEMIK '
     'KONTROL SAĞLANAMAMIŞTIR.),GLIKLAZID',
     SartDurumu.VAR),
    ('3HKETUW', 'SİNAN DEMİRHAN',
     'METFORMIN VE SULFANILURE MAKSIMUM TOLERE EDILEN DOZA RAGMEN '
     'GLISEMI REGULE DEGIL',
     SartDurumu.VAR),
    ('3MTPNTP', 'FATMA YILMAZ',
     '.metformin ve/veya sülfanilüre maksimum tolere edilebilir dozda '
     'kullanımı ile regüle olmayan kan şeker yüksekliği mevcut.',
     SartDurumu.VAR),
    ('3FCXSUL', 'AYŞE KÜÇÜK',
     'DİYABETİK PERİFERAL NÖROPATİK AĞRI METFORMİN VE SÜLFANİLÜRELERİN '
     'TOLERE EDİLEBİLİR DOZUNDA YETERLİ GLİSEMİK KONTROL SAĞLANAMAMIŞTIR',
     SartDurumu.VAR),
    ('3BSRW37', 'AYŞE KÜÇÜK',
     'DİYABETİK PERİFERAL NÖROPATİK AĞRI METFORMİN VE SÜLFANİLÜRELERİN '
     'TOLERE EDİLEBİLİR DOZUNDA YETERLİ GLİSEMİK KONTROL SAĞLANAMAMIŞTIR',
     SartDurumu.VAR),
    ('2LONLCP', 'FATMA KAHRAMAN',
     'maksimal doz metfomrin ve sülfanilüre altında yeterli glismeik '
     'kontrol sağlanamayan hasta',
     SartDurumu.VAR),
    ('2NPHE6Z', 'MAKBULE TEKİN',
     'metformin ve/veya sülfonilürelerin makismum tolere edilebilir '
     'dozunda reügle olmayan tip 2 dm',
     SartDurumu.VAR),
    ('2USHOJ3', 'BAYRAM KARABAYIR',
     'ldl 105 10.02.23 maksimal doz metfomrin ve sülfanilüre+pioglitazon '
     'altında yeterli glismik kontrol sağlanamayan hasta',
     SartDurumu.VAR),
    ('2Q0279X', 'HAVVA KARAARSLAN',
     'HASTA KENDİ KENDİNE KAN SEKERİNİ ÖLCEBİLİR. METFORMİN VE/ VEYA '
     'SÜLFONİLÜRE MAKSİMUM TOLERE EDİLEBİLİR DOZUNA RAĞMEN KAN ŞEKER '
     'REGÜLASYONU SAĞLANAMAMIŞTIR.',
     SartDurumu.VAR),
    ('3A83JP4', 'ŞEVKET OKUMUŞ',
     'HASTA TOLERA EDEBİLECEĞİ MAKSİMUM METFORMİN VE SÜLFANÜLÜRE '
     'KULLANMIŞ OLMASINA RAĞMEN YETERLİ GLİSEMİK KONTROL SAĞLANAMAMIŞTIR.',
     SartDurumu.VAR),
    ('37PBI31', 'SEVİM MERCAN',
     'MONOTERAPİ İLE KAN BASINCI YETERLİ ORANDA KONTROL ALTINA '
     'ALINAMAMIŞTIR. HASTADA MAKSİMUM DOZ METFORMİN VE SULFONİLÜRE '
     'TEDAVİSİNE RAĞMEN NORMOGLİSEMİ SAĞLANAMAMIŞTIR',
     SartDurumu.VAR),
    ('3GTF6YY', 'HALİL ÇEVİK',
     'Metforminin maksimum tolere edilen dozu ve bir sulfonilure ile ikili '
     'kombine tedaviyle yeterli duzeyde kontrol edilemeyen hasta',
     SartDurumu.VAR),
    ('32JX9E8', 'NAHİDE ÇELİK',
     'METFORMİN VE MAKSİMUM DOZ SÜLFANİLÜRE VERİLMESİNE RAĞMEN KAN '
     'ŞEKERİ REGÜLE OLMAMIŞTIR',
     SartDurumu.VAR),
    ('2SRQD0J', 'EMİN ERARSLAN',
     '3 AYDAN FAZLA SÜLFONİLÜRELE VE METFORMİN KULLANIMINA RAGMEN KAN '
     'ŞEKERİ REGULASYONU SAĞLANAMAMIŞTIR.',
     SartDurumu.VAR),
    ('2R8LQZT', 'CENNET ÇAĞLAR',
     'kendi şekerini ölçebilir monoterapi ile kan basıncı yeterli oranda '
     'kontrol altına alınamadı. Metformin ve sülfonilürelerin tolere '
     'edilebilir maksimum dozuyla kan şekeri regüle edilemedi.',
     SartDurumu.VAR),
    ('2UGGHWN', 'FADİM YÜKSEL (eski)',
     'Metformin Ve Sulfonilureleri,Tolere Edebilecek Maksimum Dozlarda '
     'Kullanip Yeterli Glisemik Kontrolu Saglayamamis',
     SartDurumu.VAR),
    ('2P3ZIME', 'PERİZADE AKGÜN',
     'AKARBOZ,DAPAGLİFLOZİN PROPANDİOL MONOHİDRAT,EMPAGLIFLOZIN,GLIKLAZID '
     '(METFORMİN VEYA SÜLFANÜRE İLE GLUKOZ REGÜLASYON SAĞLANAMADI),'
     'LINAGLIPTIN (METFORMİNE İLE SÜLFANÜRE MAKSİMUM TOLERE EDİLEBİLEN '
     'DOZLARI İLE GLUKOZ REGÜLE EDİLEMEMİŞTİR.),METFORMIN',
     SartDurumu.VAR),
]


def main():
    basarili = 0
    toplam = len(VAKALAR)
    fail_list = []
    print(f'\n=== 25 Real-World Diyabet Reçetesi Parser Testi ===\n')
    for rid, hasta, rapor, beklenen in VAKALAR:
        s = atom_metformin_sulfo_max_yetersiz({'rapor_metni': rapor})
        ok = (s.durum == beklenen)
        icon = '[OK]  ' if ok else '[FAIL]'
        print(f'{icon} {rid} {hasta:30s} -> {s.durum.name:25s} '
              f'(beklenen: {beklenen.name})')
        if not ok:
            print(f'        Neden: {s.neden}')
            fail_list.append((rid, hasta))
        else:
            basarili += 1
    print(f'\n=== TOPLAM: {basarili}/{toplam} test gecti ===')
    if fail_list:
        print('\n--- BASARISIZ ---')
        for rid, hasta in fail_list:
            print(f'  {rid} {hasta}')
    return basarili == toplam


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
