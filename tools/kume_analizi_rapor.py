# -*- coding: utf-8 -*-
"""
Küme Analizi raporu — 2021-2026 (SADECE SELECT, Botanik EOS salt-okunur).

Kümeler (kullanıcı notasyonu):
  T = tüm ilaç satırları
  B = içerik filtresinin elediği küme (beyaz ∧ raporsuz ∧ uyarı-kodsuz ∧ mesajsız)
  K = kontrolü gereksiz ilaçlar kümesi
  X = B ∩ K   Y = B ∪ K   C = B∪K dışı
  b = B ∖ K   k = K ∖ B
"""
import sys
import os
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from botanik_db import BotanikDB
import kontrol_disi_ilaclar as kdi
import aylik_filtre_ayarlari as fa


def _fmt(n):
    return f"{int(n or 0):,}".replace(",", ".")


def main():
    db = BotanikDB(production=True)
    if not db.baglan():
        print("DB bağlanamadı.")
        return

    # Renkli (kırmızı/yeşil/mor) reçete renk ID'leri
    renkli_idler = []
    for r in db.sorgu_calistir(
            "SELECT ReceteRenkId, ReceteRenkAdi FROM ReceteRenk "
            "WHERE ReceteRenkSilme=0"):
        ad = (r.get("ReceteRenkAdi") or "").strip().lower()
        if ad in ("kırmızı", "kirmizi", "yeşil", "yesil", "mor"):
            renkli_idler.append(r["ReceteRenkId"])
    renkli_idler = sorted(renkli_idler)

    # K predicate (kontrolü gereksiz ilaçlar — pozitif eşleşme)
    k_pred = kdi.sql_eslesme_kosulu()
    liste_bos = not k_pred
    if liste_bos:
        k_pred = "(0 = 1)"

    # İçerik koşulu (4 toggle açık) → B = NOT(içerik)
    ay_all = {"renkli_getir": True, "mesaj_getir": True,
              "uyari_getir": True, "rapor_getir": True}
    icerik = fa.sql_icerik_kosullari(ay_all, renkli_idler)
    b_pred = f"(NOT {icerik})"

    TARIH = ("ra.RxKayitTarihi >= '2021-01-01' "
             "AND ra.RxKayitTarihi < '2027-01-01'")
    FROM_SQL = (
        "FROM ReceteAna ra "
        "INNER JOIN ReceteIlaclari ri ON ri.RIRxId = ra.RxId AND ri.RISilme = 0 "
        "LEFT JOIN Urun u ON u.UrunId = ri.RIUrunId "
        "LEFT JOIN ATC atc ON atc.ATCId = u.UrunATCId "
        f"WHERE ra.RxSilme = 0 AND {TARIH}")

    agg_sql = f"""
        SELECT
            SUM(CASE WHEN K=1 AND B=1 THEN 1 ELSE 0 END) AS kesisim,
            SUM(CASE WHEN K=1 AND B=0 THEN 1 ELSE 0 END) AS sadece_k,
            SUM(CASE WHEN K=0 AND B=1 THEN 1 ELSE 0 END) AS sadece_b,
            SUM(CASE WHEN K=0 AND B=0 THEN 1 ELSE 0 END) AS hicbiri,
            SUM(CAST(K AS BIGINT)) AS toplam_k,
            SUM(CAST(B AS BIGINT)) AS toplam_b,
            COUNT(*) AS toplam
        FROM (
            SELECT
                CASE WHEN {k_pred} THEN 1 ELSE 0 END AS K,
                CASE WHEN {b_pred} THEN 1 ELSE 0 END AS B
            {FROM_SQL}
        ) t
    """

    print("Sorgu çalışıyor (2021-2026)… uzun sürebilir.")
    r = db.sorgu_calistir(agg_sql)[0]

    X = int(r.get("kesisim") or 0)
    k = int(r.get("sadece_k") or 0)
    b = int(r.get("sadece_b") or 0)
    C = int(r.get("hicbiri") or 0)
    Kk = int(r.get("toplam_k") or 0)
    Bk = int(r.get("toplam_b") or 0)
    T = int(r.get("toplam") or 0)
    Y = b + k + X

    def _ornek(bolge):
        sql = f"""
            SELECT TOP 25 ISNULL(u.UrunAdi, N'(bilinmeyen)') AS ilac,
                   COUNT(*) AS adet
            {FROM_SQL} AND ({bolge})
            GROUP BY u.UrunAdi ORDER BY COUNT(*) DESC
        """
        return db.sorgu_calistir(sql)

    ornek_k = [] if liste_bos else _ornek(f"({k_pred}) AND NOT ({b_pred})")
    ornek_b = _ornek(f"NOT ({k_pred}) AND ({b_pred})")

    L = []
    L.append("=" * 60)
    L.append("  KÜME ANALİZİ — 2021-2026 (reçete-ilaç satırı bazında)")
    L.append("=" * 60)
    L.append("")
    L.append("  TANIMLAR")
    L.append("    T = Tüm ilaç satırları (2021-2026)")
    L.append("    B = beyaz ∧ raporsuz ∧ uyarı-kodsuz ∧ mesajsız (elenen)")
    L.append("    K = Kontrolü gereksiz ilaçlar")
    L.append("    X = B∩K   Y = B∪K   C = B∪K dışı   b = B∖K   k = K∖B")
    L.append("")
    L.append("  SAYILAR")
    L.append(f"    b  Sadece B (B∖K)        : {_fmt(b):>14}")
    L.append(f"    k  Sadece K (K∖B)        : {_fmt(k):>14}")
    L.append(f"    X  Kesişim (B∩K)         : {_fmt(X):>14}")
    L.append(f"    C  Ne B ne K (B∪K dışı)  : {_fmt(C):>14}")
    L.append("    " + "-" * 36)
    L.append(f"    B  Toplam B (b+X)        : {_fmt(Bk):>14}")
    L.append(f"    K  Toplam K (k+X)        : {_fmt(Kk):>14}")
    L.append(f"    Y  Birleşim (b+k+X)      : {_fmt(Y):>14}")
    L.append(f"    T  TOPLAM satır          : {_fmt(T):>14}")
    L.append("")
    L.append("  DOĞRULAMA")
    L.append(f"    B+K-X = Y : {_fmt(Bk)} + {_fmt(Kk)} - {_fmt(X)} = {_fmt(Y)}")
    L.append(f"    Y+C   = T : {_fmt(Y)} + {_fmt(C)} = {_fmt(T)}")
    L.append("")
    if Kk > Bk:
        L.append(f"  ► DAHA BÜYÜK PENCERE: K (kontrol-dışı) > B  "
                 f"({_fmt(Kk)} > {_fmt(Bk)})")
    elif Bk > Kk:
        L.append(f"  ► DAHA BÜYÜK PENCERE: B (boş/atlanır) > K  "
                 f"({_fmt(Bk)} > {_fmt(Kk)})")
    else:
        L.append(f"  ► İKİ KAPSAM EŞİT: {_fmt(Kk)}")
    if liste_bos:
        L.append("  ⚠ Kontrol-dışı liste BOŞ → K=0 (k=0, X=0).")
    L.append("")
    L.append("  k = Sadece-K en sık 25 ilaç:")
    for x in ornek_k:
        L.append(f"     {_fmt(x.get('adet')):>8}  {(x.get('ilac') or '').strip()}")
    if not ornek_k:
        L.append("     (yok)")
    L.append("")
    L.append("  b = Sadece-B en sık 25 ilaç:")
    for x in ornek_b:
        L.append(f"     {_fmt(x.get('adet')):>8}  {(x.get('ilac') or '').strip()}")
    if not ornek_b:
        L.append("     (yok)")

    rapor = "\n".join(L)
    print(rapor)

    import os
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "kume_analizi_rapor_cikti.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(rapor)
    print(f"\n(Rapor dosyası: {out})")


if __name__ == "__main__":
    main()
