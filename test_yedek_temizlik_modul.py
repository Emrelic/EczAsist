#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Yedek Temizlik Modülü smoke testleri (çoklu profil sürümü)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from yedek_temizlik_modul import (
    YedekTemizlikDepo,
    YedekTemizlikProfil,
    YedekTemizlikYonetici,
    tum_profilleri_gunluk_calistir,
    MOD_GUN,
    MOD_ADET,
)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _dosya_olustur(klasor: Path, ad: str, gun_geriden: float) -> Path:
    yol = klasor / ad
    yol.write_text("dummy", encoding="utf-8")
    epoch = time.time() - gun_geriden * 86400
    os.utime(yol, (epoch, epoch))
    return yol


def _depo_kur(tmp: Path) -> YedekTemizlikDepo:
    return YedekTemizlikDepo(ayar_yolu=tmp / "ayar.json", log_yolu=tmp / "log.txt")


def _profil_yarat(depo: YedekTemizlikDepo, **kw) -> YedekTemizlikProfil:
    p = YedekTemizlikProfil(**kw)
    depo.profiller.append(p)
    depo.kaydet()
    return p


# ---------------------------------------------------------------------------
# Mantık testleri (tekil profil)
# ---------------------------------------------------------------------------
def test_1_gun_modu_basit():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); klasor = td / "y"; klasor.mkdir()
        for i in range(10):
            _dosya_olustur(klasor, f"b_{i}.bak", gun_geriden=i)
        depo = _depo_kur(td)
        p = _profil_yarat(depo, ad="A", klasor_yolu=str(klasor),
                         mod=MOD_GUN, gun_sayisi=3,
                         yeni_dosya_kontrol_aktif=True)
        sonuc = YedekTemizlikYonetici(p, depo).temizle()
        assert sonuc["silinen_sayi"] == 7
        assert sonuc["korunan_sayi"] == 3
    print("✓ test_1_gun_modu_basit")


def test_2_guvenlik_yeni_dosya_yok():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); klasor = td / "y"; klasor.mkdir()
        for i in range(5):
            _dosya_olustur(klasor, f"o_{i}.bak", gun_geriden=10 + i)
        depo = _depo_kur(td)
        p = _profil_yarat(depo, ad="A", klasor_yolu=str(klasor),
                         mod=MOD_GUN, gun_sayisi=3,
                         yeni_dosya_kontrol_aktif=True)
        sonuc = YedekTemizlikYonetici(p, depo).temizle()
        assert sonuc["silinen_sayi"] == 0
        assert "GÜVENLİK" in sonuc["atlama_nedeni"]
        assert len(list(klasor.iterdir())) == 5
    print("✓ test_2_guvenlik_yeni_dosya_yok")


def test_3_guvenlik_kapali_hepsi_silinir():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); klasor = td / "y"; klasor.mkdir()
        for i in range(5):
            _dosya_olustur(klasor, f"o_{i}.bak", gun_geriden=10 + i)
        depo = _depo_kur(td)
        p = _profil_yarat(depo, ad="A", klasor_yolu=str(klasor),
                         mod=MOD_GUN, gun_sayisi=3,
                         yeni_dosya_kontrol_aktif=False)
        sonuc = YedekTemizlikYonetici(p, depo).temizle()
        assert sonuc["silinen_sayi"] == 5
        assert len(list(klasor.iterdir())) == 0
    print("✓ test_3_guvenlik_kapali_hepsi_silinir")


def test_4_adet_modu():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); klasor = td / "y"; klasor.mkdir()
        for i in range(10):
            _dosya_olustur(klasor, f"b_{i:02d}.bak", gun_geriden=i)
        depo = _depo_kur(td)
        p = _profil_yarat(depo, ad="A", klasor_yolu=str(klasor),
                         mod=MOD_ADET, kopya_sayisi=5)
        sonuc = YedekTemizlikYonetici(p, depo).temizle()
        assert sonuc["silinen_sayi"] == 5
        kalan = sorted(x.name for x in klasor.iterdir())
        assert kalan == [f"b_0{i}.bak" for i in range(5)]
    print("✓ test_4_adet_modu")


def test_5_adet_modu_dosya_az():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); klasor = td / "y"; klasor.mkdir()
        for i in range(3):
            _dosya_olustur(klasor, f"b_{i}.bak", gun_geriden=i)
        depo = _depo_kur(td)
        p = _profil_yarat(depo, ad="A", klasor_yolu=str(klasor),
                         mod=MOD_ADET, kopya_sayisi=5)
        sonuc = YedekTemizlikYonetici(p, depo).temizle()
        assert sonuc["silinen_sayi"] == 0
        assert "silinecek yok" in sonuc["atlama_nedeni"]
    print("✓ test_5_adet_modu_dosya_az")


def test_6_uzanti_filtresi():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); klasor = td / "y"; klasor.mkdir()
        for i in range(5):
            _dosya_olustur(klasor, f"b_{i}.bak", gun_geriden=i)
            _dosya_olustur(klasor, f"r_{i}.txt", gun_geriden=i)
        depo = _depo_kur(td)
        p = _profil_yarat(depo, ad="A", klasor_yolu=str(klasor),
                         mod=MOD_GUN, gun_sayisi=2,
                         uzanti_filtresi=".bak",
                         yeni_dosya_kontrol_aktif=True)
        sonuc = YedekTemizlikYonetici(p, depo).temizle()
        assert sonuc["silinen_sayi"] == 3
        kalanlar = sorted(x.name for x in klasor.iterdir())
        assert len(kalanlar) == 7
    print("✓ test_6_uzanti_filtresi")


def test_7_klasor_yok():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        depo = _depo_kur(td)
        p = _profil_yarat(depo, ad="A", klasor_yolu=str(td / "olmayan"),
                         mod=MOD_GUN, gun_sayisi=3)
        sonuc = YedekTemizlikYonetici(p, depo).temizle()
        assert sonuc["silinen_sayi"] == 0
        assert sonuc["atlama_nedeni"]
    print("✓ test_7_klasor_yok")


def test_8_gunluk_otomatik_idempotent():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); klasor = td / "y"; klasor.mkdir()
        for i in range(8):
            _dosya_olustur(klasor, f"b_{i}.bak", gun_geriden=i)
        depo = _depo_kur(td)
        p = _profil_yarat(depo, ad="A", klasor_yolu=str(klasor),
                         mod=MOD_GUN, gun_sayisi=3,
                         yeni_dosya_kontrol_aktif=True)
        y = YedekTemizlikYonetici(p, depo)
        s1 = y.gunluk_otomatik_calistir(bugun=date.today())
        assert s1 is not None and s1["silinen_sayi"] == 5
        s2 = y.gunluk_otomatik_calistir(bugun=date.today())
        assert s2 is None
        s3 = y.gunluk_otomatik_calistir(bugun=date.today() + timedelta(days=1))
        assert s3 is not None
    print("✓ test_8_gunluk_otomatik_idempotent")


def test_9_log_yazimi():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); klasor = td / "y"; klasor.mkdir()
        for i in range(4):
            _dosya_olustur(klasor, f"b_{i}.bak", gun_geriden=i)
        depo = _depo_kur(td)
        p = _profil_yarat(depo, ad="LogTest", klasor_yolu=str(klasor),
                         mod=MOD_GUN, gun_sayisi=2,
                         yeni_dosya_kontrol_aktif=True)
        YedekTemizlikYonetici(p, depo).temizle()
        assert depo.log_yolu.exists()
        icerik = depo.log_yolu.read_text(encoding="utf-8")
        assert "TEMIZLIK" in icerik
        assert "profil='LogTest'" in icerik
    print("✓ test_9_log_yazimi")


def test_10_alt_klasor_dokunulmaz():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); klasor = td / "y"; klasor.mkdir()
        alt = klasor / "arsiv"; alt.mkdir()
        _dosya_olustur(klasor, "ust.bak", gun_geriden=10)
        _dosya_olustur(alt, "alt.bak", gun_geriden=10)
        _dosya_olustur(klasor, "yeni.bak", gun_geriden=0)
        depo = _depo_kur(td)
        p = _profil_yarat(depo, ad="A", klasor_yolu=str(klasor),
                         mod=MOD_GUN, gun_sayisi=3,
                         yeni_dosya_kontrol_aktif=True)
        sonuc = YedekTemizlikYonetici(p, depo).temizle()
        assert sonuc["silinen_sayi"] == 1
        assert (alt / "alt.bak").exists()
    print("✓ test_10_alt_klasor_dokunulmaz")


# ---------------------------------------------------------------------------
# Çoklu profil testleri
# ---------------------------------------------------------------------------
def test_11_iki_profil_iki_kural():
    """2 ayrı klasör, 2 ayrı kural — aynı çağrıda ikisi de işlenmeli."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        k1 = td / "yedek1"; k1.mkdir()
        k2 = td / "yedek2"; k2.mkdir()
        for i in range(10):
            _dosya_olustur(k1, f"a_{i:02d}.bak", gun_geriden=i)  # gün modu
            _dosya_olustur(k2, f"b_{i:02d}.zip", gun_geriden=i)  # adet modu
        depo = _depo_kur(td)
        _profil_yarat(depo, ad="Profil-Gün", klasor_yolu=str(k1),
                     mod=MOD_GUN, gun_sayisi=3,
                     yeni_dosya_kontrol_aktif=True)
        _profil_yarat(depo, ad="Profil-Adet", klasor_yolu=str(k2),
                     mod=MOD_ADET, kopya_sayisi=4)
        sonuclar = tum_profilleri_gunluk_calistir(depo)
        assert len(sonuclar) == 2
        # k1: 3 günden eski 7 dosya silinmeli, 3 kalmalı
        # k2: en yeni 4 hariç 6 dosya silinmeli
        ad_to_silinen = {s["profil"]: s["silinen_sayi"] for s in sonuclar}
        assert ad_to_silinen["Profil-Gün"] == 7, ad_to_silinen
        assert ad_to_silinen["Profil-Adet"] == 6, ad_to_silinen
        assert len(list(k1.iterdir())) == 3
        assert len(list(k2.iterdir())) == 4
    print("✓ test_11_iki_profil_iki_kural")


def test_12_pasif_profil_atlanir():
    """Aktif değil işaretli profil otomatik tetikte atlanır."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        k1 = td / "y1"; k1.mkdir(); k2 = td / "y2"; k2.mkdir()
        for i in range(6):
            _dosya_olustur(k1, f"a_{i}.bak", gun_geriden=i)
            _dosya_olustur(k2, f"b_{i}.bak", gun_geriden=i)
        depo = _depo_kur(td)
        _profil_yarat(depo, ad="Aktif", klasor_yolu=str(k1),
                     mod=MOD_GUN, gun_sayisi=2,
                     yeni_dosya_kontrol_aktif=True, aktif=True)
        _profil_yarat(depo, ad="Pasif", klasor_yolu=str(k2),
                     mod=MOD_GUN, gun_sayisi=2,
                     yeni_dosya_kontrol_aktif=True, aktif=False)
        sonuclar = tum_profilleri_gunluk_calistir(depo)
        adlar = [s["profil"] for s in sonuclar]
        assert adlar == ["Aktif"], f"Sonuçlar: {adlar}"
        # Pasif klasör değişmemiş olmalı
        assert len(list(k2.iterdir())) == 6
    print("✓ test_12_pasif_profil_atlanir")


def test_13_eski_format_migration():
    """Eski tek-profil JSON yeni formata dönüştürülür."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); klasor = td / "y"; klasor.mkdir()
        ayar = td / "ayar.json"
        eski = {
            "klasor_yolu": str(klasor),
            "mod": MOD_GUN,
            "gun_sayisi": 7,
            "kopya_sayisi": 5,
            "uzanti_filtresi": ".bak",
            "yeni_dosya_kontrol_aktif": True,
            "otomatik_calistir": True,
        }
        ayar.write_text(json.dumps(eski), encoding="utf-8")
        depo = YedekTemizlikDepo(ayar_yolu=ayar, log_yolu=td / "log.txt")
        assert len(depo.profiller) == 1
        p = depo.profiller[0]
        assert p.ad == "Varsayılan"
        assert p.gun_sayisi == 7
        assert p.uzanti_filtresi == ".bak"
        # Disk yeni formatta yazılmış olmalı
        on_disk = json.loads(ayar.read_text(encoding="utf-8"))
        assert "profiller" in on_disk
        assert on_disk["profiller"][0]["ad"] == "Varsayılan"
    print("✓ test_13_eski_format_migration")


def test_14_global_otomatik_kapali_hepsini_atla():
    """Global otomatik_calistir=False ise tüm profiller atlanır."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); klasor = td / "y"; klasor.mkdir()
        for i in range(5):
            _dosya_olustur(klasor, f"b_{i}.bak", gun_geriden=i)
        depo = _depo_kur(td)
        depo.otomatik_calistir = False
        _profil_yarat(depo, ad="A", klasor_yolu=str(klasor),
                     mod=MOD_GUN, gun_sayisi=2,
                     yeni_dosya_kontrol_aktif=True)
        sonuclar = tum_profilleri_gunluk_calistir(depo)
        assert sonuclar == []
        # Dosyalar bozulmamış
        assert len(list(klasor.iterdir())) == 5
    print("✓ test_14_global_otomatik_kapali_hepsini_atla")


def test_15_profil_yonetimi():
    """Profil ekle/sil/yeniden-adlandır + benzersizleştirme."""
    with tempfile.TemporaryDirectory() as td:
        depo = _depo_kur(Path(td))
        p1 = depo.profil_ekle("Botanik")
        p2 = depo.profil_ekle("Botanik")  # aynı ad → "Botanik 2"
        assert p2.ad == "Botanik 2"
        # Yeniden adlandırma çakışması
        assert depo.profil_yeniden_adlandir("Botanik 2", "Botanik") is False
        assert depo.profil_yeniden_adlandir("Botanik 2", "Medula") is True
        assert depo.profil_bul("Medula") is not None
        # Silme
        assert depo.profil_sil("Botanik") is True
        assert len(depo.profiller) == 1
        # Diskten yeniden oku, kalıcı olduğundan emin ol
        depo2 = YedekTemizlikDepo(ayar_yolu=depo.ayar_yolu, log_yolu=depo.log_yolu)
        assert len(depo2.profiller) == 1
        assert depo2.profiller[0].ad == "Medula"
    print("✓ test_15_profil_yonetimi")


def test_16_iki_profil_son_tarih_bagimsiz():
    """Her profilin son_calisma_tarihi bağımsız tutulur — biri çalıştırılırsa diğeri etkilenmez."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); k1 = td / "y1"; k1.mkdir(); k2 = td / "y2"; k2.mkdir()
        for i in range(6):
            _dosya_olustur(k1, f"a_{i}.bak", gun_geriden=i)
            _dosya_olustur(k2, f"b_{i}.bak", gun_geriden=i)
        depo = _depo_kur(td)
        p1 = _profil_yarat(depo, ad="P1", klasor_yolu=str(k1),
                          mod=MOD_GUN, gun_sayisi=2,
                          yeni_dosya_kontrol_aktif=True)
        p2 = _profil_yarat(depo, ad="P2", klasor_yolu=str(k2),
                          mod=MOD_GUN, gun_sayisi=2,
                          yeni_dosya_kontrol_aktif=True)
        # Bugün P1'i çalıştır
        YedekTemizlikYonetici(p1, depo).gunluk_otomatik_calistir(bugun=date.today())
        assert p1.son_calisma_tarihi == date.today().isoformat()
        assert p2.son_calisma_tarihi == ""
        # P2 hâlâ çalıştırılabilir olmalı
        s2 = YedekTemizlikYonetici(p2, depo).gunluk_otomatik_calistir(bugun=date.today())
        assert s2 is not None and s2["silinen_sayi"] > 0
    print("✓ test_16_iki_profil_son_tarih_bagimsiz")


# ---------------------------------------------------------------------------
def main():
    testler = [
        test_1_gun_modu_basit,
        test_2_guvenlik_yeni_dosya_yok,
        test_3_guvenlik_kapali_hepsi_silinir,
        test_4_adet_modu,
        test_5_adet_modu_dosya_az,
        test_6_uzanti_filtresi,
        test_7_klasor_yok,
        test_8_gunluk_otomatik_idempotent,
        test_9_log_yazimi,
        test_10_alt_klasor_dokunulmaz,
        test_11_iki_profil_iki_kural,
        test_12_pasif_profil_atlanir,
        test_13_eski_format_migration,
        test_14_global_otomatik_kapali_hepsini_atla,
        test_15_profil_yonetimi,
        test_16_iki_profil_son_tarih_bagimsiz,
    ]
    hata = 0
    for t in testler:
        try:
            t()
        except AssertionError as e:
            print(f"✗ {t.__name__}: {e}")
            hata += 1
        except Exception as e:
            print(f"✗ {t.__name__}: BEKLENMEDIK {type(e).__name__}: {e}")
            hata += 1
    print(f"\n{len(testler) - hata}/{len(testler)} test geçti")
    return hata


if __name__ == "__main__":
    raise SystemExit(main())
