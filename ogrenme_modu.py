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
4. Kullanıcı karar verir: Algoritmik Öğren / AI'ya Bırak / Durdur
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
            callback(ilac_bilgi) -> str ("algoritmik_ogren", "yoksay", "ai_ya_birak", "dur")

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
        recete_turu_oku, ilac_tablosu_satir_sayisi_oku, ilac_tablosu_toplu_oku,
        ilac_satiri_ilac_adi_oku, ilac_satiri_msj_oku,
        ilac_satiri_rapor_kodu_oku, ilac_satiri_checkbox_sec,
        ilac_bilgi_butonuna_tikla, ilac_bilgi_etkin_madde_oku,
        ilac_bilgi_sgk_kodu_oku, ilac_mesaj_basligi_oku,
        ilac_mesaj_basligina_tikla, ilac_bilgi_penceresi_mesaj_oku,
        ilac_bilgi_penceresi_kapat, ilac_bilgi_penceresi_raporlu_doz_oku,
        ilac_bilgi_ayaktan_doz_oku, _doz_karsilastir, _tedavi_semasi_parse,
        ilac_satiri_recete_doz_oku, ilac_satiri_eos_rapor_dozu_oku,
        rapor_butonuna_tikla, rapor_tedavi_semasi_oku,
        rapor_tani_bilgileri_oku, rapor_aciklamalari_oku, rapor_geri_don,
    )
    from recete_kontrol.sut_kontrolleri import sut_kategorisi_tespit_et
    from botanik_db import BotanikDB
    from kontrol_kurallari import KontrolKurallari, KontrolRaporu, IlacMesajDurumu

    # Veritabanı bağlantısı (etkin madde sorgusu için)
    db = None
    try:
        db = BotanikDB()
    except Exception as e:
        logger.warning(f"Veritabanı bağlantısı kurulamadı (etkin madde sorgusu devre dışı): {e}")

    # Kural veritabanı
    kural_db = None
    try:
        kural_db = KontrolKurallari()
    except Exception as e:
        logger.warning(f"Kural veritabanı açılamadı: {e}")

    # İlaç mesaj durum cache
    mesaj_cache = None
    try:
        mesaj_cache = IlacMesajDurumu()
    except Exception as e:
        logger.warning(f"İlaç mesaj cache açılamadı: {e}")

    # Kontrol raporu
    kontrol_raporu = None
    try:
        oturum_id_str = session_logger.oturum_id if session_logger and hasattr(session_logger, 'oturum_id') else datetime.now().strftime("%Y%m%d_%H%M%S")
        kontrol_raporu = KontrolRaporu(oturum_id=oturum_id_str)
    except Exception as e:
        logger.warning(f"Kontrol raporu oluşturulamadı: {e}")

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
        # 4. İlaç satırlarını TEK SEFERDE oku (toplu DOM okuma)
        # ═══════════════════════════════════════════
        tum_satirlar = ilac_tablosu_toplu_oku(bot)
        satir_sayisi = len(tum_satirlar)
        rapor['toplam_ilac'] = satir_sayisi

        if satir_sayisi == 0:
            logger.warning("  İlaç tablosunda satır bulunamadı")
            rapor['basari'] = True
            return rapor

        logger.info(f"  İlaç sayısı: {satir_sayisi}")

        # İlaç sayıları hesapla
        for s in tum_satirlar:
            if s['rapor_kodu']:
                rapor['raporlu_ilac_sayisi'] += 1
            if s['msj'] and s['msj'].lower() == "var":
                rapor['mesajli_ilac_sayisi'] += 1

        for satir_idx in range(satir_sayisi):
            if should_stop():
                break

            satir_data = tum_satirlar[satir_idx]
            ilac_adi = satir_data['ilac_adi']
            msj = satir_data['msj']
            rapor_kodu = satir_data['rapor_kodu']

            ilac_bilgi = {
                'satir': satir_idx,
                'recete_no': medula_recete_no,
                'recete_turu': recete_turu,
                'ilac_adi': ilac_adi,
                'msj': msj,
                'rapor_kodu': rapor_kodu,
                'raporlu': bool(rapor_kodu),
            }

            # EOS'tan gelen etkin madde bilgisi (DB'ye gerek kalmayabilir)
            etkin_maddeler = []
            eos_etkin = satir_data.get('eos_etkin_madde')
            if eos_etkin:
                etkin_maddeler = [eos_etkin]
                ilac_bilgi['etkin_madde'] = eos_etkin
                ilac_bilgi['sgk_kodu'] = satir_data.get('eos_sgk_kodu')
            elif db and ilac_adi:
                try:
                    etkin_maddeler = db.etkin_madde_getir_ilac_adiyla(ilac_adi)
                    if etkin_maddeler:
                        ilac_bilgi['etkin_madde_db'] = etkin_maddeler
                except Exception as e:
                    logger.debug(f"    Etkin madde sorgu hatası: {e}")

            logger.info(f"\n  ── Satır {satir_idx}: {ilac_adi or '?'} | Rapor: {rapor_kodu or '-'} | Msj: {msj or '-'} | Etkin: {', '.join(etkin_maddeler) if etkin_maddeler else '?'}")

            # ═══════════════════════════════════════════
            # KARAR AĞACI:
            # 1. Raporsuz + mesajsız → sonraki satıra geç
            # 2. Raporsuz + mesajlı → İlaç Bilgi'ye gir, mesajı öğren (doz kontrolü yok)
            # 3. Raporlu + mesajsız → sadece doz kontrolü (İlaç Bilgi'ye GİRME)
            # 4. Raporlu + mesajlı → İlaç Bilgi'ye gir, mesajı öğren + doz kontrolü
            # ═══════════════════════════════════════════

            mesajli_medula = msj and msj.lower() == "var"
            raporlu = bool(rapor_kodu)

            # ─── MESAJ CACHE KONTROLÜ ───
            # Etkin madde bazlı cache: yok/var/yoksay
            mesajli = mesajli_medula  # Varsayılan: Medula'dan gelen değer
            if mesaj_cache:
                ilac_etkin = ilac_bilgi.get('etkin_madde', '')
                if not ilac_etkin and etkin_maddeler:
                    ilac_etkin = etkin_maddeler[0] if isinstance(etkin_maddeler, list) else etkin_maddeler
                cache_durum = mesaj_cache.durum_sorgula(ilac_etkin) if ilac_etkin else None

                if cache_durum == "yoksay":
                    # Mesaj var ama yoksay → mesajsız gibi davran
                    mesajli = False
                    logger.info(f"    MESAJ YOKSAY (cache): {ilac_etkin}")
                elif cache_durum == "yok":
                    # Cache'de mesaj yok kayıtlı → mesajsız
                    mesajli = False
                elif cache_durum == "var":
                    # Cache'de mesaj var kayıtlı
                    mesajli = True
                elif cache_durum is None and mesajli_medula:
                    # İlk karşılaşma ve Medula'da mesaj var → cache'e "var" yaz
                    if ilac_etkin:
                        mesaj_cache.durum_kaydet(ilac_etkin, "var", ilac_adi=ilac_adi)
                elif cache_durum is None and not mesajli_medula:
                    # İlk karşılaşma ve Medula'da mesaj yok → cache'e "yok" yaz
                    if ilac_etkin:
                        mesaj_cache.durum_kaydet(ilac_etkin, "yok", ilac_adi=ilac_adi)

            # ─── 1. Raporsuz + mesajsız → atla ───
            if not raporlu and not mesajli:
                logger.debug(f"    Raporsuz + mesajsız, atlanıyor")
                rapor['islenen_ilaclar'].append(ilac_bilgi)
                continue

            # ─── 2. Raporlu + mesajsız → sadece doz kontrolü ───
            if raporlu and not mesajli:
                logger.info(f"    Raporlu + mesajsız → doz kontrolü")

                # ÖNCELİK 1: BotanikEOS verisini toplu okumadan al (ek DOM çağrısı yok)
                eos_rapor = None
                if satir_data.get('eos_rapor_dozu'):
                    eos_rapor = {
                        'rapor_dozu': satir_data['eos_rapor_dozu'],
                        'arka_plan': satir_data['eos_arka_plan'],
                        'doz_uygun': satir_data['eos_doz_uygun'],
                        'sgk_etkin_madde': satir_data.get('eos_sgk_etkin_madde'),
                        'sgk_kodu': satir_data.get('eos_sgk_kodu'),
                        'etkin_madde': satir_data.get('eos_etkin_madde'),
                    }

                if eos_rapor and eos_rapor.get('rapor_dozu'):
                    ilac_bilgi['eos_rapor_dozu'] = eos_rapor['rapor_dozu']
                    ilac_bilgi['eos_arka_plan'] = eos_rapor['arka_plan']
                    ilac_bilgi['etkin_madde'] = eos_rapor.get('etkin_madde')
                    ilac_bilgi['sgk_kodu'] = eos_rapor.get('sgk_kodu')

                    if eos_rapor['doz_uygun'] is True:
                        # Yeşil → doz uygun, rapor sayfasına gitmeye gerek yok
                        ilac_bilgi['doz_uygun'] = True
                        ilac_bilgi['doz_aciklama'] = f"{eos_rapor.get('etkin_madde', '?')}: EOS yeşil - doz uygun"
                        logger.info(f"    ✓ EOS YEŞİL → Doz uygun ({eos_rapor.get('sgk_etkin_madde', '?')}) | Rapor: {eos_rapor['rapor_dozu']}")
                        rapor['islenen_ilaclar'].append(ilac_bilgi)
                        continue
                    elif eos_rapor['doz_uygun'] is False:
                        # Kırmızı → doz aşımı
                        ilac_bilgi['doz_uygun'] = False
                        ilac_bilgi['doz_aciklama'] = f"{eos_rapor.get('etkin_madde', '?')}: EOS kırmızı - DOZ AŞIMI"
                        rapor['doz_asimi_sayisi'] += 1
                        logger.warning(f"    ⚠️ EOS KIRMIZI → DOZ AŞIMI ({eos_rapor.get('sgk_etkin_madde', '?')}) | Rapor: {eos_rapor['rapor_dozu']}")
                        rapor['islenen_ilaclar'].append(ilac_bilgi)
                        continue
                    else:
                        # Sarı/belirsiz → ek kontrol gerekebilir, rapor sayfasına git
                        logger.info(f"    ⚠ EOS SARI/BELİRSİZ ({eos_rapor.get('arka_plan')}) → Rapor sayfasına gidiliyor...")

                # ÖNCELİK 2: EOS bilgisi yoksa veya belirsizse, rapor sayfasına git
                recete_doz_str = ilac_satiri_recete_doz_oku(bot, satir_idx)
                ilac_bilgi['recete_doz'] = recete_doz_str
                recete_doz_parsed = _tedavi_semasi_parse(recete_doz_str) if recete_doz_str else None

                if not ilac_satiri_checkbox_sec(bot, satir_idx, sec=True):
                    logger.warning(f"    Checkbox seçilemedi")
                    rapor['islenen_ilaclar'].append(ilac_bilgi)
                    continue

                time.sleep(0.1)

                try:
                    if rapor_butonuna_tikla(bot):
                        time.sleep(0.3)

                        tedavi_semasi = rapor_tedavi_semasi_oku(bot)
                        ilac_bilgi['rapor_tedavi_semasi'] = tedavi_semasi

                        if tedavi_semasi:
                            logger.info(f"    Raporda {len(tedavi_semasi)} etkin madde bulundu:")
                            for ts in tedavi_semasi:
                                logger.info(f"      {ts['sgk_kodu']} | {ts['etkin_madde']} | {ts['tedavi_semasi']}")

                        rapor_geri_don(bot)
                        time.sleep(0.2)

                        if recete_doz_str:
                            logger.info(f"    Reçete dozu: {recete_doz_str}")

                        if recete_doz_parsed and tedavi_semasi:
                            recete_dict = {
                                'periyot': 1,
                                'birim': recete_doz_parsed.get('birim', 'Günde'),
                                'carpan': recete_doz_parsed.get('periyot', 1),
                                'doz': recete_doz_parsed.get('carpan', 1.0),
                            }

                            eslesen_ts = None
                            if etkin_maddeler and len(tedavi_semasi) > 1:
                                for ts in tedavi_semasi:
                                    rapor_etkin = ts.get('etkin_madde', '').upper()
                                    for em in etkin_maddeler:
                                        if em.upper() in rapor_etkin or rapor_etkin in em.upper():
                                            eslesen_ts = ts
                                            logger.info(f"    Etkin madde eşleşmesi: {em} → {rapor_etkin}")
                                            break
                                    if eslesen_ts:
                                        break

                            if not eslesen_ts:
                                for ts in tedavi_semasi:
                                    if ts.get('tedavi_parsed'):
                                        eslesen_ts = ts
                                        break

                            if eslesen_ts:
                                rapor_doz_parsed = eslesen_ts.get('tedavi_parsed')
                                if rapor_doz_parsed:
                                    rapor_dict = {
                                        'periyot': 1,
                                        'birim': rapor_doz_parsed.get('birim', 'Günde'),
                                        'carpan': rapor_doz_parsed.get('periyot', 1),
                                        'doz': rapor_doz_parsed.get('carpan', 1.0),
                                    }
                                    doz_sonuc = _doz_karsilastir(recete_dict, rapor_dict)
                                    ilac_bilgi['doz_uygun'] = doz_sonuc['uygun']
                                    ilac_bilgi['doz_aciklama'] = f"{eslesen_ts['etkin_madde']}: {doz_sonuc['aciklama']}"
                                    ilac_bilgi['etkin_madde'] = eslesen_ts['etkin_madde']

                                    if not doz_sonuc['uygun']:
                                        rapor['doz_asimi_sayisi'] += 1
                                        logger.warning(f"    ⚠️ DOZ AŞIMI ({eslesen_ts['etkin_madde']}): {doz_sonuc['aciklama']}")
                                    else:
                                        logger.info(f"    ✓ Doz uygun ({eslesen_ts['etkin_madde']}): {doz_sonuc['aciklama']}")
                    else:
                        logger.warning(f"    Rapor butonu tıklanamadı")
                finally:
                    ilac_satiri_checkbox_sec(bot, satir_idx, sec=False)

                rapor['islenen_ilaclar'].append(ilac_bilgi)
                time.sleep(0.1)
                continue

            # ─── 3/4. Mesajlı ilaç ───
            # Önce kural veritabanında otomatik kontrol dene
            if kural_db:
                try:
                    # Mesaj metnini henüz okumadık ama kural pattern'i ile
                    # reçetedeki diğer ilaçlara bakarak kontrol yapabiliriz.
                    # Bunun için tum_satirlar'daki etkin madde bilgilerini kullanırız.
                    # Not: Mesaj metnini bilmeden de ilac_adi/etkin_madde bazlı kural arayabiliriz
                    # Ama asıl mesaj metni İlaç Bilgi sayfasında. Şimdilik bilinen kuralları
                    # mesaj_pattern=None ile değil, ilac/etkin_madde bazlı arıyoruz.
                    pass  # Mesaj metni henüz okunmadı, İlaç Bilgi sonrası kontrol edilecek
                except Exception as e:
                    logger.debug(f"    Kural ön-kontrol hatası: {e}")

            # (Raporlu + mesajlı VEYA Raporsuz + mesajlı)
            if raporlu:
                logger.info(f"    Raporlu + mesajlı → İlaç Bilgi açılıyor (mesaj + doz kontrolü)")
            else:
                logger.info(f"    Raporsuz + mesajlı → İlaç Bilgi açılıyor (sadece mesaj öğrenme)")

            # Reçete dozunu oku (sadece raporlu ilaçlar için)
            if raporlu:
                recete_doz = ilac_satiri_recete_doz_oku(bot, satir_idx)
                ilac_bilgi['recete_doz'] = recete_doz

            if not ilac_satiri_checkbox_sec(bot, satir_idx, sec=True):
                logger.warning(f"    Checkbox seçilemedi")
                rapor['islenen_ilaclar'].append(ilac_bilgi)
                continue

            time.sleep(0.1)

            if not ilac_bilgi_butonuna_tikla(bot):
                logger.warning(f"    İlaç Bilgi butonu tıklanamadı")
                ilac_satiri_checkbox_sec(bot, satir_idx, sec=False)
                rapor['islenen_ilaclar'].append(ilac_bilgi)
                continue

            time.sleep(0.3)

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
                    time.sleep(0.15)

                # Mesaj metni
                mesaj_metni = ilac_bilgi_penceresi_mesaj_oku(bot)
                ilac_bilgi['mesaj_metni'] = mesaj_metni

                # Doz kontrolü (sadece raporlu ilaçlar için - İlaç Bilgi sayfasından)
                if raporlu:
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

                # ─── KURAL KONTROLÜ (mesaj okunduktan sonra) ───
                kural_sonuc = None
                if kural_db and mesaj_metni:
                    try:
                        kural_sonuc = kural_db.kural_uygula(
                            mesaj_metni=mesaj_metni,
                            ilac_bilgi=ilac_bilgi,
                            tum_recete_ilaclari=tum_satirlar,
                        )
                    except Exception as e:
                        logger.debug(f"    Kural uygulama hatası: {e}")

                if kural_sonuc:
                    ilac_bilgi['kural_sonuc'] = kural_sonuc
                    ilac_bilgi['mesaj_uygunluk'] = 'uygun' if kural_sonuc['uygun'] else 'uygunsuz'
                    if kural_sonuc['uygun']:
                        logger.info(f"    ✓ KURAL UYGUN (ID={kural_sonuc['kural_id']}): {kural_sonuc['aciklama']}")
                        ilac_bilgi['karar'] = 'kural_gecir'
                        # İlaç Bilgi penceresini kapat ve devam et
                        ilac_bilgi_penceresi_kapat(bot)
                        time.sleep(0.1)
                        ilac_satiri_checkbox_sec(bot, satir_idx, sec=False)
                        rapor['islenen_ilaclar'].append(ilac_bilgi)
                        continue
                    else:
                        logger.warning(f"    ⚠ KURAL UYGUNSUZ (ID={kural_sonuc['kural_id']}): {kural_sonuc['aciklama']}")
                        # Uygunsuzluk bilgisini popup'a da ekle
                        ilac_bilgi['kural_uygunsuz_aciklama'] = kural_sonuc['aciklama']

                # KULLANICIYA GÖSTER (öğrenme modu - kural yoksa veya uygunsuzsa)
                logger.info(f"    MESAJLI İLAÇ - Kullanıcı kararı bekleniyor...")

                if kullanici_callback:
                    ilac_bilgi['tip'] = 'mesajli_ilac'
                    karar = kullanici_callback(ilac_bilgi)

                    logger.info(f"    Kullanıcı kararı: {karar}")
                    ilac_bilgi['karar'] = karar

                    if karar == "dur":
                        ilac_bilgi_penceresi_kapat(bot)
                        time.sleep(0.1)
                        ilac_satiri_checkbox_sec(bot, satir_idx, sec=False)
                        rapor['islenen_ilaclar'].append(ilac_bilgi)
                        break
                    elif karar == "algoritmik_ogren":
                        # Sistem durur, kullanıcı Claude Code'da kuralı öğretir
                        # İlaç bilgilerini loga yaz ki kullanıcı Claude Code'da görsün
                        logger.info(f"\n{'='*60}")
                        logger.info(f"ALGORİTMİK ÖĞRENME MODU AKTİF")
                        logger.info(f"İlaç: {ilac_adi}")
                        logger.info(f"Etkin Madde: {ilac_bilgi.get('etkin_madde', '?')}")
                        logger.info(f"SGK Kodu: {ilac_bilgi.get('sgk_kodu', '?')}")
                        logger.info(f"SUT Maddesi: {ilac_bilgi.get('sut_maddesi', '?')}")
                        logger.info(f"Rapor Kodu: {rapor_kodu}")
                        logger.info(f"Mesaj: {ilac_bilgi.get('mesaj_metni', '?')[:200]}")
                        logger.info(f"{'='*60}")
                        logger.info(f"Kullanıcı Claude Code'da kuralı öğretecek. Sistem bekliyor...")
                        # İlaç Bilgi penceresini kapat, bot duraklar
                        ilac_bilgi_penceresi_kapat(bot)
                        time.sleep(0.1)
                        ilac_satiri_checkbox_sec(bot, satir_idx, sec=False)
                        rapor['islenen_ilaclar'].append(ilac_bilgi)
                        rapor['algoritmik_ogren_bekliyor'] = True
                        rapor['bekleyen_ilac'] = ilac_bilgi
                        break
                    elif karar == "yoksay":
                        # Mesajı yoksay olarak cache'e kaydet
                        ilac_etkin = ilac_bilgi.get('etkin_madde', '')
                        if mesaj_cache and ilac_etkin:
                            mesaj_cache.durum_kaydet(
                                ilac_etkin, "yoksay",
                                ilac_adi=ilac_adi,
                                aciklama="Kullanici tarafindan yoksay olarak isaretlendi"
                            )
                            logger.info(f"    MESAJ YOKSAY kaydedildi: {ilac_etkin}")
                        ilac_bilgi['mesaj_uygunluk'] = 'yoksay'
                else:
                    ilac_bilgi['karar'] = 'callback_yok'

            finally:
                # İlaç Bilgi sayfasından geri dön ve checkbox kaldır
                ilac_bilgi_penceresi_kapat(bot)
                time.sleep(0.1)
                ilac_satiri_checkbox_sec(bot, satir_idx, sec=False)

            rapor['islenen_ilaclar'].append(ilac_bilgi)
            time.sleep(0.1)

        rapor['basari'] = True

        # ═══════════════════════════════════════════
        # KONTROL RAPORU TABLOSUNA KAYDET
        # ═══════════════════════════════════════════
        if kontrol_raporu:
            for ilac in rapor['islenen_ilaclar']:
                try:
                    doz_uygunluk_str = None
                    if ilac.get('doz_uygun') is True:
                        doz_uygunluk_str = "uygun"
                    elif ilac.get('doz_uygun') is False:
                        doz_uygunluk_str = "asim"

                    mesaj_var = bool(ilac.get('msj') and ilac['msj'].lower() == "var")

                    kontrol_raporu.satir_ekle(
                        grup=grup,
                        recete_sira_no=recete_sira_no,
                        sgk_recete_no=medula_recete_no,
                        ilac_ismi=ilac.get('ilac_adi', '?'),
                        etkin_madde=ilac.get('etkin_madde', ''),
                        recete_dozu=ilac.get('recete_doz', ''),
                        rapor_dozu=ilac.get('eos_rapor_dozu') or ilac.get('raporlu_doz_str', ''),
                        doz_uygunluk=doz_uygunluk_str,
                        mesaj_var=mesaj_var,
                        mesaj_metni=ilac.get('mesaj_metni', ''),
                        mesaj_uygunluk=ilac.get('mesaj_uygunluk', ''),
                        rapor_kodu=ilac.get('rapor_kodu', ''),
                        karar=ilac.get('karar', ''),
                    )
                except Exception as e:
                    logger.debug(f"Kontrol raporu kayıt hatası: {e}")

        # ═══════════════════════════════════════════
        # REÇETE ÖZET RAPORU (Log)
        # ═══════════════════════════════════════════
        logger.info(f"\n{'─'*60}")
        logger.info(f"REÇETE ÖZET | No: {medula_recete_no} | Toplam: {rapor['toplam_ilac']} ilaç")
        logger.info(f"  Raporlu: {rapor['raporlu_ilac_sayisi']} | Mesajlı: {rapor['mesajli_ilac_sayisi']} | Doz aşımı: {rapor['doz_asimi_sayisi']}")

        for ilac in rapor['islenen_ilaclar']:
            ilac_adi = ilac.get('ilac_adi', '?')
            etkin = ilac.get('etkin_madde') or ilac.get('etkin_madde_db', ['?'])[0] if ilac.get('etkin_madde_db') else ilac.get('etkin_madde', '')
            doz_durum = ""
            if ilac.get('doz_uygun') is True:
                doz_durum = "✓ DOZ UYGUN"
            elif ilac.get('doz_uygun') is False:
                doz_durum = "⚠ DOZ AŞIMI"

            rapor_kodu = ilac.get('rapor_kodu', '-')
            msj = ilac.get('msj', '-')
            doz_aciklama = ilac.get('doz_aciklama', '')

            mesaj_uygunluk = ilac.get('mesaj_uygunluk', '')
            msj_durum = ""
            if mesaj_uygunluk == 'uygun':
                msj_durum = "✓ MSJ UYGUN"
            elif mesaj_uygunluk == 'uygunsuz':
                msj_durum = "⚠ MSJ UYGUNSUZ"
            karar_str = ilac.get('karar', '')

            if doz_durum or msj_durum:
                logger.info(f"  [{ilac.get('satir')}] {ilac_adi} | Etkin: {etkin} | Rapor: {rapor_kodu} | Msj: {msj} | {doz_durum} {msj_durum} | {doz_aciklama} {karar_str}".strip())
            elif ilac.get('raporlu'):
                logger.info(f"  [{ilac.get('satir')}] {ilac_adi} | Etkin: {etkin} | Rapor: {rapor_kodu} | Msj: {msj}")
            else:
                logger.debug(f"  [{ilac.get('satir')}] {ilac_adi} | Raporsuz | Msj: {msj}")

        logger.info(f"{'─'*60}")

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
        str: "algoritmik_ogren", "yoksay", "ai_ya_birak", "dur"
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

    # Kural uygunsuzluk uyarısı
    kural_uygunsuz = ilac_bilgi.get('kural_uygunsuz_aciklama')
    if kural_uygunsuz:
        tk.Label(pencere, text=f"KURAL UYGUNSUZ: {kural_uygunsuz}",
                 font=("Segoe UI", 10, "bold"), fg="#ff4444", bg="#2b2b2b",
                 wraplength=650).pack(pady=(0, 5))

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

    btn_style = {"font": ("Segoe UI", 10, "bold"), "width": 16, "height": 2, "bd": 0, "cursor": "hand2"}

    tk.Button(btn_frame, text="Algoritmik Ogren", bg="#28a745", fg="white",
              command=lambda: _karar_ver("algoritmik_ogren"), **btn_style).pack(side="left", padx=3)

    tk.Button(btn_frame, text="Mesaji Yoksay", bg="#17a2b8", fg="white",
              command=lambda: _karar_ver("yoksay"), **btn_style).pack(side="left", padx=3)

    tk.Button(btn_frame, text="AI'ya Birak", bg="#fd7e14", fg="white",
              command=lambda: _karar_ver("ai_ya_birak"), **btn_style).pack(side="left", padx=3)

    tk.Button(btn_frame, text="Durdur", bg="#dc3545", fg="white",
              command=lambda: _karar_ver("dur"), **btn_style).pack(side="right", padx=3)

    # Pencere ortala
    pencere.update_idletasks()
    w = pencere.winfo_width()
    h = pencere.winfo_height()
    x = (pencere.winfo_screenwidth() // 2) - (w // 2)
    y = (pencere.winfo_screenheight() // 2) - (h // 2)
    pencere.geometry(f"+{x}+{y}")

    # Modal bekle
    pencere.wait_window()

    return karar["sonuc"] or "dur"


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

    return karar["sonuc"] or "dur"
