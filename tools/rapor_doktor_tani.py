# -*- coding: utf-8 -*-
"""Rapor doktor branş boş kalma nedenini teyit eden tanı betiği.

3 reçete üzerinde SELECT-only kontrol (BotanikDB güvenlik filtresi içinden):
  - HASAN KILIÇ      | 2X11WU7   | 21.06.2023 | Protokol 14191542
  - BAKİ SOYIRGAZ    | 2YFJSPP   | 28.08.2023 | Protokol A-458992-2-001-A-28082023102717
  - BAKİ SOYIRGAZ    | 31I1RFN   | 27.12.2023 | Protokol OP39840903

Senaryolar:
  A) RaporAnaId NULL — rapor reçeteye eşleşmemiş
  B) RaporAna var ama RaporDoktor tablosunda satır yok — heyet eksik
  C) RaporDoktor var ama BransId Brans tablosunda yok
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Windows konsolu cp1254 — Unicode kutu çizimi/işaretleri için UTF-8'e zorla
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
from botanik_db import BotanikDB


VAKALAR = [
    ('HASAN KILIÇ',   '53584607806', '2X11WU7'),
    ('BAKİ SOYIRGAZ', '11399539088', '2YFJSPP'),
    ('BAKİ SOYIRGAZ', '11399539088', '31I1RFN'),
]


def _sec_recete(db: BotanikDB, sis_recno: str):
    """Sistem reçete numarasıyla ReceteAna + Recete kalemleri + rapor bul."""
    sql = """
        SELECT TOP 5
            ra.RxId,
            ra.RxSgkIslemNo,
            ra.RxEReceteNo,
            ra.RxKayitTarihi,
            ra.RxMusteriId,
            ra.RxDoktorId,
            ra.RxBransId
        FROM ReceteAna ra
        WHERE ra.RxSgkIslemNo = ?
    """
    return db.sorgu_calistir(sql, (sis_recno,))


def _rapor_eslesme(db: BotanikDB, rx_id, musteri_id):
    """RxId → SecilenRapor kayıtları + RaporAna eşleşmesi."""
    sql = """
        SELECT
            sr.SRId,
            sr.SRRxId,
            sr.SRUrunId,
            sr.SRRaporNo,
            sr.SRRaporKodu,
            rap.RaporAnaId,
            rap.RaporAnaRaporNo,
            rap.RaporAnaRaporTakipNo,
            rap.RaporAnaProtokolNo,
            rap.RaporAnaRaporTarihi
        FROM SecilenRapor sr
        OUTER APPLY (
            SELECT TOP 1 r.*
            FROM RaporAna r
            WHERE r.RaporAnaMusteriId = ?
              AND (r.RaporAnaSilme IS NULL OR r.RaporAnaSilme = 0)
              AND (CAST(r.RaporAnaRaporNo    AS NVARCHAR(50)) = sr.SRRaporNo
                OR CAST(r.RaporAnaRaporTakipNo AS NVARCHAR(50)) = sr.SRRaporNo
                OR CAST(r.RaporAnaProtokolNo   AS NVARCHAR(50)) = sr.SRRaporNo)
        ) rap
        WHERE sr.SRRxId = ?
    """
    return db.sorgu_calistir(sql, (musteri_id, rx_id))


def _rapor_doktor_kayit(db: BotanikDB, rapor_ana_id):
    """Verilen RaporAnaId için RaporDoktor heyetini listele.

    Asıl SQL'den (aylik_recete_sorgu_gui.py:13352) öğrenilen kolonlar:
      RaporDoktorRaporAnaId, RaporDoktorDoktorId, RaporDoktorBransId,
      RaporDoktorSilme — PK ismi farklı (gereksiz, çekmiyoruz).
    """
    sql = """
        SELECT
            rd.RaporDoktorRaporAnaId AS rapor_ana_id,
            rd.RaporDoktorDoktorId   AS doktor_id,
            rd.RaporDoktorBransId    AS brans_id,
            rd.RaporDoktorSilme      AS silme,
            d.DoktorAdiSoyadi        AS doktor_ad,
            b.BransAdi               AS brans_ad
        FROM RaporDoktor rd
        LEFT JOIN Doktor d ON d.DoktorId = rd.RaporDoktorDoktorId
        LEFT JOIN Brans  b ON b.BransId  = rd.RaporDoktorBransId
        WHERE rd.RaporDoktorRaporAnaId = ?
    """
    return db.sorgu_calistir(sql, (rapor_ana_id,))


def _vaka_yazdir(db: BotanikDB, ad: str, tc: str, sis: str):
    print(f'\n══════════════════════════════════════════════════════')
    print(f' {ad} | TC {tc} | Sis.Reç {sis}')
    print(f'══════════════════════════════════════════════════════')

    recs = _sec_recete(db, sis)
    if not recs:
        print('  REÇETE BULUNAMADI — RxSgkIslemNo eşleşmedi (Botanik EOS\'a sync yok)')
        return
    rx = recs[0]
    print(f'  ReceteAna OK | RxId={rx["RxId"]} | E-Reçete={rx.get("RxEReceteNo")}')
    print(f'              | Tarih={rx.get("RxKayitTarihi")} | DoktorId={rx.get("RxDoktorId")} '
          f'BransId={rx.get("RxBransId")}')

    rap_rows = _rapor_eslesme(db, rx['RxId'], rx.get('RxMusteriId'))
    if not rap_rows:
        print('  X  SecilenRapor kaydı bulunamadı — eczacı rapor seçimi yok.')
        print('  ◀ SENARYO A — rapor zinciri başlatılamadı.')
        return

    rapor_ana_idler = set()
    print('  --- SecilenRapor → RaporAna eşleşmeleri ---')
    for ri in rap_rows[:10]:
        print(f'    SR.RaporNo={ri.get("SRRaporNo") or "—":<40} | '
              f'SR.RaporKodu={ri.get("SRRaporKodu") or "—":<10} | '
              f'RaporAnaId={ri.get("RaporAnaId") or "—"}')
        if ri.get('RaporAnaId'):
            rapor_ana_idler.add(ri['RaporAnaId'])

    if not rapor_ana_idler:
        # A senaryosu
        print('  ◀ SENARYO A — RaporAnaId NULL: reçeteye rapor EŞLEŞMEDİ.')
        print('     (SR var olabilir ama RaporAna kaydı yok; eski/silinmiş rapor)')
        return

    for raid in sorted(rapor_ana_idler):
        print(f'\n  --- RaporAnaId {raid} için heyet ---')
        rd_rows = _rapor_doktor_kayit(db, raid)
        if not rd_rows:
            # B senaryosu
            print(f'  ◀ SENARYO B — RaporDoktor tablosunda KAYIT YOK (heyet sync edilmemiş).')
            print(f'     RaporAna var ama doktor satırları boş. 2023 raporlarında '
                   'sık görülen Medula sync eksiği.')
        else:
            silinmemis = [r for r in rd_rows
                          if not r.get('silme') or r.get('silme') == 0]
            print(f'  ✓ RaporDoktor satır sayısı: {len(rd_rows)} '
                  f'(silinmemiş: {len(silinmemis)})')
            for rd in rd_rows:
                marker = ' [SILINMIS]' if rd.get('silme') else ''
                print(f'    DoktorId={rd.get("doktor_id") or "?":<10} '
                      f'({rd.get("doktor_ad") or "?"}) '
                      f'BransId={rd.get("brans_id") or "?"}{marker} '
                      f'-> Brans={rd.get("brans_ad") or "(eşleşme yok)"}')
            # C senaryosu
            if silinmemis and not any(r.get('brans_ad') for r in silinmemis):
                print('  ◀ SENARYO C — BransId Brans tablosunda hit etmiyor.')


def main():
    db = BotanikDB()
    if not db.baglan():
        print('Botanik EOS\'a bağlanılamadı.')
        sys.exit(1)
    try:
        for ad, tc, sis in VAKALAR:
            _vaka_yazdir(db, ad, tc, sis)
    finally:
        db.kapat() if hasattr(db, 'kapat') else None


if __name__ == '__main__':
    main()
