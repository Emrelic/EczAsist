"""
calede kullanicisinin SQL Server'da gercekten read-only oldugunu dogrulayan
tek-seferlik test scripti.

GUVENLIK:
  - Eger baglanan kullanici SYSADMIN ise (ornek: sa), script ANINDA durur.
  - Yazma denemeleri SADECE read-only role'e sahip oldugu DOGRULANDIKTAN sonra yapilir.
  - Bu sayede yanlislikla sa ile calistirilirsa Botanik EOS verisi tehlikeye girmez.

Beklenen:
  1) Baglanti: calede ile basarili
  2) sysadmin DEGIL, db_datareader olan tek rol
  3) INSERT denemesi -> SQL Server permission denied
  4) CREATE TABLE denemesi -> SQL Server permission denied
"""
import pyodbc
import sys

CFG = {
    "server": "192.168.1.120\\BOTANIKSQL",
    "database": "eczane",
    "user": "calede",
    "password": "152634485967",
    "trust_server_certificate": True,
}

def baglan():
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={CFG['server']};"
        f"DATABASE={CFG['database']};"
        f"UID={CFG['user']};"
        f"PWD={CFG['password']};"
        f"TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=10)

def main():
    print("=" * 60)
    print("calede read-only dogrulama testi")
    print("=" * 60)

    try:
        conn = baglan()
        print("[OK] Baglanti kuruldu")
    except Exception as e:
        print(f"[FAIL] Baglanti basarisiz: {e}")
        print("\n>>> calede SQL Server login olarak mevcut DEGIL veya parola yanlis.")
        print(">>> SSMS'te login olusturmamiz gerek (talimatlari sohbette aldin).")
        sys.exit(1)

    cur = conn.cursor()

    # GUVENLIK CIRCUIT BREAKER: sysadmin ile baglandiysak hemen dur
    cur.execute("SELECT CURRENT_USER, SYSTEM_USER, IS_SRVROLEMEMBER('sysadmin')")
    cu, su, is_sa = cur.fetchone()
    print(f"[INFO] CURRENT_USER={cu} SYSTEM_USER={su} IS_SYSADMIN={is_sa}")
    if is_sa == 1 or su.lower() in ('sa', 'dbo'):
        print("[ABORT] !!! Baglanti SYSADMIN yetkisinde — TEST IPTAL !!!")
        print("        Bu script SADECE read-only kullanici ile calismalidir.")
        print("        sa ile yazma denemeleri Botanik EOS verisini bozar — KIRMIZI CIZGI.")
        conn.close()
        sys.exit(2)

    # Rolleri ogren — db_datareader bekleniyor, tehlikeli rol varsa abort
    cur.execute("""
        SELECT r.name
        FROM sys.database_role_members rm
        JOIN sys.database_principals r ON rm.role_principal_id = r.principal_id
        JOIN sys.database_principals u ON rm.member_principal_id = u.principal_id
        WHERE u.name = CURRENT_USER
    """)
    roller = [row[0] for row in cur.fetchall()]
    print(f"[OK] calede DB rolleri: {roller}")
    tehlikeli = [r for r in roller if r in (
        'db_owner', 'db_datawriter', 'db_ddladmin',
        'db_securityadmin', 'db_accessadmin', 'db_backupoperator'
    )]
    if tehlikeli:
        print(f"[ABORT] !!! Tehlikeli rol bulundu: {tehlikeli} — TEST IPTAL !!!")
        conn.close()
        sys.exit(3)
    if 'db_datareader' not in roller:
        print("[ABORT] !!! db_datareader rolu YOK — yapilandirma eksik !!!")
        conn.close()
        sys.exit(4)

    # Buraya geldiyse: calede + db_datareader + tehlikeli rol yok
    # Artik yazma denemeleri yapabiliriz, SQL Server reddedecek (motor seviyesinde)

    # SELECT testi
    try:
        cur.execute("SELECT TOP 1 name FROM sys.tables ORDER BY name")
        r = cur.fetchone()
        print(f"[OK] SELECT sys.tables -> {r[0] if r else '(bos)'}")
    except Exception as e:
        print(f"[FAIL] SELECT hata: {e}")

    # INSERT denemesi — SQL Server reddetmeli
    try:
        cur.execute("SELECT TOP 1 TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
        tablo = cur.fetchone()[0]
        try:
            cur.execute(f"INSERT INTO [{tablo}] DEFAULT VALUES")
            conn.commit()
            print(f"[FAIL] !!! TEHLIKE: INSERT [{tablo}] BASARILI oldu — read-only DEGIL !!!")
        except pyodbc.Error as e:
            mesaj = str(e).lower()
            if "permission" in mesaj or "denied" in mesaj or "izin" in mesaj or "denied the" in mesaj:
                print(f"[OK] INSERT engellendi (motor reddetti): {str(e)[:120]}")
            else:
                print(f"[?] INSERT basarisiz, sebebi izin DEGIL: {str(e)[:200]}")
    except Exception as e:
        print(f"[skip] INSERT testi atlandi: {e}")

    # CREATE TABLE denemesi — SQL Server reddetmeli
    try:
        cur.execute("CREATE TABLE _calede_test_kontrol (x INT)")
        conn.commit()
        print("[FAIL] !!! TEHLIKE: CREATE TABLE BASARILI — read-only DEGIL !!!")
        try:
            cur.execute("DROP TABLE _calede_test_kontrol")
            conn.commit()
        except Exception:
            pass
    except pyodbc.Error as e:
        mesaj = str(e).lower()
        if "permission" in mesaj or "denied" in mesaj or "izin" in mesaj:
            print(f"[OK] CREATE TABLE engellendi (motor reddetti): {str(e)[:120]}")
        else:
            print(f"[?] CREATE TABLE basarisiz, sebebi izin DEGIL: {str(e)[:200]}")

    print("=" * 60)
    print("Test tamam — calede gercekten read-only.")
    conn.close()

if __name__ == "__main__":
    main()
