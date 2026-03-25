# -*- coding: utf-8 -*-
"""
Reçete Kontrol Motoru

İlaçları SUT kurallarına göre algoritmik olarak kontrol eder.
Veritabanındaki etkin_madde_kurallari tablosunu kullanır.
Yeni ilaçlar öğrenildikçe veritabanına eklenir.

Kontrol sırası:
1. Etkin madde → veritabanında kural var mı?
2. Rapor gerekli mi? → Rapor kodu var mı kontrol
3. Doz kontrolü → Reçete dozu ≤ Rapor dozu
4. Birlikte kullanım → Aynı reçetede yasaklı ilaç var mı?
5. Msj kontrolü → Mesaj varsa ne diyor?
"""

import sqlite3
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kontrol_kurallari.db")


class KontrolSonuc:
    """Tek bir ilaç için kontrol sonucu"""
    UYGUN = "uygun"
    UYGUN_DEGIL = "uygun_degil"
    KONTROL_GEREKLI = "kontrol_gerekli"
    BILINMIYOR = "bilinmiyor"

    def __init__(self, ilac_adi, etkin_madde=""):
        self.ilac_adi = ilac_adi
        self.etkin_madde = etkin_madde
        self.durum = self.BILINMIYOR
        self.rapor_durumu = ""       # "raporlu", "raporsuz", "raporsuz_verilebilir"
        self.doz_durumu = ""         # "uygun", "asim", "kontrol_edilemedi"
        self.birlikte_kullanim = ""  # "uygun", "yasak_var"
        self.msj_durumu = ""         # "yok", "var_kontrol_edildi", "var_sorunlu"
        self.uyarilar = []           # Uyarı mesajları listesi
        self.detay = {}              # Ek bilgiler

    def __repr__(self):
        return f"<KontrolSonuc {self.ilac_adi}: {self.durum} | Rapor:{self.rapor_durumu} Doz:{self.doz_durumu}>"


class ReceteKontrolMotoru:
    """
    Reçeteleri SUT kurallarına göre algoritmik kontrol eden motor.
    Veritabanındaki kurallara bakarak karar verir.
    Yeni ilaçlar öğrenildikçe veritabanına eklenir.
    """

    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda msg, tag="info": logger.info(msg))
        self._db_conn = None

    def _db(self):
        """Veritabanı bağlantısı (lazy)"""
        if self._db_conn is None:
            self._db_conn = sqlite3.connect(DB_PATH)
            self._db_conn.row_factory = sqlite3.Row
        return self._db_conn

    def kapat(self):
        """Veritabanı bağlantısını kapat"""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None

    # === KURAL SORGULAMA ===

    def kural_bul(self, etkin_madde):
        """
        Etkin maddeye göre veritabanından kural bul.
        Returns: dict veya None
        """
        try:
            c = self._db().cursor()
            # Tam eşleşme
            c.execute("SELECT * FROM etkin_madde_kurallari WHERE etkin_madde = ? AND aktif = 1",
                      (etkin_madde.upper(),))
            row = c.fetchone()
            if row:
                return dict(row)

            # Kısmi eşleşme (etkin madde adı içinde arama)
            c.execute("SELECT * FROM etkin_madde_kurallari WHERE ? LIKE '%' || etkin_madde || '%' AND aktif = 1",
                      (etkin_madde.upper(),))
            row = c.fetchone()
            if row:
                return dict(row)

            return None
        except Exception as e:
            logger.error(f"Kural sorgulama hatası: {e}")
            return None

    def kural_bul_sgk_kodu(self, sgk_kodu):
        """SGK kodu ile kural bul"""
        try:
            c = self._db().cursor()
            c.execute("SELECT * FROM etkin_madde_kurallari WHERE sgk_kodu = ? AND aktif = 1",
                      (sgk_kodu,))
            row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"SGK kodu sorgulama hatası: {e}")
            return None

    # === TEK İLAÇ KONTROLÜ ===

    def ilac_kontrol(self, ilac_bilgi, reçetedeki_diger_ilaclar=None):
        """
        Tek bir ilacı kontrol et.

        Args:
            ilac_bilgi: dict - ilac_tablosu_oku() çıktısındaki bir ilaç
                {ilac_adi, rapor_kodu, msj, doz, tutar, fark, ...}
            reçetedeki_diger_ilaclar: list[dict] - birlikte kullanım kontrolü için

        Returns:
            KontrolSonuc
        """
        sonuc = KontrolSonuc(ilac_bilgi.get("ilac_adi", "Bilinmeyen"))

        rapor_kodu = ilac_bilgi.get("rapor_kodu", "")
        msj = ilac_bilgi.get("msj", "")
        doz = ilac_bilgi.get("doz", "")

        # 1. Etkin madde tespiti - İlaç Bilgi'den gelecek veya veritabanından tahmin
        # Şimdilik ilac_adi'ndan arama yapalım
        kural = None

        # SGK etkin madde bilgisi varsa (İlaç Bilgi'den okunmuş)
        etkin_madde = ilac_bilgi.get("etkin_madde", "")
        sgk_kodu = ilac_bilgi.get("sgk_kodu", "")

        if sgk_kodu:
            kural = self.kural_bul_sgk_kodu(sgk_kodu)
        if not kural and etkin_madde:
            kural = self.kural_bul(etkin_madde)

        if not kural:
            # Veritabanında kural yok - bilinmiyor
            sonuc.durum = KontrolSonuc.BILINMIYOR
            sonuc.uyarilar.append(f"Etkin madde kuralı bulunamadı: {etkin_madde or ilac_bilgi.get('ilac_adi', '')}")
            return sonuc

        sonuc.etkin_madde = kural["etkin_madde"]
        kontrol_tipi = kural["kontrol_tipi"]

        # 2. Rapor kontrolü
        if kural["rapor_gerekli"]:
            if rapor_kodu:
                sonuc.rapor_durumu = "raporlu"
            else:
                sonuc.rapor_durumu = "raporsuz"
                sonuc.durum = KontrolSonuc.UYGUN_DEGIL
                sonuc.uyarilar.append(f"RAPOR GEREKLİ! SUT {kural['sut_maddesi']}: {kural['etkin_madde']} raporlu yazılmalı")
                return sonuc
        else:
            sonuc.rapor_durumu = "raporsuz_verilebilir"

        # 3. Doz kontrolü
        if doz and kural.get("raporlu_maks_doz"):
            doz_sonuc = self._doz_karsilastir(doz, kural["raporlu_maks_doz"])
            sonuc.doz_durumu = doz_sonuc
            if doz_sonuc == "asim":
                sonuc.uyarilar.append(f"DOZ AŞIMI! Reçete: {doz} > Maks: {kural['raporlu_maks_doz']}")
        else:
            sonuc.doz_durumu = "kontrol_edilemedi"

        # 4. Birlikte kullanım kontrolü
        if kural.get("birlikte_yasaklar") and reçetedeki_diger_ilaclar:
            yasaklar = json.loads(kural["birlikte_yasaklar"]) if isinstance(kural["birlikte_yasaklar"], str) else kural["birlikte_yasaklar"]
            if yasaklar:
                cakisma = self._birlikte_kullanim_kontrol(
                    kural["etkin_madde"], yasaklar, reçetedeki_diger_ilaclar
                )
                if cakisma:
                    sonuc.birlikte_kullanim = "yasak_var"
                    sonuc.uyarilar.append(f"BİRLİKTE KULLANIM YASAĞI: {', '.join(cakisma)}")
                else:
                    sonuc.birlikte_kullanim = "uygun"

        # 5. Msj kontrolü
        if msj == "var":
            sonuc.msj_durumu = "var_kontrol_gerekli"
            sonuc.uyarilar.append(f"Mesaj var - İlaç Bilgi kontrol edilmeli")
        else:
            sonuc.msj_durumu = "yok"

        # Genel durum belirleme
        if sonuc.uyarilar:
            if any("RAPOR GEREKLİ" in u or "DOZ AŞIMI" in u or "YASAĞI" in u for u in sonuc.uyarilar):
                sonuc.durum = KontrolSonuc.UYGUN_DEGIL
            else:
                sonuc.durum = KontrolSonuc.KONTROL_GEREKLI
        else:
            sonuc.durum = KontrolSonuc.UYGUN

        return sonuc

    # === REÇETE KONTROLÜ ===

    def recete_kontrol(self, ilaclar):
        """
        Reçetedeki tüm ilaçları kontrol et.

        Args:
            ilaclar: list[dict] - ilac_tablosu_oku() çıktısı

        Returns:
            list[KontrolSonuc]
        """
        sonuclar = []
        for ilac in ilaclar:
            sonuc = self.ilac_kontrol(ilac, reçetedeki_diger_ilaclar=ilaclar)
            sonuclar.append(sonuc)
            self.log(
                f"  {ilac['ilac_adi']}: {sonuc.durum}" +
                (f" - {', '.join(sonuc.uyarilar)}" if sonuc.uyarilar else ""),
                "success" if sonuc.durum == KontrolSonuc.UYGUN else
                "error" if sonuc.durum == KontrolSonuc.UYGUN_DEGIL else
                "warning"
            )
        return sonuclar

    # === YARDIMCI FONKSİYONLAR ===

    def _doz_karsilastir(self, recete_doz_str, maks_doz_str):
        """
        Doz karşılaştırması yap.
        Formatlar: "Günde 1 x 1.0" veya "1 Günde 1 x 1,00 - Adet"
        Returns: "uygun", "asim", "kontrol_edilemedi"
        """
        try:
            recete = self._doz_parse(recete_doz_str)
            maks = self._doz_parse(maks_doz_str)

            if not recete or not maks:
                return "kontrol_edilemedi"

            # Günlük toplam doz karşılaştır
            recete_gunluk = recete["carpan"] * recete["miktar"]
            maks_gunluk = maks["carpan"] * maks["miktar"]

            if recete_gunluk > maks_gunluk:
                return "asim"
            return "uygun"
        except Exception:
            return "kontrol_edilemedi"

    def _doz_parse(self, doz_str):
        """
        Doz string'ini parse et.
        "1 Günde 4 x 2,00 - Adet" → {"periyot": 1, "birim": "Günde", "carpan": 4, "miktar": 2.0}
        "Günde 1 x 1.0" → {"periyot": 1, "birim": "Günde", "carpan": 1, "miktar": 1.0}
        """
        import re
        if not doz_str:
            return None

        try:
            # "1 Günde 4 x 2,00 - Adet" formatı
            m = re.search(r'(\d+)\s*(Günde|Haftada)\s*(\d+)\s*x\s*([\d,\.]+)', doz_str)
            if m:
                return {
                    "periyot": int(m.group(1)),
                    "birim": m.group(2),
                    "carpan": int(m.group(3)),
                    "miktar": float(m.group(4).replace(",", ".")),
                }

            # "Günde 1 x 1.0" formatı
            m = re.search(r'(Günde|Haftada)\s*(\d+)\s*x\s*([\d,\.]+)', doz_str)
            if m:
                return {
                    "periyot": 1,
                    "birim": m.group(1),
                    "carpan": int(m.group(2)),
                    "miktar": float(m.group(3).replace(",", ".")),
                }
        except Exception:
            pass

        return None

    def _birlikte_kullanim_kontrol(self, etkin_madde, yasakli_gruplar, diger_ilaclar):
        """
        Birlikte kullanım yasaklarını kontrol et.
        Returns: list[str] - çakışan ilaç adları (boşsa sorun yok)
        """
        cakisanlar = []

        # Her yasaklı grup için diğer ilaçları kontrol et
        for diger in diger_ilaclar:
            diger_adi = diger.get("ilac_adi", "").upper()
            diger_etkin = diger.get("etkin_madde", "").upper()

            # Kendisi ile karşılaştırma
            if etkin_madde.upper() in diger_etkin or diger_etkin in etkin_madde.upper():
                continue

            for grup in yasakli_gruplar:
                grup_upper = grup.upper()
                # İlaç adında veya etkin maddede yasaklı grup var mı?
                if grup_upper in diger_adi or grup_upper in diger_etkin:
                    cakisanlar.append(f"{diger.get('ilac_adi', '?')} ({grup})")

        return cakisanlar

    # === YENİ KURAL ÖĞRENME ===

    def yeni_kural_ekle(self, etkin_madde, sgk_kodu="", sut_maddesi="", rapor_kodu="",
                         rapor_gerekli=0, kontrol_tipi="bilinmiyor", aciklama=""):
        """Yeni bir etkin madde kuralı öğren ve veritabanına kaydet"""
        try:
            c = self._db().cursor()
            # Daha önce var mı?
            c.execute("SELECT id FROM etkin_madde_kurallari WHERE etkin_madde = ?",
                      (etkin_madde.upper(),))
            if c.fetchone():
                self.log(f"Kural zaten var: {etkin_madde}", "info")
                return

            c.execute('''INSERT INTO etkin_madde_kurallari
                (etkin_madde, sgk_kodu, sut_maddesi, rapor_kodu, rapor_gerekli,
                 kontrol_tipi, aciklama, olusturma_tarihi, aktif)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                (etkin_madde.upper(), sgk_kodu, sut_maddesi, rapor_kodu,
                 rapor_gerekli, kontrol_tipi, aciklama, datetime.now().isoformat()))
            self._db().commit()
            self.log(f"Yeni kural öğrenildi: {etkin_madde} ({kontrol_tipi})", "success")
        except Exception as e:
            self.log(f"Kural ekleme hatası: {e}", "error")
