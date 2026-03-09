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
