# -*- coding: utf-8 -*-
"""Tanı scripti: Rapor eşleşmesi tespit edilemeyen reçeteler (toplu).

Kullanıcının elindeki listede 'Rapor Açıklaması' BOŞ görünen 13 reçete kalemi var
(diyabet/insülin/SGLT-2/DPP-4/pioglitazon — hepsi raporlu ilaç). Sistem bunlara
SecilenRapor → RaporAna ilintisini kuramamış. Hangi tier kırılmış, reçete reçete
göster:

  (1) ReceteIlaclari satırı + RIRaporKodId + RaporKodlari lookup karşılığı
  (2) SecilenRapor (SR) bu reçete + bu ürün için
  (3) SR.SRRaporNo'nun RaporAna'da (RaporNo / TakipNo / ProtokolNo) eşleşmesi
  (4) Aynı hasta için aktif rapor kodu+tarih fallback'in çalışıp çalışmadığı

Çıktı her reçete için tek paragraf özet + nedensel etiket:
  TIER_C_NO_SR          → SecilenRapor hiç yok (eczacı kaydederken rapor seçmemiş)
  TIER_C_SR_NO_RAPANA   → SR var ama RaporAna'da hiç eşleşmiyor (numara bozuk/silinmiş)
  TIER_B_FALLBACK_OK    → SR yok ama kod+tarih fallback eşleşti (turkuaz)
  TIER_RX_NOT_FOUND     → RxSgkIslemNo Botanik EOS'ta yok (silindi?)
  OK_DIREKT_VAR         → Aslında eşleşme var — paradoks; UI tarafı bug

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


# (TC, RxSgkIslemNo, beklenen_ilac_etiketi)
RECETELER = [
    ("14102522490", "2VO5UIF",  "GLIFIX PLUS — BİRSEL MATRACI"),
    ("44464353586", "31IIFBQ",  "GLIFIX PLUS — HAVVA GÜLEÇ"),
    ("55807316892", "2RPDQLW",  "JANUVIA + FORZIGA — TEVFİK ÖDÜNÇ"),
    ("45457910106", "2TCMNXE",  "GLIFIX — FATİME TEKE"),
    ("34774833830", "2TB8UPJ",  "DROPIA + JANUVIA — CEMAL DEMİR"),
    ("33970930374", "31J86U7",  "GLIFIX 15 — MAHMUT TURHAL (Aralık)"),
    ("33970930374", "2Z528GN",  "GLIFIX 15 — MAHMUT TURHAL (Eylül)"),
    ("17584869558", "2YH7G7C",  "GALVUS MET — AKİSE AKSU"),
    ("54820165494", "328SPF2",  "ONGLYZA — AYŞEGÜL TELLİ"),
    ("11399539088", "2D5KX0B",  "LANTUS SOLOSTAR — BAKİ SOYIRGAZ"),
    ("38734701788", "3E5AV76",  "BYETTA — AYNUR YILMAZ"),
]


def _kalin(s: str) -> str:
    return s


def _h1(s: str) -> None:
    print("\n" + "═" * 78)
    print(f"  {s}")
    print("═" * 78)


def _h2(s: str) -> None:
    print(f"\n  ── {s} " + "─" * max(0, 70 - len(s)))


def _tek_recete_tani(db: BotanikDB, tc: str, sgk: str, etiket: str) -> dict:
    sonuc = {
        "tc": tc, "sgk": sgk, "etiket": etiket,
        "rx_id": None, "musteri_id": None,
        "ilac_satirlari": [],
        "sr_satirlari": [],
        "rapana_dogrudan_eslesme": [],
        "rapana_kod_tarih_fallback": [],
        "tier_etiket": "?",
        "ozet": "",
    }
    _h1(f"{etiket}  |  TC={tc}  RxSgkIslemNo={sgk}")

    # ── (1) ReceteAna + ReceteIlaclari + RaporKodlari ─────────────────────
    sql1 = """
        SELECT
            ra.RxId, ra.RxEReceteNo, ra.RxSgkIslemNo, ra.RxIslemTarihi,
            ra.RxMusteriId,
            m.MusteriTCKN, m.MusteriAdiSoyadi,
            ri.RIId, ri.RIUrunId, ri.RIRaporKodId, ri.RIRaporNo,
            ri.RISilme,
            u.UrunAdi,
            rk.RaporKodu        AS lookup_kod,
            rk.RaporKodAciklama AS lookup_ack
        FROM ReceteAna ra
        LEFT JOIN Musteri m ON m.MusteriId = ra.RxMusteriId
        LEFT JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId
        LEFT JOIN Urun u ON u.UrunId = ri.RIUrunId
        LEFT JOIN RaporKodlari rk ON rk.RaporKodId = ri.RIRaporKodId
        WHERE ra.RxSgkIslemNo = ?
        ORDER BY ri.RIId
    """
    rows = db.sorgu_calistir(sql1, (sgk,))
    if not rows:
        sonuc["tier_etiket"] = "TIER_RX_NOT_FOUND"
        sonuc["ozet"] = f"Botanik EOS'ta RxSgkIslemNo={sgk} bulunamadı."
        print(f"  ✗ {sonuc['ozet']}")
        return sonuc

    rx_id = rows[0]["RxId"]
    musteri_id = rows[0]["RxMusteriId"]
    sonuc["rx_id"] = rx_id
    sonuc["musteri_id"] = musteri_id

    _h2(f"(1) ReceteIlaclari (RxId={rx_id}, MusteriId={musteri_id}, tarih={rows[0]['RxIslemTarihi']})")
    for r in rows:
        if r.get("RIId") is None:
            print(f"     (ReceteAna var, ama ReceteIlaclari satırı yok!)")
            continue
        sonuc["ilac_satirlari"].append({
            "RIId": r["RIId"],
            "UrunAdi": r.get("UrunAdi"),
            "RIRaporKodId": r.get("RIRaporKodId"),
            "RIRaporNo": r.get("RIRaporNo"),
            "lookup_kod": r.get("lookup_kod"),
            "lookup_ack": r.get("lookup_ack"),
            "RISilme": r.get("RISilme"),
        })
        silme_isaret = " [SİLİNMİŞ]" if r.get("RISilme") else ""
        print(f"     RIId={r['RIId']:>7} | {r.get('UrunAdi','')!r}{silme_isaret}")
        print(f"          RIRaporKodId={r.get('RIRaporKodId')!r}  RIRaporNo={r.get('RIRaporNo')!r}")
        print(f"          lookup_kod={r.get('lookup_kod')!r}  lookup_ack={r.get('lookup_ack')!r}")

    # ── (2) SecilenRapor (SR) — bu reçete için ─────────────────────────────
    _h2(f"(2) SecilenRapor — RxId={rx_id}")
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
        print("     ✗ Hiç SecilenRapor satırı YOK bu reçete için.")
        print("       → Eczacı reçeteyi kaydederken RAPOR SEÇMEMİŞ.")
    else:
        for r in sr_rows:
            sonuc["sr_satirlari"].append({
                "SRId": r["SRId"],
                "SRUrunId": r["SRUrunId"],
                "UrunAdi": r.get("UrunAdi"),
                "SRRaporNo": r.get("SRRaporNo"),
                "SRRaporKodu": r.get("SRRaporKodu"),
            })
            print(f"     SRId={r['SRId']:>7} | {r.get('UrunAdi','')!r}")
            print(f"          SRRaporNo={r.get('SRRaporNo')!r}  SRRaporKodu={r.get('SRRaporKodu')!r}")

    # ── (3) RaporAna — hasta için direkt numara eşleşmesi ──────────────────
    _h2(f"(3) RaporAna — MusteriId={musteri_id} (RaporNo/TakipNo/ProtokolNo eşleşmesi)")
    # NOT: RaporAna tablosunda BitisTarihi kolonu YOK — yalnız RaporTarihi.
    # Rapor geçerlilik bitişi RaporRaporKodlariICD.RRKIBitisTarihi'den okunur
    # (zaten aşağıdaki kod+tarih fallback sorgusunda kullanılıyor).
    sql3 = """
        SELECT TOP 30
            rap.RaporAnaId, rap.RaporAnaRaporNo, rap.RaporAnaRaporTakipNo,
            rap.RaporAnaProtokolNo, rap.RaporAnaRaporTarihi,
            rap.RaporAnaSilme,
            LEFT(rap.RaporAnaAciklamalar, 120) AS aciklama_120
        FROM RaporAna rap
        WHERE rap.RaporAnaMusteriId = ?
          AND (rap.RaporAnaSilme IS NULL OR rap.RaporAnaSilme = 0)
        ORDER BY rap.RaporAnaRaporTarihi DESC
    """
    rap_rows = db.sorgu_calistir(sql3, (musteri_id,))
    if not rap_rows:
        print(f"     ✗ Bu hastanın hiç RaporAna kaydı YOK (silinmemiş).")
    else:
        print(f"     {len(rap_rows)} RaporAna satırı (en yeni 30):")
        sr_numaralari = {str(sr["SRRaporNo"]).strip() for sr in sr_rows
                          if sr.get("SRRaporNo")}
        for r in rap_rows[:30]:
            no = str(r.get("RaporAnaRaporNo") or "").strip()
            tk = str(r.get("RaporAnaRaporTakipNo") or "").strip()
            pn = str(r.get("RaporAnaProtokolNo") or "").strip()
            eslesti = ""
            if no in sr_numaralari:
                eslesti = "  ◆SR.RaporNo eşleşti"
                sonuc["rapana_dogrudan_eslesme"].append(r["RaporAnaId"])
            elif tk in sr_numaralari:
                eslesti = "  ◆SR.TakipNo eşleşti"
                sonuc["rapana_dogrudan_eslesme"].append(r["RaporAnaId"])
            elif pn in sr_numaralari:
                eslesti = "  ◆SR.ProtokolNo eşleşti"
                sonuc["rapana_dogrudan_eslesme"].append(r["RaporAnaId"])
            print(f"     RaporAnaId={r['RaporAnaId']:>7} | "
                  f"No={no!r} Tk={tk!r}{eslesti}")
            print(f"          ProtokolNo={pn!r}")
            print(f"          RaporTarihi={r.get('RaporAnaRaporTarihi')}")
            ack = (r.get("aciklama_120") or "").strip()
            if ack:
                print(f"          Açıklama120={ack!r}")

    # ── (4) Kod+tarih fallback (sadece SR var ama direkt eşleşme yoksa anlamlı) ─
    if sr_rows and not sonuc["rapana_dogrudan_eslesme"]:
        _h2(f"(4) Kod+tarih fallback — SR.SRRaporKodu + RIIslemTarihi içinde geçerli rapor")
        # SR.SRRaporKodu seti
        sr_kodlari = {str(sr["SRRaporKodu"]).strip() for sr in sr_rows
                       if sr.get("SRRaporKodu")}
        if not sr_kodlari:
            print("     ✗ SR.SRRaporKodu boş — fallback denenemez.")
        else:
            ph = ",".join("?" * len(sr_kodlari))
            params = list(sr_kodlari) + [musteri_id, rows[0]["RxIslemTarihi"],
                                          rows[0]["RxIslemTarihi"]]
            # Rapor bitişi RRKIBitisTarihi'den (WHERE'de zaten süzülüyor)
            sql4 = f"""
                SELECT TOP 5
                    rap.RaporAnaId, rap.RaporAnaRaporNo,
                    rap.RaporAnaRaporTarihi,
                    rrk.RRKIBaslamaTarihi, rrk.RRKIBitisTarihi,
                    rk.RaporKodu
                FROM RaporAna rap
                INNER JOIN RaporRaporKodlariICD rrk
                        ON rrk.RRKIRaporAnaId = rap.RaporAnaId
                INNER JOIN RaporKodlari rk
                        ON rk.RaporKodId = rrk.RRKIRaporKodId
                WHERE rk.RaporKodu IN ({ph})
                  AND rap.RaporAnaMusteriId = ?
                  AND (rap.RaporAnaSilme IS NULL OR rap.RaporAnaSilme = 0)
                  AND (rrk.RRKISilme IS NULL OR rrk.RRKISilme = 0)
                  AND (rrk.RRKIBaslamaTarihi IS NULL
                       OR rrk.RRKIBaslamaTarihi <= ?)
                  AND (rrk.RRKIBitisTarihi   IS NULL
                       OR rrk.RRKIBitisTarihi   >= ?)
                ORDER BY rap.RaporAnaRaporTarihi DESC
            """
            fb_rows = db.sorgu_calistir(sql4, tuple(params))
            if not fb_rows:
                print(f"     ✗ Kod {sorted(sr_kodlari)!r} + tarih "
                      f"{rows[0]['RxIslemTarihi']} ile fallback eşleşmesi YOK.")
            else:
                print(f"     ✓ {len(fb_rows)} fallback eşleşmesi VAR:")
                for r in fb_rows:
                    sonuc["rapana_kod_tarih_fallback"].append(r["RaporAnaId"])
                    print(f"       RaporAnaId={r['RaporAnaId']} | "
                          f"Kod={r['RaporKodu']!r}  "
                          f"RaporTarihi={r['RaporAnaRaporTarihi']} | "
                          f"Kod geçerli: {r['RRKIBaslamaTarihi']} → "
                          f"{r['RRKIBitisTarihi']}")

    # ── Tier etiketleme ─────────────────────────────────────────────────────
    if not sr_rows:
        sonuc["tier_etiket"] = "TIER_C_NO_SR"
        sonuc["ozet"] = "SecilenRapor yok — eczacı rapor seçmeden kaydetmiş."
    elif sonuc["rapana_dogrudan_eslesme"]:
        sonuc["tier_etiket"] = "OK_DIREKT_VAR"
        sonuc["ozet"] = (
            f"SR.RaporNo RaporAna'da bulundu (RaporAnaId="
            f"{sonuc['rapana_dogrudan_eslesme'][:2]}). UI'da boş görünmesi paradoks.")
    elif sonuc["rapana_kod_tarih_fallback"]:
        sonuc["tier_etiket"] = "TIER_B_FALLBACK_OK"
        sonuc["ozet"] = (
            f"SR direkt eşleşmedi ama kod+tarih fallback ile bulundu "
            f"(RaporAnaId={sonuc['rapana_kod_tarih_fallback'][:2]}).")
    else:
        sonuc["tier_etiket"] = "TIER_C_SR_NO_RAPANA"
        sonuc["ozet"] = (
            "SR var ama RaporAna'da ne direkt eşleşme ne kod+tarih fallback — "
            "rapor numarası bozuk/silinmiş.")

    _h2("ÖZET")
    print(f"     Tier: {sonuc['tier_etiket']}")
    print(f"     {sonuc['ozet']}")
    return sonuc


def main():
    db = BotanikDB()
    db.baglan()

    tum_sonuclar = []
    for tc, sgk, etiket in RECETELER:
        try:
            r = _tek_recete_tani(db, tc, sgk, etiket)
            tum_sonuclar.append(r)
        except Exception as e:
            print(f"\n  ✗ HATA ({etiket}): {e}")
            tum_sonuclar.append({"tc": tc, "sgk": sgk, "etiket": etiket,
                                  "tier_etiket": "HATA", "ozet": str(e)})

    # Toplu özet
    _h1("TÜM REÇETELER — TOPLU ÖZET")
    print(f"  {'TC':<12} {'SgkIslemNo':<10} {'Tier':<22} Etiket")
    print(f"  {'-'*12} {'-'*10} {'-'*22} {'-'*40}")
    for s in tum_sonuclar:
        print(f"  {s['tc']:<12} {s['sgk']:<10} {s['tier_etiket']:<22} {s['etiket']}")

    # Tier dağılımı
    from collections import Counter
    dag = Counter(s["tier_etiket"] for s in tum_sonuclar)
    print(f"\n  Tier dağılımı:")
    for tier, n in dag.most_common():
        print(f"    {tier:<22} : {n}")


if __name__ == "__main__":
    main()
