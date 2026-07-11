# -*- coding: utf-8 -*-
"""Medula — tek hasta için İLAÇ GEÇMİŞİ + RAPOR GEÇMİŞİ birleşik toplayıcı.

AI Kontrol paketinin "Medula'dan da topla" seçeneği bu modülü kullanır:
GUI'de seçili satırın hastası (tek TC) için Medula ekranlarında gezinip
    1) Rapor geçmişi  → medula_rapor_tarayici.hasta_raporlarini_tara_ve_kaydet
       (bitmiş raporlar dahil; yerel SQLite cache'e yazar, oradan okunur)
    2) İlaç geçmişi   → medula_ilac_gecmisi.ilac_gecmisini_oku
       (çapraz-reçete SGK geçmişi, tüm sayfalar)
verilerini döndürür.

⚠️ KIRMIZI ÇİZGİ: SADECE OKUMA + navigasyon. Medula'da hiçbir veri
değiştirilmez; f:t18'e yalnız sorgu TC'si yazılır.

⚠️ İŞ AKIŞI KURALI (kullanıcı, 2026-07-05): Bir reçete sayfasında bir TC
sorgulandıktan sonra AYNI sayfada ikinci bir TC sorgulanamaz. Bu yüzden
rapor akışının kullandığı reçete sayfası ilaç akışı için YENİDEN
KULLANILMAZ — `f:buttonSonraki` ile taze reçeteye geçilir.

Eşzamanlılık: Medula tek pencere / tek state — tüm toplama işlemleri
modül kilidi ile serileştirilir.

Ana giriş: ``medula_hasta_verisi_topla(tc)`` → Dict.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

StatusCb = Optional[Callable[[str], None]]

# Medula tek pencere — toplamalar serileştirilir (pyodbc segfault dersi:
# paylaşılan COM/pencere state'ine iki thread'den dokunulmaz).
_MEDULA_KILIT = threading.RLock()

ID_BUTTON_SONRAKI = 'f:buttonSonraki'


def _bildir(msg: str, cb: StatusCb) -> None:
    logger.info(msg)
    if cb:
        try:
            cb(msg)
        except Exception:
            pass


def _tc_maskele(tc: str) -> str:
    return (tc[:3] + '****' + tc[-1]) if tc and len(tc) == 11 else str(tc)


def _recete_detayina_getir(cb: StatusCb = None, deneme_sayisi: int = 2) -> bool:
    """Medula'yı hangi durumda olursa olsun REÇETE DETAY ekranına getir.

    Rapor tarayıcının state-machine'inin hafif kopyası: kapalıysa exe+login,
    oturum düşmüşse Giriş butonu, ana sayfadaysa Reçete Listesi → ilk reçete.
    İlaç/End.Dışı akışları rapor akışından ÖNCE koştuğunda gerekir.

    Sayfa geçişleri zamanlamaya duyarlı ("B grubu TD bulunamadı" gibi geçici
    hatalar, canlı 2026-07-05) → adımlar `deneme_sayisi` kez baştan denenir.
    """
    from recete_kontrol.medula_rapor_tarayici import (
        MedulaDurum, _medula_durum_tespit, medula_baslat_ve_giris,
        recete_listesi_b_grubu_ac, ilk_recete_satirini_ac, _bekle,
        _medula_hwnd_bul, _pencereyi_one_getir, _medulaya_3_kez_giris_dene)

    for deneme in range(1, max(1, deneme_sayisi) + 1):
        if deneme > 1:
            _bildir(f'Reçete detayına getirme — deneme {deneme}/{deneme_sayisi}',
                    cb)
            _bekle(2.0)

        hwnd = _medula_hwnd_bul()
        if hwnd:
            try:
                _pencereyi_one_getir(hwnd, cb=cb)
            except Exception:
                pass
        durum = _medula_durum_tespit(cb=cb)

        if durum in (MedulaDurum.KAPALI, MedulaDurum.LOGIN_EKRANI,
                     MedulaDurum.LOGIN_DUSTU, MedulaDurum.BILINMEYEN):
            _bildir('Medula kapalı/login — başlatılıyor', cb)
            if not medula_baslat_ve_giris(cb=cb):
                continue
            durum = _medula_durum_tespit(cb=cb)

        if durum == MedulaDurum.ANA_SAYFA_LOGIN_GEREK:
            h = _medula_hwnd_bul()
            if not (h and _medulaya_3_kez_giris_dene(h, cb=cb)):
                continue
            durum = _medula_durum_tespit(cb=cb)

        if durum == MedulaDurum.ANA_SAYFA:
            if not recete_listesi_b_grubu_ac(cb=cb):
                continue   # geçici yüklenme hatası — baştan dene
            durum = MedulaDurum.RECETE_LISTESI

        if durum == MedulaDurum.RECETE_LISTESI:
            if ilk_recete_satirini_ac(cb=cb):
                return True
            continue

        if durum in (MedulaDurum.RECETE_DETAY, MedulaDurum.RAPOR_LISTESI):
            return True

    return False


def _recete_detaya_don(cb: StatusCb = None) -> bool:
    """Alt ekranlardan (rapor listesi / ilaç listesi vb.) Geri Dön'lerle
    REÇETE DETAY ekranına dön (f:t18 görünene kadar, max 3 seviye).
    Sonraki'ye BASMAZ — aynı reçetede kalınır (aynı hasta akışı)."""
    from recete_kontrol.medula_rapor_tarayici import (
        _medula_hwnd_bul, _html_doc, _bekle, ID_TC_INPUT, ID_BUTTON_GERI_DON)
    from recete_kontrol.medula_ilac_gecmisi import _elem_tikla

    hwnd = _medula_hwnd_bul()
    if not hwnd:
        _bildir('HATA: Medula penceresi yok (reçete detaya dönüş)', cb)
        return False
    d = _html_doc(hwnd)
    if d is None:
        return False
    for _ in range(4):
        try:
            if d.getElementById(ID_TC_INPUT) is not None:
                return True
        except Exception:
            pass
        if not _elem_tikla(d, ID_BUTTON_GERI_DON, buton=True):
            return False
        _bekle(1.2)
        d = _html_doc(hwnd)
        if d is None:
            return False
    _bildir('HATA: reçete detaya dönülemedi', cb)
    return False


def _taze_receteye_gec(cb: StatusCb = None) -> bool:
    """Reçete detay ekranındayken `Sonraki` ile TAZE reçeteye geç.

    SADECE hasta başlangıcında kullanılır (yeni hasta = yeni reçete
    kuralı). Aynı hastanın İlaç→Rapor→End.Dışı adımları arasında
    KULLANILMAZ — o adımlar aynı reçetede döner.
    """
    from recete_kontrol.medula_rapor_tarayici import (
        _medula_hwnd_bul, _html_doc, _bekle, ID_TC_INPUT)
    from recete_kontrol.medula_ilac_gecmisi import _elem_tikla

    if not _recete_detaya_don(cb):
        return False
    hwnd = _medula_hwnd_bul()
    d = _html_doc(hwnd)
    if d is None:
        return False

    try:
        onceki_tc = (d.getElementById(ID_TC_INPUT).getAttribute('value')
                     or '').strip()
    except Exception:
        onceki_tc = ''

    _bildir('Sonraki reçeteye geçiliyor (taze TC sorgu sayfası)', cb)
    if not _elem_tikla(d, ID_BUTTON_SONRAKI, buton=True):
        _bildir(f'HATA: {ID_BUTTON_SONRAKI} tıklanamadı', cb)
        return False
    _bekle(1.5)
    for _ in range(20):
        d = _html_doc(hwnd)
        try:
            if d is not None:
                yeni = (d.getElementById(ID_TC_INPUT).getAttribute('value')
                        or '').strip()
                if yeni and yeni != onceki_tc:
                    return True
        except Exception:
            pass
        _bekle(0.5)
    # TC değişmedi (liste sonundaki tek reçete olabilir) — yine de devam;
    # f:t18 görünüyorsa sayfa reçete detaydır.
    try:
        return d is not None and d.getElementById(ID_TC_INPUT) is not None
    except Exception:
        return False


def medula_hasta_verisi_topla(
        tc: str,
        cb: StatusCb = None,
        rapor_detayli: bool = True,
        rapor_kodu_filtre: Optional[str] = None,
        ilac_topla: bool = True,
        rapor_topla: bool = True,
        end_disi_topla: bool = True,
        rapor_eos_skip: bool = False,
        rapor_yerel_skip: bool = False) -> Dict[str, Any]:
    """Tek hasta için Medula ilaç + rapor geçmişini topla.

    Args:
        tc: 11 haneli hasta TC (ham — paketleme aşamasında anonimleşir).
        cb: durum callback'i (GUI ilerleme).
        rapor_detayli: True → her rapora girilip detay_metni okunur (yavaş);
            False → sadece liste metadata'sı.
        rapor_kodu_filtre: '07.02' gibi — sadece bu kodla başlayan raporlar
            detaylı okunur (None = hepsi).
        ilac_topla / rapor_topla / end_disi_topla: alt akışları aç/kapa.

    Returns:
        {
          "ilac_gecmisi":  [ {recete_no, ilac_adi, atc_id, ...,
                              kaynak='medula'}, ... ],
          "rapor_gecmisi": [ {rapor_takip_no, rapor_kodu, tani, icd_kodu,
                              baslangic/bitis, detay_metni,
                              kaynak='medula'}, ... ],
          "endikasyon_disi": [ {basvuru_no, basvuru_tarihi, onay_tarihi,
                                durumu, saglik_tesisi, basvuru_nedeni,
                                detay_metni, kaynak='medula'}, ... ],
          "hatalar":       [ str, ... ]     # boş = sorunsuz
        }
    Kısmi başarı mümkündür (örn. rapor toplandı, ilaç toplanamadı) —
    hatalar listesi doluysa eksik taraf paket uyarısına yansıtılmalı.
    """
    sonuc: Dict[str, Any] = {
        'ilac_gecmisi': [], 'rapor_gecmisi': [], 'endikasyon_disi': [],
        'hatalar': []}
    if not tc or not (len(tc) == 11 and str(tc).isdigit()):
        sonuc['hatalar'].append(f'Geçersiz TC: {_tc_maskele(str(tc))}')
        return sonuc
    tc = str(tc)

    with _MEDULA_KILIT:
        # Akış sırası (kullanıcı kararı 2026-07-05):
        #   1) İLAÇ geçmişi → 2) RAPOR geçmişi (her rapora tek tek girerek)
        #   → 3) ENDİKASYON DIŞI izinler.
        # Her adım kendi TAZE reçetesinde çalışır (aynı sayfada ikinci TC
        # sorgulanamaz kuralı) — f:buttonSonraki ile ilerlenir.

        # ── 1) İLAÇ GEÇMİŞİ — reçete detaya gel + taze reçete + TC + İlaç ──
        if ilac_topla:
            try:
                from recete_kontrol.medula_ilac_gecmisi import (
                    ilac_gecmisini_oku)
                _bildir(f'═══ 1/3 İLAÇ GEÇMİŞİ ({_tc_maskele(tc)}) ═══', cb)
                if not _recete_detayina_getir(cb):
                    sonuc['hatalar'].append(
                        'İlaç geçmişi: reçete detay ekranına gelinemedi')
                elif not _taze_receteye_gec(cb):
                    sonuc['hatalar'].append(
                        'İlaç geçmişi: taze reçete sayfasına geçilemedi')
                else:
                    kayitlar = ilac_gecmisini_oku(tc, cb=cb, geri_don=True)
                    if kayitlar:
                        sonuc['ilac_gecmisi'] = kayitlar
                    else:
                        # 0 kayıt: hastanın geçmişi gerçekten boş olabilir;
                        # ama navigasyon da başarısız olabilir — uyarı bırak.
                        sonuc['hatalar'].append(
                            'İlaç geçmişi 0 kayıt döndü (hasta geçmişi boş '
                            'olabilir ya da ekran açılamadı — manuel doğrula)')
            except Exception as e:
                logger.exception('Medula ilaç geçmişi hatası')
                sonuc['hatalar'].append(f'İlaç geçmişi: {e}')

        # ── 2) RAPOR GEÇMİŞİ — her rapora tek tek girerek (state-aware) ──
        # Kullanıcı akışı 2026-07-06: İlaç'tan Geri Dön ile dönülen AYNI
        # reçete üzerinden Rapor'a basılır — yeni reçete açılmaz, TC yeniden
        # yazılmaz (tc_yaz aynı değeri görünce atlar).
        if rapor_topla:
            try:
                from recete_kontrol.medula_rapor_tarayici import (
                    hasta_raporlarini_tara_ve_kaydet)
                _bildir(f'═══ 2/3 RAPOR GEÇMİŞİ ({_tc_maskele(tc)}) ═══', cb)
                if ilac_topla:
                    _recete_detaya_don(cb)   # aynı reçete — Sonraki YOK
                # Varsayılan: eos_skip=False + yerel_skip=False → HER rapora
                # her toplamada yeniden girilir (kullanıcı kararı 2026-07-05:
                # "raporlara teker teker girip verileri topla").
                hasta_raporlarini_tara_ve_kaydet(
                    tc,
                    rapor_kodu_filtre=rapor_kodu_filtre,
                    detayli_oku=rapor_detayli,
                    eos_skip=rapor_eos_skip,
                    yerel_skip=rapor_yerel_skip,
                    cb=cb)
            except Exception as e:
                logger.exception('Medula rapor tarama hatası')
                sonuc['hatalar'].append(f'Rapor tarama: {e}')
            # Tarama sonucu ne olursa olsun yerel cache'te birikmiş TÜM
            # raporları oku (önceki oturumlarda toplananlar dahil).
            try:
                from recete_kontrol.hasta_rapor_gecmisi_db import (
                    hasta_raporlarini_oku)
                for r in hasta_raporlarini_oku(tc) or []:
                    sonuc['rapor_gecmisi'].append({
                        'rapor_takip_no': r.rapor_takip_no,
                        'baslangic_tarihi': r.baslangic_tarihi,
                        'bitis_tarihi': r.bitis_tarihi,
                        'rapor_kodu': r.rapor_kodu,
                        'tani': r.tani,
                        'icd_kodu': r.icd_kodu,
                        'rapor_tipi': r.rapor_tipi,
                        'detay_metni': r.detay_metni or '',
                        'kaynak': 'medula',
                    })
                _bildir(f'Medula rapor geçmişi: '
                        f'{len(sonuc["rapor_gecmisi"])} rapor (cache dahil)',
                        cb)
            except Exception as e:
                logger.exception('Rapor cache okuma hatası')
                sonuc['hatalar'].append(f'Rapor cache okuma: {e}')

        # ── 3) ENDİKASYON DIŞI İZİNLER — AYNI reçete + End.Dışı butonu ──
        # Rapor listesinden Geri Dön ile reçete ana ekranına dönülür, aynı
        # reçetede End.Dışı'na basılır (TC yazılı — yeniden yazılmaz).
        # İzni olmayan hastada 0 satır normal — hata sayılmaz.
        if end_disi_topla:
            try:
                from recete_kontrol.medula_endikasyon_disi import (
                    endikasyon_disi_izinleri_oku)
                _bildir(f'═══ 3/3 ENDİKASYON DIŞI ({_tc_maskele(tc)}) ═══', cb)
                hazir = (_recete_detaya_don(cb)
                         if (rapor_topla or ilac_topla)
                         else (_recete_detayina_getir(cb)
                               and _taze_receteye_gec(cb)))
                if not hazir:
                    sonuc['hatalar'].append(
                        'End.Dışı: reçete detay ekranına dönülemedi')
                else:
                    sonuc['endikasyon_disi'] = endikasyon_disi_izinleri_oku(
                        tc, cb=cb, detayli=True, geri_don=True)
            except Exception as e:
                logger.exception('Medula End.Dışı hatası')
                sonuc['hatalar'].append(f'End.Dışı: {e}')

    return sonuc
