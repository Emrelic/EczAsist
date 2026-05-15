"""
Yeni allow-list tabanli _guvenlik_kontrolu icin kapsamli akil testi.

KABUL edilmesi gerekenler:
- SELECT ile baslayan her sey
- WITH (CTE) ile baslayan her sey
- ;WITH (lider noktali virgul + WITH)
- Lider whitespace / yorum / noktali virgul karma karma

REDDEDILMESI gerekenler:
- INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/MERGE/EXEC/EXECUTE/...
- Bos sorgu, sadece-yorum sorgu
- SELECT'e benzeyen ama tam degil (SELECTABC, WITHHOLD vb.)
"""
import sys
sys.path.insert(0, r"C:\Users\ana\OneDrive\Desktop\Uibul3.0\EczAsist")

from botanik_db import BotanikDB

db = BotanikDB()

KABUL_EDILEN = [
    "SELECT 1",
    "select * from sys.tables",
    "  SELECT * FROM x  ",
    "\n\n\tSELECT * FROM x\n",
    "WITH cte AS (SELECT 1) SELECT * FROM cte",
    ";WITH cte AS (SELECT 1) SELECT * FROM cte",
    " ;\n;\n;WITH cte AS (SELECT 1) SELECT * FROM cte",
    "-- yorum\nSELECT 1",
    "/* blok yorum */ SELECT 1",
    "/* iki\nsatirli\nyorum */\nSELECT 1",
    "-- bir\n-- iki\n-- uc\nSELECT 1",
    "; -- yorum\n;WITH x AS (SELECT 1) SELECT * FROM x",
    "SELECT (SELECT TOP 1 col FROM t2) FROM t1",  # alt sorgu
    "SELECT 1 WHERE 'INSERT TROLL' LIKE '%TROLL%'",  # string icinde INSERT
]

REDDEDILEN = [
    "INSERT INTO x VALUES (1)",
    "insert into x values (1)",
    "UPDATE x SET y=1",
    "DELETE FROM x",
    "DROP TABLE x",
    "CREATE TABLE x (id INT)",
    "ALTER TABLE x ADD y INT",
    "TRUNCATE TABLE x",
    "MERGE INTO x USING ...",
    "EXEC sp_who",
    "EXECUTE sp_who",
    "GRANT SELECT TO calede",
    "REVOKE SELECT FROM calede",
    "DENY INSERT TO calede",
    "BACKUP DATABASE eczane TO DISK='x.bak'",
    "RESTORE DATABASE eczane FROM DISK='x.bak'",
    "SHUTDOWN",
    "KILL 53",
    "",
    "   ",
    "\n\n\n",
    "-- sadece yorum",
    "-- yorum 1\n-- yorum 2",
    "/* yorum */",
    "/* kapanmamis yorum",
    "SELECTOR FROM x",  # SELECT benzeri ama yanlis
    "WITHHOLD x FROM y",  # WITH benzeri ama yanlis
    "SELECTabc FROM x",  # bitisik
    "SET @x = 1",
    "DECLARE @x INT",
    "BEGIN TRAN",
    "USE master",
]

print("=" * 70)
print("ALLOW-LIST GUVENLIK KONTROLU AKIL TESTI")
print("=" * 70)

fail = 0
print("\n--- KABUL edilmesi gereken (true beklenen) ---")
for sql in KABUL_EDILEN:
    sonuc = db._guvenlik_kontrolu(sql)
    durum = "[OK]" if sonuc else "[FAIL]"
    if not sonuc:
        fail += 1
    print(f"  {durum} {sql[:60]!r}")

print("\n--- REDDEDILMESI gereken (false beklenen) ---")
for sql in REDDEDILEN:
    sonuc = db._guvenlik_kontrolu(sql)
    durum = "[OK]" if not sonuc else "[FAIL]"
    if sonuc:
        fail += 1
    print(f"  {durum} {sql[:60]!r}")

print("\n" + "=" * 70)
toplam = len(KABUL_EDILEN) + len(REDDEDILEN)
print(f"Sonuc: {toplam - fail}/{toplam} basarili, {fail} FAIL")
print("=" * 70)
sys.exit(0 if fail == 0 else 1)
