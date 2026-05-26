# -*- coding: utf-8 -*-
"""Tanı scripti: BAKİ SOYIRGAZ (TC 11399539088, RxSgkIslemNo 305ZQ8U).

Botanik EOS'ta reçete kalemlerinde Rap.Kod/RaporNo dolu görünüyor (GUI ekran
görüntüsü 2026-05-23) ama bizim aylık reçete sorgu modülü rap_kod / rap_tesh /
rap_ack alanlarını tabloya aktaramamış. 4 SELECT ile hangi tier kırılmış net
göster:

  (1) ReceteIlaclari satırı + RIRaporKodId + RaporKodlari lookup karşılığı
  (2) SecilenRapor (SR) kaydı bu reçete için
  (3) RaporAna'da 2371376 / 2412253 / ProtokolNo='A-459005-2-001-A-...' eşleşmesi
  (4) Hastanın aynı tarih +/- 60 gün civarında geçerli rapor kodları

KIRMIZI ÇİZGİ: sadece SELECT. BotanikDB guard üzerinden.
"""
from __future__ import annotations

import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from botanik_db import BotanikDB  # noqa: E402


TC = "11399539088"
SISTEM_RECETE_NO = "305ZQ8U"


def _yaz(baslik: str):
    print("\n" + "═" * 78)
    print(f"  {baslik}")
    print("═" * 78)


def _satir(r: dict, alanlar: list, baslik: str = ""):
    if baslik:
        print(f"  ▸ {baslik}")
    for a in alanlar:
        v = r.get(a)
        print(f"    {a:32s} = {v!r}")


def main():
    db = BotanikDB()
    db.baglan()

    # ── (1) ReceteAna + ReceteIlaclari + RaporKodlari lookup ─────────────
    _yaz("(1) ReceteAna + ReceteIlaclari + RaporKodlari (RxSgkIslemNo=305ZQ8U)")
    sql1 = """
        SELECT
            ra.RxId, ra.RxEReceteNo, ra.RxSgkIslemNo, ra.RxIslemTarihi,
            ra.RxMusteriId, ra.RxDoktorId,
            m.MusteriTCKN, m.MusteriAdiSoyadi,
            ri.RIId, ri.RIUrunId, ri.RIRaporKodId, ri.RIRaporNo,
            u.UrunAdi,
            rk.RaporKodu        AS lookup_RaporKodu,
            rk.RaporKodAciklama AS lookup_RaporKodAciklama,
            ri.RISilme
        FROM ReceteAna ra
        LEFT JOIN Musteri m ON m.MusteriId = ra.RxMusteriId
        LEFT JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId
        LEFT JOIN Urun u ON u.UrunId = ri.RIUrunId
        LEFT JOIN RaporKodlari rk ON rk.RaporKodId = ri.RIRaporKodId
        WHERE ra.RxSgkIslemNo = ?
        ORDER BY ri.RIId
    """
    rows = db.sorgu_calistir(sql1, (SISTEM_RECETE_NO,))
    if not rows:
        print(f"  ✗ Reçete bulunamadı! (RxSgkIslemNo={SISTEM_RECETE_NO})")
        return
    print(f"  {len(rows)} ilaç satırı bulundu (RISilme=1 dahil).\n")
    rx_id = rows[0]["RxId"]
    musteri_id = rows[0]["RxMusteriId"]
    print(f"  RxId={rx_id}  MusteriId={musteri_id}  TC={rows[0]['MusteriTCKN']}")
    print(f"  Reçete tarihi: {rows[0]['RxIslemTarihi']}\n")
    for r in rows:
        _satir(r, [
            "RIId", "UrunAdi", "RIRaporKodId", "RIRaporNo",
            "lookup_RaporKodu", "lookup_RaporKodAciklama", "RISilme",
        ], f"İlaç: {r.get('UrunAdi')}")
        print()

    # ── (2) SecilenRapor — bu reçete için ────────────────────────────────
    _yaz("(2) SecilenRapor (SR) — bu reçeteye eczacının seçtiği rapor")
    sql2 = """
        SELECT sr.SRId, sr.SRRxId, sr.SRUrunId, sr.SRRaporNo, sr.SRRaporKodu,
               u.UrunAdi
        FROM SecilenRapor sr
        LEFT JOIN Urun u ON u.UrunId = sr.SRUrunId
        WHERE sr.SRRxId = ?
        ORDER BY sr.SRId
    """
    sr_rows = db.sorgu_calistir(sql2, (rx_id,))
    if not sr_rows:
        print("  ✗ Hiç SecilenRapor satırı yok bu reçete için.")
        print("    (Eczacı reçeteyi kaydederken rapor seçmemiş — tier (C))")
    else:
        print(f"  {len(sr_rows)} SR satırı:")
        for r in sr_rows:
            _satir(r, ["SRId", "SRUrunId", "UrunAdi", "SRRaporNo", "SRRaporKodu"])
            print()

    # ── (3) RaporAna eşleşme — RaporNo/TakipNo/ProtokolNo ─────────────────
    _yaz("(3) RaporAna — bu hastada 2371376 / 2412253 / A-459005-2-001 eşleşmesi")
    sql3 = """
        SELECT TOP 20
            rap.RaporAnaId, rap.RaporAnaRaporNo, rap.RaporAnaRaporTakipNo,
            rap.RaporAnaProtokolNo, rap.RaporAnaRaporTarihi,
            rap.RaporAnaBitisTarihi, rap.RaporAnaSilme,
            LEFT(rap.RaporAnaAciklamalar, 200) AS aciklama_ilk_200
        FROM RaporAna rap
        WHERE rap.RaporAnaMusteriId = ?
          AND (rap.RaporAnaSilme IS NULL OR rap.RaporAnaSilme = 0)
        ORDER BY rap.RaporAnaRaporTarihi DESC
    """
    rap_rows = db.sorgu_calistir(sql3, (musteri_id,))
    if not rap_rows:
        print(f"  ✗ Bu hastanın RaporAna kaydı YOK. (MusteriId={musteri_id})")
        print("    → tier0_sr_no_rapana — kullanıcı sezgisi DOĞRU: rapor EOS'ta yok.")
    else:
        print(f"  {len(rap_rows)} RaporAna satırı (en yeni 20):")
        # Aranan numaraları işaretle
        aranan = {"2371376", "2412253"}
        protokol_aranan = "A-459005"
        for r in rap_rows:
            isaret = []
            if str(r.get("RaporAnaRaporNo") or "") in aranan:
                isaret.append("◆RaporNo eşleşti")
            if str(r.get("RaporAnaRaporTakipNo") or "") in aranan:
                isaret.append("◆TakipNo eşleşti")
            pn = str(r.get("RaporAnaProtokolNo") or "")
            if protokol_aranan in pn:
                isaret.append(f"◆ProtokolNo='{pn}' içeriyor 'A-459005'")
            isaret_str = " ".join(isaret) if isaret else ""
            _satir(r, [
                "RaporAnaId", "RaporAnaRaporNo", "RaporAnaRaporTakipNo",
                "RaporAnaProtokolNo", "RaporAnaRaporTarihi",
                "RaporAnaBitisTarihi", "aciklama_ilk_200",
            ], isaret_str)
            print()

    # ── (4) RaporKodlari lookup — RIRaporKodId değerlerini kontrol et ─────
    _yaz("(4) RaporKodlari lookup — bizim sistemin yüklediği gibi")
    rkid_listesi = [r["RIRaporKodId"] for r in rows
                    if r.get("RIRaporKodId")]
    if not rkid_listesi:
        print("  ✗ Hiçbir reçete satırında RIRaporKodId dolu değil.")
    else:
        ph = ",".join("?" * len(rkid_listesi))
        sql4 = f"""
            SELECT RaporKodId, RaporKodu, RaporKodAciklama
            FROM RaporKodlari
            WHERE RaporKodId IN ({ph})
        """
        rk_rows = db.sorgu_calistir(sql4, tuple(rkid_listesi))
        print(f"  {len(rk_rows)} RaporKodlari satırı bulundu "
              f"(arananan {len(rkid_listesi)} ID için):")
        bulunan = {r["RaporKodId"] for r in rk_rows}
        eksik = set(rkid_listesi) - bulunan
        for r in rk_rows:
            print(f"    RaporKodId={r['RaporKodId']:>6} → "
                  f"Kod={r['RaporKodu']!r}  Ack={r['RaporKodAciklama']!r}")
        if eksik:
            print(f"  ✗ EKSİK ID'ler (lookup tablosunda yok!): {sorted(eksik)}")

    print("\n" + "═" * 78)
    print("  TANI SONUCU")
    print("═" * 78)
    has_sr = bool(sr_rows)
    has_rapana_match = False
    if rap_rows:
        for r in rap_rows:
            if (str(r.get("RaporAnaRaporNo") or "") in {"2371376", "2412253"} or
                str(r.get("RaporAnaRaporTakipNo") or "") in {"2371376", "2412253"} or
                "A-459005" in str(r.get("RaporAnaProtokolNo") or "")):
                has_rapana_match = True
                break
    print(f"  SecilenRapor kaydı:        {'VAR' if has_sr else 'YOK'}")
    print(f"  RaporAna eşleşmesi:        {'VAR' if has_rapana_match else 'YOK'}")
    print(f"  RIRaporKodId dolu satır:   {sum(1 for r in rows if r.get('RIRaporKodId'))}")
    print(f"  RaporKodlari lookup eksik: "
          f"{len(set(rkid_listesi) - {r['RaporKodId'] for r in (rk_rows if rkid_listesi else [])})}")


if __name__ == "__main__":
    main()
