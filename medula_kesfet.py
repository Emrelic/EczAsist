# -*- coding: utf-8 -*-
"""
Medula Sayfa Keşif Scripti
Tüm sayfaların element haritasını çıkarır ve JSON dosyasına kaydeder.

Keşfedilecek sayfalar:
1. Ana sayfa (Duyurular)
2. Reçete Listesi → Sorgula → Reçete tablosu
3. Reçete açma (C grubu / A grubu)
4. İlaç Bilgi sayfası
5. Rapor sayfası
6. İlaç Geçmişi sayfası
"""

import time
import json
import os
import sys
import pyautogui
from datetime import datetime

# Proje dizini
PROJE_DIZINI = os.path.dirname(os.path.abspath(__file__))
KESFET_DOSYASI = os.path.join(PROJE_DIZINI, "medula_element_haritasi.json")

# Import
sys.path.insert(0, PROJE_DIZINI)
import importlib
import recete_rapor_kontrol_gui as rr
importlib.reload(rr)
from recete_rapor_kontrol_gui import MedulaBaglanti, MEDULA_IDS


def elementleri_topla(main_window, filtre_y_min=0, filtre_y_max=9999):
    """Sayfadaki tüm elementleri topla"""
    elementler = []
    for elem in main_window.descendants():
        try:
            aid = elem.element_info.automation_id or ""
            ct = elem.element_info.control_type or ""
            txt = elem.window_text() or ""
            r = elem.rectangle()

            if not aid and not txt.strip():
                continue
            if r.top < filtre_y_min or r.top > filtre_y_max:
                continue

            elementler.append({
                "aid": aid,
                "ct": ct,
                "txt": txt.strip()[:120],
                "x": r.left, "y": r.top,
                "w": r.right - r.left, "h": r.bottom - r.top,
            })
        except:
            pass
    return elementler


def butonlari_topla(main_window, prefix=""):
    """Sadece butonları topla"""
    butonlar = []
    for elem in main_window.descendants(control_type="Button"):
        try:
            aid = elem.element_info.automation_id or ""
            txt = elem.window_text() or ""
            if prefix and not aid.startswith(prefix):
                continue
            if aid or txt.strip():
                r = elem.rectangle()
                butonlar.append({
                    "aid": aid, "txt": txt.strip()[:60],
                    "x": r.left, "y": r.top,
                })
        except:
            pass
    return butonlar


def form_alanlarini_topla(main_window, prefix="form1:"):
    """form1: ile başlayan tüm elementleri topla"""
    alanlar = []
    for elem in main_window.descendants():
        try:
            aid = elem.element_info.automation_id or ""
            if not aid.startswith(prefix):
                continue
            if "menu" in aid.lower():
                continue
            ct = elem.element_info.control_type or ""
            txt = elem.window_text() or ""
            r = elem.rectangle()
            alanlar.append({
                "aid": aid, "ct": ct, "txt": txt.strip()[:120],
                "x": r.left, "y": r.top,
            })
        except:
            pass
    return alanlar


def oturum_hazirla(m):
    """Oturumu hazırla - düşmüşse yenile"""
    if m.oturum_aktif_mi():
        return True
    print("  Oturum düşmüş, yenileniyor...")
    for deneme in range(4):
        for e in m.main_window.descendants(control_type="Button"):
            try:
                if e.element_info.automation_id == "btnMedulayaGirisYap":
                    e.click_input()
                    break
            except:
                pass
        time.sleep(6)
        if m.oturum_aktif_mi():
            print("  Oturum yenilendi!")
            return True
    print("  Oturum yenilenemedi!")
    return False


def main():
    import subprocess
    subprocess.run(["taskkill", "/F", "/IM", "BotanikMedula.exe"],
                   capture_output=True, timeout=10)
    time.sleep(3)

    harita = {
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sayfalar": {}
    }

    m = MedulaBaglanti(log_callback=lambda msg, tag="info": print(f"  [{tag}] {msg}"))

    # ====== MEDULA AÇ ======
    print("=" * 50)
    print("MEDULA AÇILIYOR...")
    print("=" * 50)
    basarili = m.medula_ac_ve_baglan()
    if not basarili:
        print("HATA: Medula açılamadı!")
        return
    time.sleep(5)

    # Oturum kontrolü - gerekirse Giriş butonuna bas
    for deneme in range(6):
        if m.oturum_aktif_mi():
            print(f"  Oturum aktif! (deneme {deneme+1})")
            break
        print(f"  Oturum aktif değil, Giriş butonuna basılıyor ({deneme+1}/6)...")
        for e in m.main_window.descendants(control_type="Button"):
            try:
                if e.element_info.automation_id == "btnMedulayaGirisYap":
                    e.click_input()
                    break
            except:
                pass
        time.sleep(8)
    else:
        print("HATA: Oturum aktif edilemedi!")
        return

    # Keepalive durdur (sayfa bozmasın)
    m.keepalive_durdur()

    # ====== 1. ANA SAYFA ======
    print("\n" + "=" * 50)
    print("1. ANA SAYFA (Duyurular)")
    print("=" * 50)

    sol_menu = []
    for elem in m.main_window.descendants(control_type="Button"):
        try:
            aid = elem.element_info.automation_id or ""
            txt = elem.window_text() or ""
            if "menuHtml" in aid:
                sol_menu.append({"aid": aid, "txt": txt.strip()[:60]})
        except:
            pass

    toolbar = butonlari_topla(m.main_window, prefix="btn")
    toolbar += butonlari_topla(m.main_window, prefix="simple")

    harita["sayfalar"]["ana_sayfa"] = {
        "sol_menu": sol_menu,
        "toolbar_butonlar": toolbar,
    }
    print(f"  Sol menü: {len(sol_menu)} item")
    print(f"  Toolbar: {len(toolbar)} buton")

    # ====== 2. REÇETE LİSTESİ ======
    print("\n" + "=" * 50)
    print("2. REÇETE LİSTESİ SAYFASI")
    print("=" * 50)

    m.recete_listesine_git()
    time.sleep(5)

    # Sorgula butonunu bekle (sayfa yüklenene kadar)
    sorgula_bulundu = False
    for bekle in range(15):
        for e in m.main_window.descendants():
            try:
                if e.element_info.automation_id == "form1:buttonSonlandirilmamisReceteler":
                    sorgula_bulundu = True
                    break
            except:
                pass
        if sorgula_bulundu:
            print(f"  Sorgula butonu bulundu ({bekle+1}s)")
            break
        time.sleep(1)

    if not sorgula_bulundu:
        print("  Sorgula butonu bulunamadı, oturum yenileniyor...")
        oturum_hazirla(m)
        time.sleep(3)
        m.recete_listesine_git()
        time.sleep(5)

    rl_elementler = elementleri_topla(m.main_window, filtre_y_min=200, filtre_y_max=800)
    rl_butonlar = [e for e in rl_elementler if e["ct"] == "Button" and e["aid"]]
    rl_sekmeler = [e for e in rl_elementler if e["ct"] == "DataItem" and
                   e["txt"] in ["A", "B", "C Sıralı", "C Kan", "GKKKOY", "Yurtdışı"]]

    harita["sayfalar"]["recete_listesi"] = {
        "butonlar": rl_butonlar,
        "sekmeler": rl_sekmeler,
        "tum_elementler_sayisi": len(rl_elementler),
    }
    print(f"  Butonlar: {len(rl_butonlar)}")
    print(f"  Sekmeler: {[s['txt'] for s in rl_sekmeler]}")

    # Sorgula
    m.sorgula()

    receteler = m.recete_listesi_oku()
    if not receteler:
        time.sleep(3)
        receteler = m.recete_listesi_oku()
    print(f"  Reçete sayısı: {len(receteler)}")
    harita["sayfalar"]["recete_listesi"]["recete_sayisi"] = len(receteler)
    harita["sayfalar"]["recete_listesi"]["recete_ornekleri"] = receteler[:5]

    # Sorgulama sonrası sekmeler
    sekme_sonrasi = []
    for elem in m.main_window.descendants(control_type="DataItem"):
        try:
            txt = elem.window_text()
            if txt and txt.strip() in ["A", "B", "GKKKOY"]:
                r = elem.rectangle()
                sekme_sonrasi.append({"txt": txt.strip(), "x": r.left, "y": r.top})
        except:
            pass
    harita["sayfalar"]["recete_listesi"]["sekmeler_sonrasi"] = sekme_sonrasi

    pyautogui.screenshot(os.path.join(PROJE_DIZINI, "kesfet_recete_listesi.png"))

    if not receteler:
        print("  UYARI: Reçete bulunamadı, devam edilemiyor!")
        with open(KESFET_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(harita, f, indent=2, ensure_ascii=False)
        return

    # ====== 3. REÇETE SAYFASI ======
    # Birden fazla reçete dene - bazıları yüklenemeyebilir
    acilan_recete = None
    for recete_no in receteler[:15]:
        print(f"\n{'=' * 50}")
        print(f"3. REÇETE SAYFASI: {recete_no}")
        print("=" * 50)

        m.receteye_tikla(recete_no)
        time.sleep(4)

        # f:buttonIlacBilgiGorme var mı kontrol et
        sayfa_ok = False
        for e in m.main_window.descendants():
            try:
                if e.element_info.automation_id == "f:buttonIlacBilgiGorme":
                    sayfa_ok = True
                    break
            except:
                pass

        if sayfa_ok:
            # İlaç tablosunun yüklenmesi için ekstra bekle
            time.sleep(3)

            # İlaç tablosunu dene (box32 kontrolü)
            ilaclar_test = m.ilac_tablosu_oku()
            if ilaclar_test:
                print(f"  Reçete sayfası yüklendi ({len(ilaclar_test)} ilaç): {recete_no}")
                acilan_recete = recete_no
                break
            else:
                print(f"  Sayfa yüklendi ama ilaç okunamadı: {recete_no}")
                # Sonraki Reçete butonuyla devam et (daha hızlı)
                sonraki_ok = m._element_bul_ve_tikla("f:buttonSonraki")
                if sonraki_ok:
                    time.sleep(4)
                    continue
                else:
                    m.geri_don()
                    time.sleep(2)
                    continue
        else:
            print(f"  Reçete sayfası yüklenemedi: {recete_no} - sonrakini deniyorum...")
            m.geri_don()
            time.sleep(2)
            # Geri dönemezse menüden git
            if not any(e.element_info.automation_id == "form1:buttonSonlandirilmamisReceteler"
                       for e in m.main_window.descendants()
                       if hasattr(e.element_info, 'automation_id') and e.element_info.automation_id):
                m.recete_listesine_git()
                time.sleep(4)
                m.sorgula()
                time.sleep(3)

    if not acilan_recete:
        print("  UYARI: Hiçbir reçete açılamadı!")
        with open(KESFET_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(harita, f, indent=2, ensure_ascii=False)
        return

    # f: ile başlayan butonlar
    f_butonlar = butonlari_topla(m.main_window, prefix="f:")
    print(f"  f: butonlar: {len(f_butonlar)}")
    for b in f_butonlar:
        print(f"    {b['aid']} = \"{b['txt']}\"")

    # tbl elementleri
    tbl_elementler = []
    for elem in m.main_window.descendants():
        try:
            aid = elem.element_info.automation_id or ""
            if "tbl" in aid:
                ct = elem.element_info.control_type or ""
                txt = elem.window_text() or ""
                tbl_elementler.append({
                    "aid": aid, "ct": ct, "txt": txt.strip()[:80]
                })
        except:
            pass
    print(f"  tbl elementler: {len(tbl_elementler)}")

    # İlaç tablosu
    ilaclar = m.ilac_tablosu_oku()
    print(f"  İlaç: {len(ilaclar)}")

    if not ilaclar and tbl_elementler:
        # Debug: DataItem'ları göster (ilaç tablosu alanı)
        print("  DEBUG - İlaç tablosu boş, DataItem'lar:")
        for e in m.main_window.descendants(control_type="DataItem"):
            try:
                txt = e.window_text()
                r = e.rectangle()
                if txt and txt.strip() and r.top > 600 and r.top < 950:
                    print(f"    y={r.top} x={r.left} \"{txt.strip()[:80]}\"")
            except:
                pass

    # form alanları
    recete_form = form_alanlarini_topla(m.main_window, prefix="f:")
    print(f"  f: form alanları: {len(recete_form)}")

    harita["sayfalar"]["recete_sayfasi"] = {
        "recete_no": receteler[0],
        "f_butonlar": f_butonlar,
        "tbl_elementler_sayisi": len(tbl_elementler),
        "tbl_ornekleri": tbl_elementler[:30],
        "ilac_sayisi": len(ilaclar),
        "ilaclar": [{k: v for k, v in i.items() if v} for i in ilaclar],
        "form_alanlari": recete_form[:50],
    }

    pyautogui.screenshot(os.path.join(PROJE_DIZINI, "kesfet_recete_sayfasi.png"))

    # ====== 4. İLAÇ BİLGİ SAYFASI ======
    if ilaclar:
        print("\n" + "=" * 50)
        print("4. İLAÇ BİLGİ SAYFASI")
        print("=" * 50)

        m._element_bul_ve_tikla("f:tbl1:0:checkbox7")
        time.sleep(0.5)
        m._element_bul_ve_tikla("f:buttonIlacBilgiGorme")
        time.sleep(5)

        ib_form1 = form_alanlarini_topla(m.main_window, prefix="form1:")
        ib_butonlar = [e for e in ib_form1 if e["ct"] == "Button"]
        ib_degerler = [e for e in ib_form1 if e["ct"] in ["Text", "Edit", "DataItem"] and e["txt"]]

        print(f"  form1 butonlar: {len(ib_butonlar)}")
        for b in ib_butonlar:
            print(f"    {b['aid']} = \"{b['txt']}\"")
        print(f"  form1 değerler: {len(ib_degerler)}")
        for d in ib_degerler[:20]:
            print(f"    {d['ct']} {d['aid']} = \"{d['txt']}\"")

        harita["sayfalar"]["ilac_bilgi"] = {
            "butonlar": ib_butonlar,
            "degerler": ib_degerler[:30],
        }

        pyautogui.screenshot(os.path.join(PROJE_DIZINI, "kesfet_ilac_bilgi.png"))

        # Kapat - birden fazla yöntem dene
        kapandi = m._element_bul_ve_tikla("form1:buttonKapat")
        if not kapandi:
            kapandi = m._element_bul_ve_tikla("form1:buttonGeriDon")
        if not kapandi:
            kapandi = m._element_bul_ve_tikla("f:buttonGeriDon")
        print(f"  İlaç Bilgi kapatıldı: {kapandi}")
        time.sleep(2)

        # ====== 5. RAPOR SAYFASI ======
        print("\n" + "=" * 50)
        print("5. RAPOR SAYFASI")
        print("=" * 50)

        # İlk raporlu ilacı bul
        raporlu_idx = None
        for i, ilac in enumerate(ilaclar):
            if ilac.get("rapor_kodu"):
                raporlu_idx = i
                break

        if raporlu_idx is not None:
            # Checkbox seç
            cb_id = f"f:tbl1:{raporlu_idx}:checkbox7"
            m._element_bul_ve_tikla(cb_id)
            time.sleep(0.5)
            m._element_bul_ve_tikla("f:buttonRaporGoruntule")
            time.sleep(5)

            rapor_form1 = form_alanlarini_topla(m.main_window, prefix="form1:")
            rapor_butonlar = [e for e in rapor_form1 if e["ct"] == "Button"]
            rapor_degerler = [e for e in rapor_form1 if e["ct"] in ["Text", "Edit", "DataItem"] and e["txt"]]

            print(f"  form1 butonlar: {len(rapor_butonlar)}")
            for b in rapor_butonlar:
                print(f"    {b['aid']} = \"{b['txt']}\"")
            print(f"  form1 değerler: {len(rapor_degerler)}")
            for d in rapor_degerler[:20]:
                print(f"    {d['ct']} {d['aid']} = \"{d['txt']}\"")

            harita["sayfalar"]["rapor_sayfasi"] = {
                "ilac_satir": raporlu_idx,
                "butonlar": rapor_butonlar,
                "degerler": rapor_degerler[:30],
            }

            pyautogui.screenshot(os.path.join(PROJE_DIZINI, "kesfet_rapor.png"))

            # Geri dön
            m._element_bul_ve_tikla("form1:buttonGeriDon")
            time.sleep(2)
        else:
            print("  Raporlu ilaç bulunamadı")

        # ====== 6. İLAÇ GEÇMİŞİ ======
        print("\n" + "=" * 50)
        print("6. İLAÇ GEÇMİŞİ SAYFASI")
        print("=" * 50)

        m._element_bul_ve_tikla("f:buttonIlacListesi")
        time.sleep(5)

        ig_form1 = form_alanlarini_topla(m.main_window, prefix="form1:")
        ig_butonlar = [e for e in ig_form1 if e["ct"] == "Button"]
        ig_degerler = [e for e in ig_form1 if e["ct"] in ["Text", "Edit", "DataItem"] and e["txt"]]

        print(f"  form1 butonlar: {len(ig_butonlar)}")
        for b in ig_butonlar:
            print(f"    {b['aid']} = \"{b['txt']}\"")
        print(f"  form1 değerler: {len(ig_degerler)}")

        harita["sayfalar"]["ilac_gecmisi"] = {
            "butonlar": ig_butonlar,
            "degerler": ig_degerler[:30],
        }

        pyautogui.screenshot(os.path.join(PROJE_DIZINI, "kesfet_ilac_gecmisi.png"))

        # Geri dön
        m._element_bul_ve_tikla("form1:buttonGeriDon")
        time.sleep(2)

    # ====== KAYDET ======
    print("\n" + "=" * 50)
    print("HARITA KAYDEDİLİYOR...")
    print("=" * 50)

    with open(KESFET_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(harita, f, indent=2, ensure_ascii=False)
    print(f"Kaydedildi: {KESFET_DOSYASI}")

    # Beep
    import winsound
    for _ in range(5):
        winsound.Beep(1000, 300)
        time.sleep(0.1)
    print("\n=== KEŞİF TAMAMLANDI ===")


if __name__ == "__main__":
    main()
