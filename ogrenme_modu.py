# -*- coding: utf-8 -*-
"""
Öğrenme Modu

Reçeteleri teker teker açar, ilaç satırlarını gezer.
Mesajlı ilaçlarda durur, mesajı okur ve kullanıcıya gösterir.
Kullanıcı ile birlikte kural implementasyonu yapılır.

Akış:
1. Reçeteyi aç
2. Renkli reçete kontrolü (yeşil/kırmızı ise listede var mı?)
3. İlaç satırlarını gez:
   a. Rapor kodu var mı? → Doz kontrolü
   b. Mesaj var mı? → Dur, mesajı oku, kullanıcıya göster
4. Kullanıcı karar verir: Kural Ekle / AI'ya Bırak / Atla
5. Sonraki reçeteye geç
"""

import time
import json
import logging
import threading
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Öğrenme modu kayıt dosyası
OGRENME_KAYIT_DOSYA = Path(__file__).parent / "ogrenme_modu_kayitlar.json"


class OgrenmeModuKayit:
    """Öğrenme modunda toplanan ilaç mesajlarını ve kararları kaydeder."""

    def __init__(self):
        self.kayitlar = []
        self.ai_ya_birakilanlar = []
        self._dosyadan_yukle()

    def _dosyadan_yukle(self):
        """Mevcut kayıtları dosyadan yükle"""
        try:
            if OGRENME_KAYIT_DOSYA.exists():
                with open(OGRENME_KAYIT_DOSYA, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.kayitlar = data.get('kayitlar', [])
                    self.ai_ya_birakilanlar = data.get('ai_ya_birakilanlar', [])
                    logger.info(f"Öğrenme kayıtları yüklendi: {len(self.kayitlar)} kayıt")
        except Exception as e:
            logger.warning(f"Öğrenme kayıt yükleme hatası: {e}")

    def kaydet(self):
        """Kayıtları dosyaya yaz"""
        try:
            data = {
                'kayitlar': self.kayitlar,
                'ai_ya_birakilanlar': self.ai_ya_birakilanlar,
                'son_guncelleme': datetime.now().isoformat(),
                'toplam_kayit': len(self.kayitlar),
                'toplam_ai': len(self.ai_ya_birakilanlar)
            }
            with open(OGRENME_KAYIT_DOSYA, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Öğrenme kayıt yazma hatası: {e}")

    def kayit_ekle(self, ilac_bilgi, karar, notlar=""):
        """
        Yeni kayıt ekle.

        Args:
            ilac_bilgi: dict - ilac_adi, etkin_madde, mesaj_metni, sut_maddesi vb.
            karar: str - "kural_eklendi", "ai_ya_birakildi", "atlandi"
            notlar: str - Ek notlar
        """
        kayit = {
            'tarih': datetime.now().isoformat(),
            'ilac_adi': ilac_bilgi.get('ilac_adi', '?'),
            'etkin_madde': ilac_bilgi.get('etkin_madde', '?'),
            'sut_maddesi': ilac_bilgi.get('sut_maddesi', '?'),
            'mesaj_metni': ilac_bilgi.get('mesaj_metni', ''),
            'rapor_kodu': ilac_bilgi.get('rapor_kodu', ''),
            'recete_no': ilac_bilgi.get('recete_no', ''),
            'karar': karar,
            'notlar': notlar
        }
        self.kayitlar.append(kayit)

        if karar == "ai_ya_birakildi":
            self.ai_ya_birakilanlar.append(kayit)

        self.kaydet()
        return kayit


def ogrenme_modu_reçete_isle(bot, recete_sira_no, grup="", session_logger=None,
                              stop_check=None, onceden_okunan_recete_no=None,
                              renkli_kontrol=None, kullanici_callback=None):
    """
    Öğrenme modunda tek bir reçeteyi işle.

    Her ilaç satırını gezer, mesajlı olanlarda durur ve
    kullanıcıya gösterir.

    Args:
        bot: BotanikBot instance
        recete_sira_no: Reçete sıra numarası
        grup: Grup bilgisi
        session_logger: SessionLogger
        stop_check: Durdurma kontrolü
        onceden_okunan_recete_no: Önceden okunan reçete no
        renkli_kontrol: RenkliReceteKontrol instance
        kullanici_callback: Fonksiyon - mesajlı ilaçta çağrılır
            callback(ilac_bilgi) -> str ("devam", "ai_ya_birak", "atla", "dur")

    Returns:
        dict: {
            'basari': bool,
            'recete_no': str,
            'toplam_ilac': int,
            'mesajli_ilac_sayisi': int,
            'raporlu_ilac_sayisi': int,
            'doz_asimi_sayisi': int,
            'islenen_ilaclar': list,
            'renkli_recete_durumu': str,
        }
    """
    from botanik_bot import (
        recete_turu_oku, ilac_tablosu_satir_sayisi_oku,
        ilac_satiri_ilac_adi_oku, ilac_satiri_msj_oku,
        ilac_satiri_rapor_kodu_oku, ilac_satiri_checkbox_sec,
        ilac_bilgi_butonuna_tikla, ilac_bilgi_etkin_madde_oku,
        ilac_bilgi_sgk_kodu_oku, ilac_mesaj_basligi_oku,
        ilac_mesaj_basligina_tikla, ilac_bilgi_penceresi_mesaj_oku,
        ilac_bilgi_penceresi_kapat, ilac_bilgi_penceresi_raporlu_doz_oku,
        ilac_bilgi_ayaktan_doz_oku, _doz_karsilastir,
        rapor_butonuna_tikla, rapor_tedavi_semasi_oku,
        rapor_tani_bilgileri_oku, rapor_aciklamalari_oku, rapor_geri_don,
    )
    from recete_kontrol.sut_kontrolleri import sut_kategorisi_tespit_et

    rapor = {
        'basari': False,
        'recete_no': None,
        'recete_turu': None,
        'toplam_ilac': 0,
        'mesajli_ilac_sayisi': 0,
        'raporlu_ilac_sayisi': 0,
        'doz_asimi_sayisi': 0,
        'islenen_ilaclar': [],
        'renkli_recete_durumu': None,
    }

    def should_stop():
        return stop_check and stop_check()

    try:
        # ═══════════════════════════════════════════
        # 1. Reçete numarasını oku
        # ═══════════════════════════════════════════
        medula_recete_no = onceden_okunan_recete_no
        if not medula_recete_no:
            hizli_sonuc = bot.recete_sayfasi_hizli_tarama(max_deneme=2, bekleme_suresi=0.15)
            if hizli_sonuc:
                medula_recete_no = hizli_sonuc.get('recete_no')
            else:
                birlesik_sonuc = bot.recete_telefon_kontrol_birlesik(max_deneme=2, bekleme_suresi=0.2)
                medula_recete_no = birlesik_sonuc.get('recete_no')

        if not medula_recete_no:
            logger.warning(f"Öğrenme: Reçete {recete_sira_no} numara okunamadı")
            return rapor

        rapor['recete_no'] = medula_recete_no
        logger.info(f"\n{'═'*60}")
        logger.info(f"ÖĞRENME MODU | Reçete {recete_sira_no} | No: {medula_recete_no}")
        logger.info(f"{'═'*60}")

        # ═══════════════════════════════════════════
        # 2. Reçete türünü oku
        # ═══════════════════════════════════════════
        recete_turu = recete_turu_oku(bot) or "Normal"
        rapor['recete_turu'] = recete_turu
        logger.info(f"  Reçete türü: {recete_turu}")

        # ═══════════════════════════════════════════
        # 3. Renkli reçete kontrolü
        # ═══════════════════════════════════════════
        if renkli_kontrol and recete_turu.lower() in ["yeşil", "yesil", "kırmızı", "kirmizi"]:
            sorun_var, mesaj = renkli_kontrol.kontrol_et(medula_recete_no, recete_turu, grup)
            rapor['renkli_recete_durumu'] = mesaj
            if sorun_var:
                logger.warning(f"  RENKLI REÇETE: {mesaj}")
                # Kullanıcıya bildir
                if kullanici_callback:
                    kullanici_callback({
                        'tip': 'renkli_recete_uyari',
                        'recete_no': medula_recete_no,
                        'recete_turu': recete_turu,
                        'mesaj': mesaj
                    })
            else:
                logger.info(f"  Renkli reçete: {mesaj}")

        if should_stop():
            return rapor

        # ═══════════════════════════════════════════
        # 4. İlaç satırlarını gez
        # ═══════════════════════════════════════════
        satir_sayisi = ilac_tablosu_satir_sayisi_oku(bot)
        rapor['toplam_ilac'] = satir_sayisi

        if satir_sayisi == 0:
            logger.warning("  İlaç tablosunda satır bulunamadı")
            rapor['basari'] = True
            return rapor

        logger.info(f"  İlaç sayısı: {satir_sayisi}")

        for satir_idx in range(satir_sayisi):
            if should_stop():
                break

            ilac_bilgi = {
                'satir': satir_idx,
                'recete_no': medula_recete_no,
                'recete_turu': recete_turu,
            }

            # ─── 4a. Temel bilgileri oku ───
            ilac_adi = ilac_satiri_ilac_adi_oku(bot, satir_idx)
            msj = ilac_satiri_msj_oku(bot, satir_idx)
            rapor_kodu = ilac_satiri_rapor_kodu_oku(bot, satir_idx)

            ilac_bilgi['ilac_adi'] = ilac_adi
            ilac_bilgi['msj'] = msj
            ilac_bilgi['rapor_kodu'] = rapor_kodu
            ilac_bilgi['raporlu'] = bool(rapor_kodu)

            if rapor_kodu:
                rapor['raporlu_ilac_sayisi'] += 1
            if msj and msj.lower() == "var":
                rapor['mesajli_ilac_sayisi'] += 1

            logger.info(f"\n  ── Satır {satir_idx}: {ilac_adi or '?'} | Rapor: {rapor_kodu or '-'} | Msj: {msj or '-'}")

            # Raporsuz VE mesajsız → atla
            if not rapor_kodu and (not msj or msj.lower() != "var"):
                logger.debug(f"    Raporsuz ve mesajsız, atlanıyor")
                rapor['islenen_ilaclar'].append(ilac_bilgi)
                continue

            # ─── 4b. Detaylı bilgi al (checkbox seç + İlaç Bilgi aç) ───
            if not ilac_satiri_checkbox_sec(bot, satir_idx, sec=True):
                logger.warning(f"    Checkbox seçilemedi")
                rapor['islenen_ilaclar'].append(ilac_bilgi)
                continue

            time.sleep(0.2)

            if not ilac_bilgi_butonuna_tikla(bot):
                logger.warning(f"    İlaç Bilgi butonu tıklanamadı")
                ilac_satiri_checkbox_sec(bot, satir_idx, sec=False)
                rapor['islenen_ilaclar'].append(ilac_bilgi)
                continue

            time.sleep(0.5)

            try:
                # Etkin madde
                etkin_madde = ilac_bilgi_etkin_madde_oku(bot)
                ilac_bilgi['etkin_madde'] = etkin_madde
                if etkin_madde:
                    logger.info(f"    Etkin madde: {etkin_madde}")

                # SGK kodu
                sgk_kodu = ilac_bilgi_sgk_kodu_oku(bot)
                ilac_bilgi['sgk_kodu'] = sgk_kodu

                # Mesaj başlığı (SUT maddesi)
                mesaj_basligi = ilac_mesaj_basligi_oku(bot, mesaj_index=0)
                if mesaj_basligi:
                    ilac_bilgi['mesaj_basligi'] = mesaj_basligi.get('baslik')
                    ilac_bilgi['sut_maddesi'] = mesaj_basligi.get('sut_maddesi')
                    logger.info(f"    SUT maddesi: {ilac_bilgi.get('sut_maddesi')}")

                    # Mesaj metnini yükle
                    ilac_mesaj_basligina_tikla(bot, mesaj_index=0)
                    time.sleep(0.3)

                # Mesaj metni
                mesaj_metni = ilac_bilgi_penceresi_mesaj_oku(bot)
                ilac_bilgi['mesaj_metni'] = mesaj_metni

                # ─── 4c. Raporlu ilaç → Doz kontrolü ───
                if rapor_kodu:
                    raporlu_doz = ilac_bilgi_penceresi_raporlu_doz_oku(bot)
                    ilac_bilgi['raporlu_doz'] = raporlu_doz
                    if raporlu_doz:
                        logger.info(f"    Raporlu doz: {raporlu_doz['periyot']} {raporlu_doz['birim']} {raporlu_doz['carpan']} x {raporlu_doz['doz']}")

                    ayaktan_doz = ilac_bilgi_ayaktan_doz_oku(bot)
                    ilac_bilgi['ayaktan_doz'] = ayaktan_doz

                    if raporlu_doz and ayaktan_doz:
                        try:
                            doz_sonuc = _doz_karsilastir(ayaktan_doz, raporlu_doz)
                            ilac_bilgi['doz_uygun'] = doz_sonuc['uygun']
                            ilac_bilgi['doz_aciklama'] = doz_sonuc['aciklama']
                            if not doz_sonuc['uygun']:
                                rapor['doz_asimi_sayisi'] += 1
                                logger.warning(f"    DOZ AŞIMI: {doz_sonuc['aciklama']}")
                            else:
                                logger.info(f"    Doz uygun: {doz_sonuc['aciklama']}")
                        except Exception:
                            pass

                # ─── 4d. SUT kategorisi kontrolü ───
                sut_kategori = sut_kategorisi_tespit_et(ilac_bilgi)
                ilac_bilgi['sut_kategori'] = sut_kategori

                if sut_kategori:
                    logger.info(f"    SUT kategorisi: {sut_kategori}")

                    # Rapor sayfasına git ve bilgileri oku
                    ilac_bilgi_penceresi_kapat(bot)
                    time.sleep(0.3)

                    if rapor_butonuna_tikla(bot):
                        time.sleep(1)
                        aciklamalar = rapor_aciklamalari_oku(bot)
                        tani_bilgileri = rapor_tani_bilgileri_oku(bot)
                        tedavi_semasi = rapor_tedavi_semasi_oku(bot)

                        ilac_bilgi['rapor_aciklamalari'] = aciklamalar
                        ilac_bilgi['rapor_tani_bilgileri'] = tani_bilgileri
                        ilac_bilgi['rapor_tedavi_semasi'] = tedavi_semasi

                        if aciklamalar:
                            logger.info(f"    Rapor açıklamaları: {len(aciklamalar)} adet")

                        rapor_geri_don(bot)
                        time.sleep(0.5)

                        # SUT kontrolünü rapor bilgileriyle yap
                        from recete_kontrol.sut_kontrolleri import sut_kontrol_yap
                        # Açıklamaları mesaj_metni'ne ekle
                        if aciklamalar:
                            mevcut = ilac_bilgi.get('mesaj_metni') or ''
                            ilac_bilgi['mesaj_metni'] = f"{mevcut} [RAPOR: {' | '.join(aciklamalar)}]"

                        sut_sonuc = sut_kontrol_yap(ilac_bilgi)
                        if sut_sonuc:
                            ilac_bilgi['sut_kontrol'] = {
                                'sonuc': sut_sonuc['kontrol_raporu'].sonuc.value,
                                'mesaj': sut_sonuc['kontrol_raporu'].mesaj,
                                'uyari': sut_sonuc['kontrol_raporu'].uyari,
                            }
                            logger.info(f"    SUT Kontrol: {sut_sonuc['kontrol_raporu'].sonuc.value}")

                    # İlaç Bilgi penceresini tekrar aç (mesajı göstermek için)
                    # (checkbox hala seçili olmalı)
                    ilac_bilgi_butonuna_tikla(bot)
                    time.sleep(0.5)

                # ─── 4e. Mesajlı ilaç → KULLANICIYA GÖSTER ───
                if msj and msj.lower() == "var":
                    logger.info(f"    MESAJLI İLAÇ - Kullanıcı kararı bekleniyor...")

                    if kullanici_callback:
                        ilac_bilgi['tip'] = 'mesajli_ilac'
                        karar = kullanici_callback(ilac_bilgi)

                        logger.info(f"    Kullanıcı kararı: {karar}")
                        ilac_bilgi['karar'] = karar

                        if karar == "dur":
                            # Pencereyi kapat, checkbox kaldır
                            ilac_bilgi_penceresi_kapat(bot)
                            time.sleep(0.2)
                            ilac_satiri_checkbox_sec(bot, satir_idx, sec=False)
                            rapor['islenen_ilaclar'].append(ilac_bilgi)
                            break  # Döngüden çık
                    else:
                        ilac_bilgi['karar'] = 'callback_yok'

            finally:
                # Pencereyi kapat ve checkbox'ı kaldır
                ilac_bilgi_penceresi_kapat(bot)
                time.sleep(0.2)
                ilac_satiri_checkbox_sec(bot, satir_idx, sec=False)

            rapor['islenen_ilaclar'].append(ilac_bilgi)
            time.sleep(0.2)

        rapor['basari'] = True
        return rapor

    except Exception as e:
        logger.error(f"Öğrenme modu reçete işleme hatası: {e}")
        rapor['hata'] = str(e)
        return rapor


def ogrenme_modu_popup_goster(root, ilac_bilgi):
    """
    Tkinter popup ile mesajlı ilacı kullanıcıya göster.
    Kullanıcı karar verene kadar bekler (modal dialog).

    Args:
        root: Tkinter root penceresi
        ilac_bilgi: dict - ilac_adi, mesaj_metni, etkin_madde vb.

    Returns:
        str: "devam", "ai_ya_birak", "atla", "dur"
    """
    import tkinter as tk

    karar = {"sonuc": None}

    def _karar_ver(secim):
        karar["sonuc"] = secim
        pencere.destroy()

    pencere = tk.Toplevel(root)
    pencere.title("Öğrenme Modu - İlaç Mesajı")
    pencere.geometry("700x550")
    pencere.transient(root)
    pencere.grab_set()
    pencere.configure(bg="#2b2b2b")

    # Başlık
    ilac_adi = ilac_bilgi.get('ilac_adi', '?')
    etkin_madde = ilac_bilgi.get('etkin_madde', '?')
    sut_maddesi = ilac_bilgi.get('sut_maddesi', '')
    rapor_kodu = ilac_bilgi.get('rapor_kodu', '')

    baslik_text = f"{ilac_adi}"
    if etkin_madde and etkin_madde != '?':
        baslik_text += f"\n({etkin_madde})"

    tk.Label(pencere, text=baslik_text, font=("Segoe UI", 14, "bold"),
             fg="#00ff88", bg="#2b2b2b", justify="center").pack(pady=(10, 5))

    # Bilgi satırı
    bilgi_parts = []
    if sut_maddesi:
        bilgi_parts.append(f"SUT: {sut_maddesi}")
    if rapor_kodu:
        bilgi_parts.append(f"Rapor: {rapor_kodu}")

    sut_kategori = ilac_bilgi.get('sut_kategori')
    if sut_kategori:
        bilgi_parts.append(f"Kategori: {sut_kategori}")

    if bilgi_parts:
        tk.Label(pencere, text=" | ".join(bilgi_parts), font=("Segoe UI", 10),
                 fg="#aaaaaa", bg="#2b2b2b").pack(pady=(0, 5))

    # Doz bilgisi
    doz_uygun = ilac_bilgi.get('doz_uygun')
    if doz_uygun is not None:
        doz_renk = "#00ff00" if doz_uygun else "#ff4444"
        doz_text = f"Doz: {'UYGUN' if doz_uygun else 'AŞIM!'} - {ilac_bilgi.get('doz_aciklama', '')}"
        tk.Label(pencere, text=doz_text, font=("Segoe UI", 10, "bold"),
                 fg=doz_renk, bg="#2b2b2b").pack(pady=(0, 5))

    # SUT kontrol sonucu
    sut_kontrol = ilac_bilgi.get('sut_kontrol')
    if sut_kontrol:
        sut_renk = "#00ff00" if sut_kontrol['sonuc'] == 'uygun' else "#ffaa00"
        tk.Label(pencere, text=f"SUT: {sut_kontrol['mesaj']}", font=("Segoe UI", 9),
                 fg=sut_renk, bg="#2b2b2b", wraplength=650).pack(pady=(0, 5))

    # Mesaj metni
    tk.Label(pencere, text="İlaç Mesajı:", font=("Segoe UI", 10, "bold"),
             fg="#ffffff", bg="#2b2b2b", anchor="w").pack(fill="x", padx=15, pady=(5, 2))

    mesaj_frame = tk.Frame(pencere, bg="#1e1e1e", bd=1, relief="sunken")
    mesaj_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

    mesaj_text = tk.Text(mesaj_frame, wrap="word", font=("Consolas", 10),
                         bg="#1e1e1e", fg="#e0e0e0", insertbackground="#ffffff",
                         relief="flat", padx=10, pady=10)
    mesaj_text.pack(fill="both", expand=True)

    mesaj_metni = ilac_bilgi.get('mesaj_metni', 'Mesaj okunamadı')
    mesaj_text.insert("1.0", mesaj_metni or "Mesaj okunamadı")
    mesaj_text.config(state="disabled")

    # Rapor açıklamaları
    aciklamalar = ilac_bilgi.get('rapor_aciklamalari', [])
    if aciklamalar:
        tk.Label(pencere, text="Rapor Açıklamaları:", font=("Segoe UI", 9, "bold"),
                 fg="#ffaa00", bg="#2b2b2b", anchor="w").pack(fill="x", padx=15, pady=(0, 2))
        for aciklama in aciklamalar[:3]:  # İlk 3
            tk.Label(pencere, text=f"  • {aciklama[:100]}", font=("Segoe UI", 8),
                     fg="#cccccc", bg="#2b2b2b", anchor="w", wraplength=650).pack(fill="x", padx=15)

    # Butonlar
    btn_frame = tk.Frame(pencere, bg="#2b2b2b")
    btn_frame.pack(fill="x", padx=15, pady=(5, 15))

    btn_style = {"font": ("Segoe UI", 11, "bold"), "width": 15, "height": 2, "bd": 0, "cursor": "hand2"}

    tk.Button(btn_frame, text="Devam Et", bg="#28a745", fg="white",
              command=lambda: _karar_ver("devam"), **btn_style).pack(side="left", padx=5)

    tk.Button(btn_frame, text="AI'ya Bırak", bg="#fd7e14", fg="white",
              command=lambda: _karar_ver("ai_ya_birak"), **btn_style).pack(side="left", padx=5)

    tk.Button(btn_frame, text="Atla", bg="#6c757d", fg="white",
              command=lambda: _karar_ver("atla"), **btn_style).pack(side="left", padx=5)

    tk.Button(btn_frame, text="Durdur", bg="#dc3545", fg="white",
              command=lambda: _karar_ver("dur"), **btn_style).pack(side="right", padx=5)

    # Pencere ortala
    pencere.update_idletasks()
    w = pencere.winfo_width()
    h = pencere.winfo_height()
    x = (pencere.winfo_screenwidth() // 2) - (w // 2)
    y = (pencere.winfo_screenheight() // 2) - (h // 2)
    pencere.geometry(f"+{x}+{y}")

    # Modal bekle
    pencere.wait_window()

    return karar["sonuc"] or "atla"


def ogrenme_modu_thread_safe_callback(root, ilac_bilgi):
    """
    Worker thread'den GUI thread'e güvenli geçiş yapan callback.
    Threading.Event ile senkronizasyon sağlar.

    Args:
        root: Tkinter root penceresi
        ilac_bilgi: dict

    Returns:
        str: Kullanıcı kararı
    """
    karar = {"sonuc": None}
    event = threading.Event()

    def _gui_thread_popup():
        sonuc = ogrenme_modu_popup_goster(root, ilac_bilgi)
        karar["sonuc"] = sonuc
        event.set()

    # GUI thread'de popup göster
    root.after(0, _gui_thread_popup)

    # Worker thread bekle
    event.wait(timeout=300)  # Max 5 dakika

    return karar["sonuc"] or "atla"
