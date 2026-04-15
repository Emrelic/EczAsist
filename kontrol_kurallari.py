# -*- coding: utf-8 -*-
"""
Kontrol Kuralları ve Rapor Veritabanı

İlaç mesaj kuralları:
- Kullanıcı Claude Code aracılığıyla kuralları öğretir
- Sistem sonraki seferlerde aynı mesajı otomatik kontrol eder

Kontrol Raporu:
- Her reçetedeki her ilaç satırı için detaylı kayıt tutar
- Grup, reçete no, hasta, ilaç, doz, mesaj uygunluk vb.
"""

import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# İLAÇ GRUP TANIMLARI (SUT kurallarında birlikte kullanım kontrolü)
# ═══════════════════════════════════════════════════════════════

ILAC_GRUPLARI = {
    # ── DİYABET GRUPLARI ──
    "DPP4": {
        "ad": "DPP-4 Antagonistleri",
        "etkin_maddeler": [
            "SITAGLIPTIN", "VILDAGLIPTIN", "SAXAGLIPTIN", "ALOGLIPTIN",
            "LINAGLIPTIN",
        ],
    },
    "SGLT2": {
        "ad": "SGLT2 İnhibitörleri",
        "etkin_maddeler": [
            "EMPAGLIFLOZIN", "DAPAGLIFLOZIN", "CANAGLIFLOZIN", "ERTUGLIFLOZIN",
        ],
    },
    "GLP1": {
        "ad": "GLP-1 Analogları",
        "etkin_maddeler": [
            "LIRAGLUTIDE", "DULAGLUTIDE", "SEMAGLUTIDE", "EXENATIDE",
            "LIXISENATIDE", "TIRZEPATIDE",
        ],
    },
    # ── KOAH / ASTIM GRUPLARI (SUT 4.2.9 / 4.2.24.B) ──
    "LABA": {
        "ad": "Uzun Etkili Beta Agonistler (LABA)",
        "etkin_maddeler": [
            "FORMOTEROL", "SALMETEROL", "INDAKATEROL", "VILANTEROL",
            "OLODATEROL",
        ],
    },
    "LAMA": {
        "ad": "Uzun Etkili Antikolinerjikler (LAMA)",
        "etkin_maddeler": [
            "TIOTROPIUM", "GLIKOPIRONYUM", "UMEKLIDINYUM", "AKLIDINYUM",
        ],
    },
    "IKS": {
        "ad": "İnhale Kortikosteroidler (İKS)",
        "etkin_maddeler": [
            "BUDESONID", "BEKLOMETAZON", "FLUTIKAZON", "MOMETAZON",
            "SIKLESONID",
        ],
    },
    "SABA": {
        "ad": "Kısa Etkili Beta Agonistler (SABA)",
        "etkin_maddeler": [
            "SALBUTAMOL", "TERBUTALIN",
        ],
    },
    "SAMA": {
        "ad": "Kısa Etkili Antikolinerjikler (SAMA)",
        "etkin_maddeler": [
            "IPRATROPIUM",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════
# KOAH İLAÇ TİCARİ İSİM → GRUP EŞLEŞTİRMESİ
# ═══════════════════════════════════════════════════════════════

KOAH_ILAC_GRUPLARI = {
    # LABA mono
    "FORADIL": {"etkin_madde": "FORMOTEROL", "grup": "LABA"},
    "OXIS": {"etkin_madde": "FORMOTEROL", "grup": "LABA"},
    "SEREVENT": {"etkin_madde": "SALMETEROL", "grup": "LABA"},
    "ONBREZ": {"etkin_madde": "INDAKATEROL", "grup": "LABA"},
    # LAMA mono
    "SPIRIVA": {"etkin_madde": "TIOTROPIUM", "grup": "LAMA"},
    "BRALTUS": {"etkin_madde": "TIOTROPIUM", "grup": "LAMA"},
    "TIOBLIS": {"etkin_madde": "TIOTROPIUM", "grup": "LAMA"},
    "SEEBRI": {"etkin_madde": "GLIKOPIRONYUM", "grup": "LAMA"},
    "ENUREV": {"etkin_madde": "GLIKOPIRONYUM", "grup": "LAMA"},
    "BRETARIS": {"etkin_madde": "AKLIDINYUM", "grup": "LAMA"},
    "EKLIRA": {"etkin_madde": "AKLIDINYUM", "grup": "LAMA"},
    # LABA+LAMA kombo
    "TIOFORM": {"etkin_madde": "FORMOTEROL+TIOTROPIUM", "grup": "LABA+LAMA"},
    "SPIROLTO": {"etkin_madde": "TIOTROPIUM+OLODATEROL", "grup": "LABA+LAMA"},
    "STRIVERDI": {"etkin_madde": "OLODATEROL", "grup": "LABA"},
    "ANORO": {"etkin_madde": "UMEKLIDINYUM+VILANTEROL", "grup": "LABA+LAMA"},
    "ULTIBRO": {"etkin_madde": "INDAKATEROL+GLIKOPIRONYUM", "grup": "LABA+LAMA"},
    "DUAKLIR": {"etkin_madde": "AKLIDINYUM+FORMOTEROL", "grup": "LABA+LAMA"},
    # LABA+IKS kombo
    "SERETIDE": {"etkin_madde": "SALMETEROL+FLUTIKAZON", "grup": "LABA+IKS"},
    "SALMEX": {"etkin_madde": "SALMETEROL+FLUTIKAZON", "grup": "LABA+IKS"},
    "FOXAIR": {"etkin_madde": "SALMETEROL+FLUTIKAZON", "grup": "LABA+IKS"},
    "SYMBICORT": {"etkin_madde": "FORMOTEROL+BUDESONID", "grup": "LABA+IKS"},
    "DUORESP": {"etkin_madde": "FORMOTEROL+BUDESONID", "grup": "LABA+IKS"},
    "FOSTER": {"etkin_madde": "FORMOTEROL+BEKLOMETAZON", "grup": "LABA+IKS"},
    "INNOVAIR": {"etkin_madde": "FORMOTEROL+BEKLOMETAZON", "grup": "LABA+IKS"},
    "RELVAR": {"etkin_madde": "VILANTEROL+FLUTIKAZON", "grup": "LABA+IKS"},
    "REVITY": {"etkin_madde": "VILANTEROL+FLUTIKAZON", "grup": "LABA+IKS"},
    # Üçlü kombinasyon (LABA+LAMA+IKS)
    "TRIMBOW": {"etkin_madde": "FORMOTEROL+BEKLOMETAZON+GLIKOPIRONYUM", "grup": "LABA+LAMA+IKS"},
    "TRELEGY": {"etkin_madde": "VILANTEROL+UMEKLIDINYUM+FLUTIKAZON", "grup": "LABA+LAMA+IKS"},
    # IKS mono
    "PULMICORT": {"etkin_madde": "BUDESONID", "grup": "IKS"},
    "BUDECORT": {"etkin_madde": "BUDESONID", "grup": "IKS"},
    "MIFLONIDE": {"etkin_madde": "BUDESONID", "grup": "IKS"},
    "FLIXOTIDE": {"etkin_madde": "FLUTIKAZON", "grup": "IKS"},
    "BECLATE": {"etkin_madde": "BEKLOMETAZON", "grup": "IKS"},
    # SABA
    "VENTOLIN": {"etkin_madde": "SALBUTAMOL", "grup": "SABA"},
    "BUVENTOL": {"etkin_madde": "SALBUTAMOL", "grup": "SABA"},
    "BRICANYL": {"etkin_madde": "TERBUTALIN", "grup": "SABA"},
    # SAMA
    "ATROVENT": {"etkin_madde": "IPRATROPIUM", "grup": "SAMA"},
    "IPRAVENT": {"etkin_madde": "IPRATROPIUM", "grup": "SAMA"},
    # SABA+SAMA kombo
    "COMBIVENT": {"etkin_madde": "SALBUTAMOL+IPRATROPIUM", "grup": "SABA+SAMA"},
    "IPRAMOL": {"etkin_madde": "SALBUTAMOL+IPRATROPIUM", "grup": "SABA+SAMA"},
}


def etkin_madde_grup_bul(etkin_madde):
    """
    Etkin maddenin hangi ilaç gruplarına ait olduğunu bul.

    Args:
        etkin_madde: Etkin madde adı

    Returns:
        list[str]: Grup kodları (ör: ["DPP4", "SGLT2"])
    """
    if not etkin_madde:
        return []
    em_upper = etkin_madde.upper()
    gruplar = []
    for grup_kodu, grup_bilgi in ILAC_GRUPLARI.items():
        for madde in grup_bilgi["etkin_maddeler"]:
            if madde in em_upper or em_upper in madde:
                gruplar.append(grup_kodu)
                break
    return gruplar


def birlikte_kullanim_kontrol(hedef_ilac_etkin_madde, diger_ilaclar_etkin_madde,
                               yasakli_gruplar):
    """
    Hedef ilacın reçetedeki diğer ilaçlarla birlikte kullanım kontrolü.

    Args:
        hedef_ilac_etkin_madde: Kontrol edilen ilacın etkin maddesi
        diger_ilaclar_etkin_madde: Reçetedeki diğer ilaçların etkin maddeleri listesi
        yasakli_gruplar: Birlikte kullanılamayacak grup kodları (ör: ["DPP4", "SGLT2", "GLP1"])

    Returns:
        dict: {
            'uygun': bool,
            'cakisan_ilaclar': list[dict],  # {'etkin_madde': str, 'grup': str}
            'aciklama': str
        }
    """
    cakisan = []

    # Hedef ilacın kendi etkin maddelerini çıkar (ör: "EMPAGLIFLOZIN+LINAGLIPTIN" → iki madde)
    hedef_maddeler = set()
    if hedef_ilac_etkin_madde:
        for parca in hedef_ilac_etkin_madde.upper().replace("+", ",").replace("/", ",").split(","):
            hedef_maddeler.add(parca.strip())

    for diger_em in diger_ilaclar_etkin_madde:
        if not diger_em:
            continue
        diger_em_upper = diger_em.upper().strip()

        # Hedef ilacın kendi bileşenleriyle aynıysa atla
        if diger_em_upper in hedef_maddeler:
            continue

        diger_gruplar = etkin_madde_grup_bul(diger_em)
        for grup in diger_gruplar:
            if grup in yasakli_gruplar:
                cakisan.append({
                    'etkin_madde': diger_em,
                    'grup': ILAC_GRUPLARI[grup]['ad'],
                    'grup_kodu': grup,
                })

    if cakisan:
        cakisan_str = ", ".join(f"{c['etkin_madde']} ({c['grup']})" for c in cakisan)
        return {
            'uygun': False,
            'cakisan_ilaclar': cakisan,
            'aciklama': f"Birlikte kullanım UYGUNSUZ: {cakisan_str}"
        }

    return {
        'uygun': True,
        'cakisan_ilaclar': [],
        'aciklama': "Birlikte kullanım uygun"
    }

DB_DOSYA = Path(__file__).parent / "kontrol_kurallari.db"


def _db_baglan():
    """Veritabanına bağlan, tablolar yoksa oluştur."""
    conn = sqlite3.connect(str(DB_DOSYA))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    # Kural tablosu
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ilac_mesaj_kurallari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            etkin_madde TEXT,
            ilac_adi_pattern TEXT,
            mesaj_pattern TEXT NOT NULL,
            sut_maddesi TEXT,
            rapor_kodu TEXT,
            aksiyon TEXT NOT NULL DEFAULT 'gecir',
            kosullar TEXT,
            aciklama TEXT,
            olusturma_tarihi TEXT NOT NULL,
            guncelleme_tarihi TEXT,
            aktif INTEGER DEFAULT 1
        )
    """)

    # Kontrol raporu tablosu
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kontrol_raporu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oturum_id TEXT,
            grup TEXT,
            recete_sira_no INTEGER,
            sgk_recete_no TEXT,
            recete_tarihi TEXT,
            hasta_ismi TEXT,
            ilac_ismi TEXT,
            etkin_madde TEXT,
            recete_dozu TEXT,
            rapor_dozu TEXT,
            doz_uygunluk TEXT,
            mesaj_var INTEGER DEFAULT 0,
            mesaj_metni TEXT,
            mesaj_uygunluk TEXT,
            uyari_kodu TEXT,
            uyari_kodu_uygunluk TEXT,
            rapor_kodu TEXT,
            karar TEXT,
            kontrol_tarihi TEXT NOT NULL
        )
    """)

    # İlaç mesaj durum tablosu (cache)
    # durum: "yok" | "var" | "yoksay"
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ilac_mesaj_durumu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            etkin_madde TEXT NOT NULL,
            ilac_adi TEXT,
            barkod TEXT,
            durum TEXT NOT NULL DEFAULT 'yok',
            aciklama TEXT,
            olusturma_tarihi TEXT NOT NULL,
            guncelleme_tarihi TEXT,
            UNIQUE(etkin_madde)
        )
    """)

    # İlaç kontrol ayarları tablosu
    # Hangi ilaç/etkin madde/grup/uyarı kodu için hangi kontrollerin yapılıp yapılmayacağı
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ilac_kontrol_ayarlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hedef_tipi TEXT NOT NULL,
            hedef_deger TEXT NOT NULL,
            kontrol_tipi TEXT NOT NULL,
            aktif INTEGER NOT NULL DEFAULT 1,
            aciklama TEXT,
            olusturma_tarihi TEXT NOT NULL,
            guncelleme_tarihi TEXT,
            UNIQUE(hedef_tipi, hedef_deger, kontrol_tipi)
        )
    """)

    # Öğrenilen ilaç veritabanı
    # Sistem tarafından keşfedilen ilaçların adı, etkin maddesi, ATC/farmakolojik grubu
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ogrenilen_ilaclar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ilac_adi TEXT NOT NULL,
            etkin_madde TEXT,
            atc_grup TEXT,
            farmakolojik_grup TEXT,
            sgk_kodu TEXT,
            rapor_kodu TEXT,
            ilk_gorulme_tarihi TEXT NOT NULL,
            son_gorulme_tarihi TEXT,
            gorulme_sayisi INTEGER DEFAULT 1,
            sut_arastirildi_tarih TEXT,         -- AI ile SUT araştırma tarihi (6 ay TTL)
            sut_kategori TEXT,                   -- Araştırma sonucu kategori
            sut_aciklama TEXT,                   -- Araştırma açıklaması
            UNIQUE(ilac_adi)
        )
    """)
    # Migration: eski tablolara yeni kolonları ekle
    try:
        conn.execute("ALTER TABLE ogrenilen_ilaclar ADD COLUMN sut_arastirildi_tarih TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE ogrenilen_ilaclar ADD COLUMN sut_kategori TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE ogrenilen_ilaclar ADD COLUMN sut_aciklama TEXT")
    except Exception:
        pass

    conn.commit()
    return conn


class IlacMesajDurumu:
    """
    İlaç mesaj durum cache'i.

    4 durum:
    - None (veri yok): İlk karşılaşma, Medula'dan öğren
    - "yok": Mesaj yok, atla
    - "var": Mesaj var, kural kontrolü yap
    - "yoksay": Mesaj var ama önemsiz, yokmuş gibi davran
    """

    def __init__(self):
        self.conn = _db_baglan()
        self._cache = {}  # RAM cache: etkin_madde → durum
        self._cache_yukle()

    def _cache_yukle(self):
        """Tüm kayıtları RAM'e yükle (hızlı erişim)."""
        try:
            rows = self.conn.execute(
                "SELECT etkin_madde, durum FROM ilac_mesaj_durumu"
            ).fetchall()
            for row in rows:
                self._cache[row['etkin_madde'].upper()] = row['durum']
            logger.debug(f"İlaç mesaj cache yüklendi: {len(self._cache)} kayıt")
        except Exception as e:
            logger.warning(f"İlaç mesaj cache yükleme hatası: {e}")

    def durum_sorgula(self, etkin_madde):
        """
        Etkin maddeye göre mesaj durumunu sorgula.

        Returns:
            str veya None: "yok", "var", "yoksay" veya None (veri yok)
        """
        if not etkin_madde:
            return None
        return self._cache.get(etkin_madde.upper())

    def durum_kaydet(self, etkin_madde, durum, ilac_adi=None, barkod=None, aciklama=None):
        """
        İlaç mesaj durumunu kaydet veya güncelle.

        Args:
            etkin_madde: Etkin madde adı
            durum: "yok" | "var" | "yoksay"
            ilac_adi: İlaç adı (opsiyonel)
            barkod: Barkod (opsiyonel)
            aciklama: Açıklama (opsiyonel)
        """
        if not etkin_madde:
            return
        em_upper = etkin_madde.upper()
        now = datetime.now().isoformat()

        # UPSERT
        mevcut = self.conn.execute(
            "SELECT id FROM ilac_mesaj_durumu WHERE etkin_madde = ?", (em_upper,)
        ).fetchone()

        if mevcut:
            self.conn.execute("""
                UPDATE ilac_mesaj_durumu
                SET durum = ?, ilac_adi = COALESCE(?, ilac_adi),
                    barkod = COALESCE(?, barkod), aciklama = COALESCE(?, aciklama),
                    guncelleme_tarihi = ?
                WHERE etkin_madde = ?
            """, (durum, ilac_adi, barkod, aciklama, now, em_upper))
        else:
            self.conn.execute("""
                INSERT INTO ilac_mesaj_durumu
                (etkin_madde, ilac_adi, barkod, durum, aciklama, olusturma_tarihi)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (em_upper, ilac_adi, barkod, durum, aciklama, now))

        self.conn.commit()
        self._cache[em_upper] = durum
        logger.info(f"İlaç mesaj durumu kaydedildi: {em_upper} → {durum}")

    def tum_kayitlar(self):
        """Tüm kayıtları getir."""
        rows = self.conn.execute(
            "SELECT * FROM ilac_mesaj_durumu ORDER BY etkin_madde"
        ).fetchall()
        return [dict(r) for r in rows]

    def kapat(self):
        if self.conn:
            self.conn.close()


class KontrolKurallari:
    """İlaç mesaj kuralları veritabanı yöneticisi."""

    def __init__(self):
        self.conn = _db_baglan()

    def kural_ekle(self, mesaj_pattern, aksiyon, etkin_madde=None,
                   ilac_adi_pattern=None, sut_maddesi=None, rapor_kodu=None,
                   kosullar=None, aciklama=None):
        """
        Yeni kural ekle.

        Args:
            mesaj_pattern: Mesajdaki anahtar metin (kısmi eşleşme)
            aksiyon: "gecir" | "durdur" | "uyar" | "doz_kontrol"
            etkin_madde: Etkin madde filtresi (opsiyonel)
            ilac_adi_pattern: İlaç adı filtresi (opsiyonel)
            sut_maddesi: SUT maddesi filtresi (opsiyonel)
            rapor_kodu: Rapor kodu filtresi (opsiyonel)
            kosullar: Ek koşullar JSON string (opsiyonel)
            aciklama: Kural açıklaması

        Returns:
            int: Eklenen kuralın ID'si
        """
        now = datetime.now().isoformat()
        cursor = self.conn.execute("""
            INSERT INTO ilac_mesaj_kurallari
            (etkin_madde, ilac_adi_pattern, mesaj_pattern, sut_maddesi,
             rapor_kodu, aksiyon, kosullar, aciklama, olusturma_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (etkin_madde, ilac_adi_pattern, mesaj_pattern, sut_maddesi,
              rapor_kodu, aksiyon, kosullar, aciklama, now))
        self.conn.commit()
        kural_id = cursor.lastrowid
        logger.info(f"Kural eklendi (ID={kural_id}): {mesaj_pattern[:50]}... → {aksiyon}")
        return kural_id

    def kural_bul(self, mesaj_metni, etkin_madde=None, ilac_adi=None,
                  sut_maddesi=None, rapor_kodu=None):
        """
        Mesaj metnine uyan kuralları bul.

        Eşleşme: mesaj_pattern, mesaj_metni içinde geçiyorsa eşleşir.
        Ek filtreler (etkin_madde, ilac_adi, sut_maddesi, rapor_kodu)
        kural tablosunda dolu ise karşılaştırılır, boşsa joker kabul edilir.

        Returns:
            list[dict]: Eşleşen kurallar (en spesifik önce)
        """
        if not mesaj_metni:
            return []

        rows = self.conn.execute(
            "SELECT * FROM ilac_mesaj_kurallari WHERE aktif = 1"
        ).fetchall()

        eslesen = []
        mesaj_upper = mesaj_metni.upper()

        for row in rows:
            pattern = row['mesaj_pattern']
            if not pattern:
                continue
            if pattern.upper() not in mesaj_upper:
                continue

            # Ek filtre kontrolü (kural tablosunda dolu ise karşılaştır)
            if row['etkin_madde'] and etkin_madde:
                if row['etkin_madde'].upper() not in etkin_madde.upper():
                    continue
            if row['ilac_adi_pattern'] and ilac_adi:
                if row['ilac_adi_pattern'].upper() not in ilac_adi.upper():
                    continue
            if row['sut_maddesi'] and sut_maddesi:
                if row['sut_maddesi'].upper() not in sut_maddesi.upper():
                    continue
            if row['rapor_kodu'] and rapor_kodu:
                if row['rapor_kodu'] != rapor_kodu:
                    continue

            eslesen.append(dict(row))

        # Spesifik olanlar önce (daha fazla filtre dolu olan)
        eslesen.sort(key=lambda r: sum([
            bool(r.get('etkin_madde')),
            bool(r.get('ilac_adi_pattern')),
            bool(r.get('sut_maddesi')),
            bool(r.get('rapor_kodu')),
        ]), reverse=True)

        return eslesen

    def tum_kurallar(self):
        """Tüm aktif kuralları getir."""
        rows = self.conn.execute(
            "SELECT * FROM ilac_mesaj_kurallari WHERE aktif = 1 ORDER BY olusturma_tarihi DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def kural_sil(self, kural_id):
        """Kuralı pasifleştir (silme yerine)."""
        self.conn.execute(
            "UPDATE ilac_mesaj_kurallari SET aktif = 0, guncelleme_tarihi = ? WHERE id = ?",
            (datetime.now().isoformat(), kural_id)
        )
        self.conn.commit()

    def kural_uygula(self, mesaj_metni, ilac_bilgi, tum_recete_ilaclari,
                     ilac_gecmisi_ilaclari=None):
        """
        Mesaj metnine uyan kuralı bul ve uygula.

        Args:
            mesaj_metni: İlaç mesaj metni
            ilac_bilgi: dict - hedef ilacın bilgileri (etkin_madde, ilac_adi vb.)
            tum_recete_ilaclari: list[dict] - reçetedeki tüm ilaçların bilgileri
            ilac_gecmisi_ilaclari: list[dict] - hastanın ilaç geçmişi (opsiyonel)
                Her dict: {'etkin_madde': str, 'ilac_adi': str, ...}

        Returns:
            dict veya None: {
                'kural_id': int,
                'aksiyon': str,
                'uygun': bool,
                'aciklama': str,
                'detay': dict
            }
        """
        kurallar = self.kural_bul(
            mesaj_metni,
            etkin_madde=ilac_bilgi.get('etkin_madde'),
            ilac_adi=ilac_bilgi.get('ilac_adi'),
            sut_maddesi=ilac_bilgi.get('sut_maddesi'),
            rapor_kodu=ilac_bilgi.get('rapor_kodu'),
        )

        if not kurallar:
            return None

        kural = kurallar[0]  # En spesifik kural
        aksiyon = kural['aksiyon']
        kosullar = json.loads(kural['kosullar']) if kural.get('kosullar') else {}

        # Aksiyon: birlikte_kullanim_kontrol
        if aksiyon == "birlikte_kullanim_kontrol":
            yasakli_gruplar = kosullar.get('yasakli_gruplar', [])
            hedef_em = ilac_bilgi.get('etkin_madde', '')

            # Diğer ilaçların etkin maddelerini topla (hedef ilaç hariç)
            diger_etkin = []
            hedef_satir = ilac_bilgi.get('satir')
            for ilac in tum_recete_ilaclari:
                if ilac.get('satir') == hedef_satir:
                    continue
                em = ilac.get('eos_etkin_madde') or ilac.get('etkin_madde', '')
                if em:
                    diger_etkin.append(em)

            # Reçetedeki ilaçlarla kontrol
            sonuc = birlikte_kullanim_kontrol(hedef_em, diger_etkin, yasakli_gruplar)

            # İlaç geçmişi ile de kontrol et (eğer verilmişse)
            gecmis_cakisan = []
            if ilac_gecmisi_ilaclari and sonuc['uygun']:
                import re
                gecmis_etkin = []
                for ilac in ilac_gecmisi_ilaclari:
                    em = ilac.get('etkin_madde', '')
                    if em:
                        # Parantez içi grup adlarını temizle
                        em_temiz = re.sub(r'\([^)]*\)', '', em)
                        em_temiz = em_temiz.replace(' - ', '+').replace('-', '+')
                        em_temiz = ' '.join(em_temiz.split()).strip()
                        if em_temiz:
                            gecmis_etkin.append(em_temiz)

                if gecmis_etkin:
                    gecmis_sonuc = birlikte_kullanim_kontrol(
                        hedef_em, gecmis_etkin, yasakli_gruplar
                    )
                    if not gecmis_sonuc['uygun']:
                        sonuc = gecmis_sonuc
                        sonuc['aciklama'] = "ILAC GECMISI: " + sonuc['aciklama']

            return {
                'kural_id': kural['id'],
                'aksiyon': aksiyon,
                'uygun': sonuc['uygun'],
                'aciklama': sonuc['aciklama'],
                'detay': sonuc,
            }

        # Aksiyon: gecir (koşulsuz geçir)
        elif aksiyon == "gecir":
            return {
                'kural_id': kural['id'],
                'aksiyon': aksiyon,
                'uygun': True,
                'aciklama': kural.get('aciklama', 'Kural: geçir'),
                'detay': {},
            }

        # Aksiyon: durdur
        elif aksiyon == "durdur":
            return {
                'kural_id': kural['id'],
                'aksiyon': aksiyon,
                'uygun': False,
                'aciklama': kural.get('aciklama', 'Kural: durdur'),
                'detay': {},
            }

        return None

    def kapat(self):
        if self.conn:
            self.conn.close()


class KontrolRaporu:
    """Reçete kontrol raporu veritabanı yöneticisi."""

    def __init__(self, oturum_id=None):
        self.conn = _db_baglan()
        self.oturum_id = oturum_id

    def satir_ekle(self, grup, recete_sira_no, sgk_recete_no, ilac_ismi,
                   recete_tarihi=None, hasta_ismi=None, etkin_madde=None,
                   recete_dozu=None, rapor_dozu=None, doz_uygunluk=None,
                   mesaj_var=False, mesaj_metni=None, mesaj_uygunluk=None,
                   uyari_kodu=None, uyari_kodu_uygunluk=None,
                   rapor_kodu=None, karar=None):
        """Kontrol raporu tablosuna satır ekle."""
        now = datetime.now().isoformat()
        self.conn.execute("""
            INSERT INTO kontrol_raporu
            (oturum_id, grup, recete_sira_no, sgk_recete_no, recete_tarihi,
             hasta_ismi, ilac_ismi, etkin_madde, recete_dozu, rapor_dozu,
             doz_uygunluk, mesaj_var, mesaj_metni, mesaj_uygunluk,
             uyari_kodu, uyari_kodu_uygunluk, rapor_kodu, karar, kontrol_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (self.oturum_id, grup, recete_sira_no, sgk_recete_no, recete_tarihi,
              hasta_ismi, ilac_ismi, etkin_madde, recete_dozu, rapor_dozu,
              doz_uygunluk, int(mesaj_var), mesaj_metni, mesaj_uygunluk,
              uyari_kodu, uyari_kodu_uygunluk, rapor_kodu, karar, now))
        self.conn.commit()

    def oturum_raporu(self, oturum_id=None):
        """Oturum bazlı rapor getir."""
        oid = oturum_id or self.oturum_id
        if not oid:
            return []
        rows = self.conn.execute(
            "SELECT * FROM kontrol_raporu WHERE oturum_id = ? ORDER BY id",
            (oid,)
        ).fetchall()
        return [dict(r) for r in rows]

    def grup_raporu(self, grup, oturum_id=None):
        """Grup bazlı rapor getir."""
        oid = oturum_id or self.oturum_id
        if oid:
            rows = self.conn.execute(
                "SELECT * FROM kontrol_raporu WHERE grup = ? AND oturum_id = ? ORDER BY id",
                (grup, oid)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM kontrol_raporu WHERE grup = ? ORDER BY id DESC LIMIT 500",
                (grup,)
            ).fetchall()
        return [dict(r) for r in rows]

    def ozet(self, oturum_id=None):
        """Oturum özet istatistikleri."""
        oid = oturum_id or self.oturum_id
        if not oid:
            return {}
        row = self.conn.execute("""
            SELECT
                COUNT(*) as toplam_satir,
                COUNT(DISTINCT sgk_recete_no) as toplam_recete,
                SUM(CASE WHEN doz_uygunluk = 'uygun' THEN 1 ELSE 0 END) as doz_uygun,
                SUM(CASE WHEN doz_uygunluk = 'asim' THEN 1 ELSE 0 END) as doz_asim,
                SUM(CASE WHEN mesaj_var = 1 THEN 1 ELSE 0 END) as mesajli,
                SUM(CASE WHEN mesaj_uygunluk = 'uygun' THEN 1 ELSE 0 END) as mesaj_uygun,
                SUM(CASE WHEN mesaj_uygunluk = 'uygunsuz' THEN 1 ELSE 0 END) as mesaj_uygunsuz
            FROM kontrol_raporu WHERE oturum_id = ?
        """, (oid,)).fetchone()
        return dict(row) if row else {}

    def kapat(self):
        if self.conn:
            self.conn.close()


# ═══════════════════════════════════════════════════════════════
# ÖĞRENİLEN İLAÇLAR VERİTABANI
# ═══════════════════════════════════════════════════════════════

class OgrenilenIlaclar:
    """Sistem tarafından keşfedilen ilaçların veritabanı.

    Her karşılaşılan ilacın adı, etkin maddesi, ATC/farmakolojik grubu kaydedilir.
    Tekrar karşılaşıldığında görülme sayısı ve tarihi güncellenir.
    """

    def __init__(self):
        self.conn = _db_baglan()

    def ilac_kaydet(self, ilac_adi, etkin_madde=None, atc_grup=None,
                    farmakolojik_grup=None, sgk_kodu=None, rapor_kodu=None):
        """İlacı veritabanına kaydet veya güncelle (görülme sayısı artır)."""
        if not ilac_adi:
            return
        ilac_adi_upper = ilac_adi.strip().upper()
        now = datetime.now().isoformat()

        mevcut = self.conn.execute(
            "SELECT id, gorulme_sayisi FROM ogrenilen_ilaclar WHERE ilac_adi = ?",
            (ilac_adi_upper,)
        ).fetchone()

        if mevcut:
            self.conn.execute("""
                UPDATE ogrenilen_ilaclar
                SET etkin_madde = COALESCE(?, etkin_madde),
                    atc_grup = COALESCE(?, atc_grup),
                    farmakolojik_grup = COALESCE(?, farmakolojik_grup),
                    sgk_kodu = COALESCE(?, sgk_kodu),
                    rapor_kodu = COALESCE(?, rapor_kodu),
                    son_gorulme_tarihi = ?,
                    gorulme_sayisi = gorulme_sayisi + 1
                WHERE id = ?
            """, (etkin_madde, atc_grup, farmakolojik_grup, sgk_kodu,
                  rapor_kodu, now, mevcut['id']))
        else:
            self.conn.execute("""
                INSERT INTO ogrenilen_ilaclar
                (ilac_adi, etkin_madde, atc_grup, farmakolojik_grup,
                 sgk_kodu, rapor_kodu, ilk_gorulme_tarihi, son_gorulme_tarihi, gorulme_sayisi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (ilac_adi_upper, etkin_madde, atc_grup, farmakolojik_grup,
                  sgk_kodu, rapor_kodu, now, now))

        self.conn.commit()

    def ilac_bul(self, ilac_adi):
        """İlaç adına göre kayıt bul."""
        if not ilac_adi:
            return None
        row = self.conn.execute(
            "SELECT * FROM ogrenilen_ilaclar WHERE ilac_adi = ?",
            (ilac_adi.strip().upper(),)
        ).fetchone()
        return dict(row) if row else None

    def sut_arastirma_gerekli_mi(self, ilac_adi, ttl_gun=180):
        """Bu ilaç için SUT araştırması gerekli mi?
        - Kayıt yoksa: True (hiç araştırılmamış)
        - Kayıt var ama sut_arastirildi_tarih boşsa: True
        - Son araştırma > ttl_gun önce ise: True (güncel değil)
        - Aksi halde: False (son ttl_gun içinde araştırılmış, DB değeri geçerli)
        Returns: (arastir: bool, mevcut_kayit: dict|None)
        """
        kayit = self.ilac_bul(ilac_adi)
        if not kayit:
            return True, None
        tarih_str = kayit.get("sut_arastirildi_tarih")
        if not tarih_str:
            return True, kayit
        try:
            son = datetime.fromisoformat(tarih_str)
            gecen = (datetime.now() - son).days
            if gecen > ttl_gun:
                return True, kayit
            return False, kayit
        except Exception:
            return True, kayit

    def sut_arastirma_kaydet(self, ilac_adi, kategori, aciklama="", etkin_madde=None):
        """AI tarafından yapılan SUT araştırmasının sonucunu kaydet (tarih damgası ile)."""
        if not ilac_adi:
            return
        ilac_adi_upper = ilac_adi.strip().upper()
        now = datetime.now().isoformat()
        mevcut = self.ilac_bul(ilac_adi_upper)
        if mevcut:
            self.conn.execute("""
                UPDATE ogrenilen_ilaclar
                SET sut_arastirildi_tarih = ?,
                    sut_kategori = ?,
                    sut_aciklama = ?,
                    farmakolojik_grup = COALESCE(?, farmakolojik_grup),
                    etkin_madde = COALESCE(?, etkin_madde)
                WHERE ilac_adi = ?
            """, (now, kategori, aciklama, kategori, etkin_madde, ilac_adi_upper))
        else:
            self.conn.execute("""
                INSERT INTO ogrenilen_ilaclar
                (ilac_adi, etkin_madde, farmakolojik_grup, ilk_gorulme_tarihi,
                 son_gorulme_tarihi, gorulme_sayisi,
                 sut_arastirildi_tarih, sut_kategori, sut_aciklama)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (ilac_adi_upper, etkin_madde, kategori, now, now, now, kategori, aciklama))
        self.conn.commit()

    def etkin_madde_ile_bul(self, etkin_madde):
        """Etkin maddeye göre tüm ilaçları bul."""
        if not etkin_madde:
            return []
        rows = self.conn.execute(
            "SELECT * FROM ogrenilen_ilaclar WHERE etkin_madde = ? ORDER BY ilac_adi",
            (etkin_madde.strip().upper(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def grup_ile_bul(self, atc_grup=None, farmakolojik_grup=None):
        """ATC veya farmakolojik gruba göre ilaçları bul."""
        if atc_grup:
            rows = self.conn.execute(
                "SELECT * FROM ogrenilen_ilaclar WHERE atc_grup = ? ORDER BY ilac_adi",
                (atc_grup.strip().upper(),)
            ).fetchall()
        elif farmakolojik_grup:
            rows = self.conn.execute(
                "SELECT * FROM ogrenilen_ilaclar WHERE farmakolojik_grup = ? ORDER BY ilac_adi",
                (farmakolojik_grup.strip().upper(),)
            ).fetchall()
        else:
            return []
        return [dict(r) for r in rows]

    def tum_ilaclar(self):
        """Tüm öğrenilen ilaçları getir."""
        rows = self.conn.execute(
            "SELECT * FROM ogrenilen_ilaclar ORDER BY ilac_adi"
        ).fetchall()
        return [dict(r) for r in rows]

    def istatistik(self):
        """Özet istatistikler."""
        row = self.conn.execute("""
            SELECT
                COUNT(*) as toplam_ilac,
                COUNT(DISTINCT etkin_madde) as farkli_etkin_madde,
                COUNT(DISTINCT atc_grup) as farkli_atc_grup,
                COUNT(DISTINCT farmakolojik_grup) as farkli_farmakolojik_grup
            FROM ogrenilen_ilaclar
        """).fetchone()
        return dict(row) if row else {}

    def kapat(self):
        if self.conn:
            self.conn.close()


# ═══════════════════════════════════════════════════════════════
# İLAÇ KONTROL AYARLARI (BYPASS SİSTEMİ)
# ═══════════════════════════════════════════════════════════════

# Hedef tipleri
HEDEF_TIPI_ILAC = "ilac"               # Belirli bir ilaç adı (ör: "TRAVAZOL")
HEDEF_TIPI_ETKIN_MADDE = "etkin_madde"  # Belirli bir etkin madde (ör: "METFORMIN")
HEDEF_TIPI_ATC_GRUP = "atc_grup"       # ATC/farmakolojik grup (ör: "TOPİKAL ANTİFUNGALLER")
HEDEF_TIPI_UYARI_KODU = "uyari_kodu"   # Belirli bir uyarı kodu (ör: "280")

# Kontrol tipleri
KONTROL_TIPI_UYARI_KODU = "uyari_kodu"     # Uyarı kodu kontrolü
KONTROL_TIPI_SUT = "sut"                    # SUT kontrolü
KONTROL_TIPI_ILAC_MESAJI = "ilac_mesaji"    # İlaç mesajı kontrolü (var/yok)
KONTROL_TIPI_DOZ = "doz"                    # Doz kontrolü
KONTROL_TIPI_HEPSI = "hepsi"               # Tüm kontroller

# Öncelik sırası: ilac > etkin_madde > atc_grup > uyari_kodu
HEDEF_ONCELIK = {
    HEDEF_TIPI_ILAC: 4,
    HEDEF_TIPI_ETKIN_MADDE: 3,
    HEDEF_TIPI_ATC_GRUP: 2,
    HEDEF_TIPI_UYARI_KODU: 1,
}


class KontrolAyarlari:
    """İlaç kontrol bypass ayarları yöneticisi.

    Hangi ilaç/etkin madde/ATC grup/uyarı kodu için hangi kontrollerin
    yapılıp yapılmayacağını yönetir.

    Kullanım örnekleri:
        ayarlar.ayar_kaydet("ilac", "TRAVAZOL", "uyari_kodu", aktif=False)
        ayarlar.ayar_kaydet("atc_grup", "TOPİKAL ANTİFUNGALLER", "uyari_kodu", aktif=False)
        ayarlar.ayar_kaydet("ilac", "GLİFOR", "ilac_mesaji", aktif=False)

        if ayarlar.kontrol_aktif_mi("ilac_mesaji", ilac_adi="GLİFOR"):
            # mesaj kontrolü yap
        else:
            # bypass
    """

    def __init__(self):
        self.conn = _db_baglan()
        self._cache = {}  # (hedef_tipi, hedef_deger, kontrol_tipi) → aktif
        self._cache_yukle()

    def _cache_yukle(self):
        """Tüm ayarları RAM cache'e yükle."""
        try:
            rows = self.conn.execute(
                "SELECT hedef_tipi, hedef_deger, kontrol_tipi, aktif FROM ilac_kontrol_ayarlari"
            ).fetchall()
            for row in rows:
                key = (row['hedef_tipi'], row['hedef_deger'].upper(), row['kontrol_tipi'])
                self._cache[key] = bool(row['aktif'])
            logger.debug(f"Kontrol ayarları cache yüklendi: {len(self._cache)} kayıt")
        except Exception as e:
            logger.warning(f"Kontrol ayarları cache yükleme hatası: {e}")

    def ayar_kaydet(self, hedef_tipi, hedef_deger, kontrol_tipi, aktif=True, aciklama=None):
        """Kontrol ayarı kaydet veya güncelle.

        Args:
            hedef_tipi: "ilac", "etkin_madde", "atc_grup", "uyari_kodu"
            hedef_deger: Hedef değer (ilaç adı, etkin madde, grup adı, uyarı kodu)
            kontrol_tipi: "uyari_kodu", "sut", "ilac_mesaji", "doz", "hepsi"
            aktif: True=kontrol yap, False=kontrol yapma (bypass)
            aciklama: Açıklama metni
        """
        if not hedef_deger:
            return
        hedef_deger_upper = hedef_deger.strip().upper()
        now = datetime.now().isoformat()
        aktif_int = 1 if aktif else 0

        mevcut = self.conn.execute(
            "SELECT id FROM ilac_kontrol_ayarlari WHERE hedef_tipi = ? AND hedef_deger = ? AND kontrol_tipi = ?",
            (hedef_tipi, hedef_deger_upper, kontrol_tipi)
        ).fetchone()

        if mevcut:
            self.conn.execute("""
                UPDATE ilac_kontrol_ayarlari
                SET aktif = ?, aciklama = COALESCE(?, aciklama), guncelleme_tarihi = ?
                WHERE id = ?
            """, (aktif_int, aciklama, now, mevcut['id']))
        else:
            self.conn.execute("""
                INSERT INTO ilac_kontrol_ayarlari
                (hedef_tipi, hedef_deger, kontrol_tipi, aktif, aciklama, olusturma_tarihi)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (hedef_tipi, hedef_deger_upper, kontrol_tipi, aktif_int, aciklama, now))

        self.conn.commit()
        key = (hedef_tipi, hedef_deger_upper, kontrol_tipi)
        self._cache[key] = bool(aktif_int)
        durum = "AKTİF" if aktif else "PASİF"
        logger.info(f"Kontrol ayarı: {hedef_tipi}={hedef_deger_upper}, {kontrol_tipi} → {durum}")

    def ayar_sil(self, hedef_tipi, hedef_deger, kontrol_tipi):
        """Ayarı sil (varsayılan davranışa dön = kontrol yap)."""
        if not hedef_deger:
            return
        hedef_deger_upper = hedef_deger.strip().upper()
        self.conn.execute(
            "DELETE FROM ilac_kontrol_ayarlari WHERE hedef_tipi = ? AND hedef_deger = ? AND kontrol_tipi = ?",
            (hedef_tipi, hedef_deger_upper, kontrol_tipi)
        )
        self.conn.commit()
        key = (hedef_tipi, hedef_deger_upper, kontrol_tipi)
        self._cache.pop(key, None)

    def _ayar_getir(self, hedef_tipi, hedef_deger, kontrol_tipi):
        """Cache'den tekil ayar sorgula. None = ayar yok."""
        if not hedef_deger:
            return None
        key = (hedef_tipi, hedef_deger.strip().upper(), kontrol_tipi)
        if key in self._cache:
            return self._cache[key]
        # "hepsi" kontrolünü de dene
        key_hepsi = (hedef_tipi, hedef_deger.strip().upper(), KONTROL_TIPI_HEPSI)
        if key_hepsi in self._cache:
            return self._cache[key_hepsi]
        return None

    def kontrol_aktif_mi(self, kontrol_tipi, ilac_adi=None, etkin_madde=None,
                         atc_grup=None, farmakolojik_grup=None, uyari_kodu=None):
        """Belirtilen kontrol bu ilaç/madde/grup için aktif mi?

        Öncelik: ilac > etkin_madde > atc_grup > uyari_kodu
        Hiç ayar yoksa varsayılan = True (kontrol yap).

        Returns:
            bool: True=kontrol yap, False=bypass
        """
        # İlaç adından kısa adı çıkar (ör: "TRAVAZOL 20 MG KREM" → "TRAVAZOL")
        ilac_kisa = None
        if ilac_adi:
            ilac_kisa = ilac_adi.strip().upper().split()[0] if ilac_adi.strip() else None

        # 1. İlaç adı (tam ve kısa)
        if ilac_adi:
            sonuc = self._ayar_getir(HEDEF_TIPI_ILAC, ilac_adi.strip(), kontrol_tipi)
            if sonuc is not None:
                return sonuc
        if ilac_kisa:
            sonuc = self._ayar_getir(HEDEF_TIPI_ILAC, ilac_kisa, kontrol_tipi)
            if sonuc is not None:
                return sonuc

        # 2. Etkin madde
        if etkin_madde:
            sonuc = self._ayar_getir(HEDEF_TIPI_ETKIN_MADDE, etkin_madde.strip(), kontrol_tipi)
            if sonuc is not None:
                return sonuc

        # 3. ATC grup / Farmakolojik grup
        if atc_grup:
            sonuc = self._ayar_getir(HEDEF_TIPI_ATC_GRUP, atc_grup.strip(), kontrol_tipi)
            if sonuc is not None:
                return sonuc
        if farmakolojik_grup:
            sonuc = self._ayar_getir(HEDEF_TIPI_ATC_GRUP, farmakolojik_grup.strip(), kontrol_tipi)
            if sonuc is not None:
                return sonuc

        # 4. Uyarı kodu
        if uyari_kodu:
            sonuc = self._ayar_getir(HEDEF_TIPI_UYARI_KODU, uyari_kodu.strip(), kontrol_tipi)
            if sonuc is not None:
                return sonuc

        # Varsayılan: kontrol yap
        return True

    def tum_ayarlar(self):
        """Tüm ayarları getir."""
        rows = self.conn.execute(
            "SELECT * FROM ilac_kontrol_ayarlari ORDER BY hedef_tipi, hedef_deger"
        ).fetchall()
        return [dict(r) for r in rows]

    def hedef_ayarlari(self, hedef_tipi, hedef_deger):
        """Belirli bir hedef için tüm ayarları getir."""
        if not hedef_deger:
            return []
        rows = self.conn.execute(
            "SELECT * FROM ilac_kontrol_ayarlari WHERE hedef_tipi = ? AND hedef_deger = ?",
            (hedef_tipi, hedef_deger.strip().upper())
        ).fetchall()
        return [dict(r) for r in rows]

    def bypass_ozet(self):
        """Bypass (pasif) olan tüm ayarları özetle."""
        rows = self.conn.execute(
            "SELECT * FROM ilac_kontrol_ayarlari WHERE aktif = 0 ORDER BY hedef_tipi, hedef_deger"
        ).fetchall()
        return [dict(r) for r in rows]

    def kapat(self):
        if self.conn:
            self.conn.close()


# ═══════════════════════════════════════════════════════════════
# GLOBAL SINGLETON ERİŞİMCİLER
# ═══════════════════════════════════════════════════════════════

_kontrol_ayarlari_instance = None
_ogrenilen_ilaclar_instance = None


def get_kontrol_ayarlari():
    """KontrolAyarlari singleton'ı döndür."""
    global _kontrol_ayarlari_instance
    if _kontrol_ayarlari_instance is None:
        _kontrol_ayarlari_instance = KontrolAyarlari()
    return _kontrol_ayarlari_instance


def get_ogrenilen_ilaclar():
    """OgrenilenIlaclar singleton'ı döndür."""
    global _ogrenilen_ilaclar_instance
    if _ogrenilen_ilaclar_instance is None:
        _ogrenilen_ilaclar_instance = OgrenilenIlaclar()
    return _ogrenilen_ilaclar_instance
