# -*- coding: utf-8 -*-
"""Hasta Rapor Geçmişi — yerel SQLite katmanı.

MEDULA'dan tarayıcı ile çekilen hasta raporları burada saklanır. Hepatit/
diyabet/KOAH gibi kontrollerde 'başlangıç raporu var mı / hangi raporda
başladı' sorgusu için kullanılır.

DB: APPDATA/BotanikKasa/hasta_rapor_gecmisi.db (uygulama veri klasörü)
Tablo: hasta_rapor_gecmisi (UNIQUE: hasta_tc + rapor_takip_no)
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════
# 1. KATEGORİ EŞLEME (rapor_kodu → ilaç grubu, hangi kontrol için kullanılacak)
# ═════════════════════════════════════════════════════════════════════════

# Rapor kodu prefix → kategori (hepatit kontrollerinde 'B18.x'/'B17.1'/'B16'
# içeren tüm raporları filtrelemek için)
KATEGORI_ICD_PREFIX = {
    'HEPATIT_B': ('B18.0', 'B18.1', 'B16'),
    'HEPATIT_C': ('B18.2', 'B17.1'),
    'HEPATIT_D': ('B17.0',),
    'HEPATIT_GENEL': ('B16', 'B17', 'B18', 'B19', 'Z22.5'),
    'DIYABET': ('E10', 'E11', 'E13', 'E14'),
    'HIPERTANSIYON': ('I10', 'I11', 'I12', 'I13', 'I15'),
    'KOAH_ASTIM': ('J44', 'J45', 'J46'),
    'KKY': ('I50',),
}


# ═════════════════════════════════════════════════════════════════════════
# 2. DATACLASS — RaporKaydi
# ═════════════════════════════════════════════════════════════════════════

@dataclass
class RaporKaydi:
    hasta_tc: str
    rapor_takip_no: str
    baslangic_tarihi: str = ''          # dd/mm/yyyy
    bitis_tarihi: str = ''              # dd/mm/yyyy
    rapor_kodu: str = ''                # "14.01", "06.01", vb.
    tani: str = ''                      # "Hepatit B Enfeksiyon"
    icd_kodu: str = ''                  # "B18.1"
    rapor_tipi: str = ''                # "Elektronik İmzalı Rapor"
    detay_metni: str = ''               # rapor detay sayfasından (opsiyonel)
    kategori: str = ''                  # 'HEPATIT_B', vb. (otomatik atanır)
    rapor_sira: int = 0                 # MEDULA tablosundaki sıra (en yenisi=0)
    eklenme_tarihi: str = ''            # auto
    guncellenme_tarihi: str = ''        # auto

    def kategoriyi_belirle(self) -> str:
        """ICD koduna göre kategoriyi otomatik belirle (HEPATIT_B, DIYABET vb.)."""
        if not self.icd_kodu:
            return ''
        icd_u = self.icd_kodu.upper().replace(' ', '')
        for kat, prefixler in KATEGORI_ICD_PREFIX.items():
            for p in prefixler:
                if icd_u.startswith(p):
                    return kat
        return ''


# ═════════════════════════════════════════════════════════════════════════
# 3. DB YOL ÇÖZÜMLEME (APPDATA/BotanikKasa kalıbı, mevcut DB'lerle uyumlu)
# ═════════════════════════════════════════════════════════════════════════

def _db_yolu() -> Path:
    """APPDATA/BotanikKasa/hasta_rapor_gecmisi.db (fallback: proje kökü)."""
    appdata = os.environ.get('APPDATA')
    if appdata:
        klasor = Path(appdata) / 'BotanikKasa'
        klasor.mkdir(parents=True, exist_ok=True)
        return klasor / 'hasta_rapor_gecmisi.db'
    return Path(__file__).resolve().parent.parent / 'hasta_rapor_gecmisi.db'


def _baglanti() -> sqlite3.Connection:
    """SQLite bağlantısı (foreign_keys + row_factory)."""
    conn = sqlite3.connect(str(_db_yolu()))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


# ═════════════════════════════════════════════════════════════════════════
# 4. ŞEMA — CREATE TABLE
# ═════════════════════════════════════════════════════════════════════════

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS hasta_rapor_gecmisi (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    hasta_tc             TEXT NOT NULL,
    rapor_takip_no       TEXT NOT NULL,
    baslangic_tarihi     TEXT DEFAULT '',
    bitis_tarihi         TEXT DEFAULT '',
    rapor_kodu           TEXT DEFAULT '',
    tani                 TEXT DEFAULT '',
    icd_kodu             TEXT DEFAULT '',
    rapor_tipi           TEXT DEFAULT '',
    detay_metni          TEXT DEFAULT '',
    kategori             TEXT DEFAULT '',
    rapor_sira           INTEGER DEFAULT 0,
    eklenme_tarihi       TEXT DEFAULT (datetime('now', 'localtime')),
    guncellenme_tarihi   TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(hasta_tc, rapor_takip_no)
);
CREATE INDEX IF NOT EXISTS idx_hasta_tc ON hasta_rapor_gecmisi(hasta_tc);
CREATE INDEX IF NOT EXISTS idx_kategori ON hasta_rapor_gecmisi(hasta_tc, kategori);
CREATE INDEX IF NOT EXISTS idx_baslangic ON hasta_rapor_gecmisi(hasta_tc, baslangic_tarihi);
"""


def sema_olustur() -> None:
    """Tabloyu (yoksa) oluştur — uygulama açılışında çağrılır."""
    with _baglanti() as conn:
        conn.executescript(_SCHEMA_SQL)


# ═════════════════════════════════════════════════════════════════════════
# 5. CRUD
# ═════════════════════════════════════════════════════════════════════════

def kaydet(rapor: RaporKaydi) -> int:
    """Bir raporu DB'ye yaz (varsa güncelle, yoksa ekle). Returns: id."""
    if not rapor.hasta_tc or not rapor.rapor_takip_no:
        raise ValueError('hasta_tc ve rapor_takip_no zorunlu')
    if not rapor.kategori:
        rapor.kategori = rapor.kategoriyi_belirle()
    simdi = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with _baglanti() as conn:
        # INSERT OR REPLACE eski id'yi koru, eklenme_tarihi'ni kaybetme
        mevcut = conn.execute(
            'SELECT id, eklenme_tarihi FROM hasta_rapor_gecmisi '
            'WHERE hasta_tc=? AND rapor_takip_no=?',
            (rapor.hasta_tc, rapor.rapor_takip_no)).fetchone()
        if mevcut:
            conn.execute("""
                UPDATE hasta_rapor_gecmisi SET
                    baslangic_tarihi=?, bitis_tarihi=?, rapor_kodu=?, tani=?,
                    icd_kodu=?, rapor_tipi=?, detay_metni=?, kategori=?,
                    rapor_sira=?, guncellenme_tarihi=?
                WHERE id=?
            """, (rapor.baslangic_tarihi, rapor.bitis_tarihi, rapor.rapor_kodu,
                  rapor.tani, rapor.icd_kodu, rapor.rapor_tipi,
                  rapor.detay_metni, rapor.kategori, rapor.rapor_sira,
                  simdi, mevcut['id']))
            return int(mevcut['id'])
        cur = conn.execute("""
            INSERT INTO hasta_rapor_gecmisi
                (hasta_tc, rapor_takip_no, baslangic_tarihi, bitis_tarihi,
                 rapor_kodu, tani, icd_kodu, rapor_tipi, detay_metni,
                 kategori, rapor_sira, eklenme_tarihi, guncellenme_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (rapor.hasta_tc, rapor.rapor_takip_no, rapor.baslangic_tarihi,
              rapor.bitis_tarihi, rapor.rapor_kodu, rapor.tani, rapor.icd_kodu,
              rapor.rapor_tipi, rapor.detay_metni, rapor.kategori,
              rapor.rapor_sira, simdi, simdi))
        return int(cur.lastrowid)


def hasta_raporlarini_oku(hasta_tc: str,
                            kategori: Optional[str] = None
                            ) -> List[RaporKaydi]:
    """Bir hastanın tüm raporlarını oku (en yeniden eskiye sıralı).

    kategori: 'HEPATIT_B', 'HEPATIT_C', 'DIYABET' vb. — None ise hepsi.
    """
    sql = ('SELECT * FROM hasta_rapor_gecmisi WHERE hasta_tc=? ')
    params: list = [hasta_tc]
    if kategori:
        sql += 'AND kategori=? '
        params.append(kategori)
    sql += 'ORDER BY baslangic_tarihi DESC, rapor_sira ASC'
    with _baglanti() as conn:
        return [_row_to_kayit(r) for r in conn.execute(sql, params).fetchall()]


def en_eski_baslangic_raporu(hasta_tc: str,
                                kategori: Optional[str] = None
                                ) -> Optional[RaporKaydi]:
    """Bir hastanın belirli kategorideki en eski raporu = 'başlangıç raporu'.

    Hepatit kontrollerinde 'hasta önceki rapor başlangıcı' sorgusu için
    kullanılır.
    """
    sql = 'SELECT * FROM hasta_rapor_gecmisi WHERE hasta_tc=? '
    params: list = [hasta_tc]
    if kategori:
        sql += 'AND kategori=? '
        params.append(kategori)
    sql += "ORDER BY baslangic_tarihi ASC LIMIT 1"
    with _baglanti() as conn:
        r = conn.execute(sql, params).fetchone()
        return _row_to_kayit(r) if r else None


def mevcut_rapor_takipleri(hasta_tc: str) -> Set[str]:
    """Bir hastanın DB'de zaten kayıtlı rapor_takip_no'larını döndür.

    MEDULA tarama sırasında 'bu rapor zaten var mı, atlayalım mı?' kontrolü.
    """
    with _baglanti() as conn:
        return {r['rapor_takip_no'] for r in conn.execute(
            'SELECT rapor_takip_no FROM hasta_rapor_gecmisi WHERE hasta_tc=?',
            (hasta_tc,)).fetchall()}


def sil(hasta_tc: str, rapor_takip_no: Optional[str] = None) -> int:
    """Hasta raporu sil. rapor_takip_no None ise tüm hasta silinir."""
    sql = 'DELETE FROM hasta_rapor_gecmisi WHERE hasta_tc=?'
    params: list = [hasta_tc]
    if rapor_takip_no:
        sql += ' AND rapor_takip_no=?'
        params.append(rapor_takip_no)
    with _baglanti() as conn:
        cur = conn.execute(sql, params)
        return cur.rowcount


# ═════════════════════════════════════════════════════════════════════════
# 6. YARDIMCI — rapor_kodu metninden ICD ve rapor_kodu ayır
# ═════════════════════════════════════════════════════════════════════════

_RAPOR_KODU_PATTERN = re.compile(
    r'^\s*([\d]+(?:\.[\d]+)?)\s*[-–—]\s*(.+?)\s*\(([A-Z][\d]+(?:\.[\d]+)?)\)\s*$'
)


def rapor_kodu_metnini_parcala(metin: str) -> tuple:
    """'06.01 - Hepatit B Gastro(B18.1)' → ('06.01', 'Hepatit B Gastro', 'B18.1').

    Eşleşmezse boş 3-tuple döner.
    """
    if not metin:
        return ('', '', '')
    m = _RAPOR_KODU_PATTERN.match(metin)
    if not m:
        return ('', metin.strip(), '')
    return (m.group(1).strip(), m.group(2).strip(), m.group(3).strip())


def _row_to_kayit(r: sqlite3.Row) -> RaporKaydi:
    return RaporKaydi(
        hasta_tc=r['hasta_tc'],
        rapor_takip_no=r['rapor_takip_no'],
        baslangic_tarihi=r['baslangic_tarihi'] or '',
        bitis_tarihi=r['bitis_tarihi'] or '',
        rapor_kodu=r['rapor_kodu'] or '',
        tani=r['tani'] or '',
        icd_kodu=r['icd_kodu'] or '',
        rapor_tipi=r['rapor_tipi'] or '',
        detay_metni=r['detay_metni'] or '',
        kategori=r['kategori'] or '',
        rapor_sira=r['rapor_sira'] or 0,
        eklenme_tarihi=r['eklenme_tarihi'] or '',
        guncellenme_tarihi=r['guncellenme_tarihi'] or '',
    )


# Public API
__all__ = [
    'RaporKaydi', 'KATEGORI_ICD_PREFIX',
    'sema_olustur', 'kaydet', 'sil',
    'hasta_raporlarini_oku', 'en_eski_baslangic_raporu',
    'mevcut_rapor_takipleri', 'rapor_kodu_metnini_parcala',
]
