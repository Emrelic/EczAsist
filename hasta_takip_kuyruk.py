"""
Hasta Takip WhatsApp - Mesaj Biriktirme & Zamanlama Motoru

SQLite tabanlı yerel kuyruk. Botanik EOS DB'ye dokunmaz.
Modlar:
  - Anlık        : Her tarama sonrası günü gelen her hastaya anında bildir
  - Pazartesi    : Günü gelenleri biriktir, pazartesi birleşik mesaj olarak listele
  - X günde bir  : Belirli periyotta topla, gönderim gününde listele
  - Hafta sonu tolerans: Cuma-Pazartesi arası günü gelecekleri de aynı mesajda birleştir
"""

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_SCRIPT_DIR, "hasta_takip.db")
_AYAR_PATH = os.path.join(_SCRIPT_DIR, "hasta_takip_ayarlari.json")


@dataclass
class HastaTakipAyarlari:
    # Gönderim modu: "anlik" | "pazartesi" | "periyodik"
    gonderim_modu: str = "anlik"

    # Periyodik modda kaç günde bir listele/gönder
    periyot_gun: int = 5

    # Hafta sonu toleransı: bu kadar gün sonrasına kadar da listele/biriktir
    hafta_sonu_tolerans_gun: int = 3

    # Rapor-sonrası ek yazdırma toleransı (Medula "bitiş -15 gün" kuralı)
    rapor_yazdirma_tolerans_gun: int = 15

    # Eski bitiş tarihli kayıtları listeden düşür
    eski_kayit_gun: int = 30

    # Sadece takipli hastalar (Musteri.MusteriTakipli=1)
    sadece_takipli: bool = True

    # Veri kaynağı: "RECETE" | "MEDULA" | "BIRLESIK"
    kaynak: str = "BIRLESIK"

    # Çalışma saatleri: dışında gönderim penceresi açılmaz
    calisma_baslangic: str = "09:00"
    calisma_bitis: str = "18:00"

    # Mesaj şablonu (placeholders: {hasta_adi}, {ilac_listesi}, {eczane_adi}, {eczane_tel})
    mesaj_sablonu: str = (
        "Sayın {hasta_adi}\n"
        "{ilac_listesi}\n"
        " ilacınızı DOKTORA yazdırma günü gelmiştir. {eczane_adi}  {eczane_tel}"
    )

    # İlaç listesinde her satırın formatı
    ilac_satir_formati: str = "{urun_adi},"

    eczane_adi: str = "İKİZLER ECZANESİ"
    eczane_tel: str = "0542 515 74 40"

    # Pazartesi mod için gönderim günü (0=Pazartesi, 6=Pazar)
    toplu_gonderim_gunu: int = 0

    # --- Rapor bitiş takibi ---
    rapor_bitis_uyari_gun: int = 30  # Bu kadar gün kala raporla
    rapor_bitis_mesaj_sablonu: str = (
        "Sayın {hasta_adi}\n"
        "Aşağıdaki raporlarınız yaklaşan tarihlerde bitmektedir:\n\n"
        "{rapor_listesi}\n"
        "Lütfen yenilemek için doktorunuza başvurunuz.\n"
        "{eczane_adi}  {eczane_tel}"
    )
    rapor_bitis_tani_satir_formati: str = (
        "Tanı: {rapor_kodu} - {rapor_kod_aciklama}\n"
        "ICD: {icd_kodu} - {icd_aciklamasi}\n"
        "Başlama: {baslama} | Bitiş: {bitis} (kalan: {kalan_gun} gün)\n"
        "Etken Maddeler: {etkin_maddeler}\n"
        "İlaçlar: {ilaclar}\n"
    )

    @classmethod
    def yukle(cls) -> "HastaTakipAyarlari":
        if not os.path.exists(_AYAR_PATH):
            return cls()
        try:
            with open(_AYAR_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
        except Exception as e:
            logger.warning("Ayarlar okunamadı, varsayılan kullanılıyor: %s", e)
            return cls()

    def kaydet(self) -> None:
        with open(_AYAR_PATH, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2)


def _saat_parse(s: str) -> Optional[tuple]:
    try:
        h, m = s.split(":")
        return int(h), int(m)
    except Exception:
        return None


class MesajKuyrugu:
    """SQLite tabanlı mesaj kuyruğu ve gönderim log'u."""

    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS mesaj_kuyrugu (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    musteri_id       INTEGER NOT NULL,
                    hasta_adi        TEXT NOT NULL,
                    cep_tel          TEXT,
                    tckn             TEXT,
                    toplam_ziyaret   INTEGER,
                    son_ziyaret      TEXT,
                    takipli          INTEGER DEFAULT 0,
                    ilac_json        TEXT NOT NULL,       -- [{urun_adi, bitis_tarihi, yazdirma_tarihi, kaynak}, ...]
                    olusturma        TEXT NOT NULL,       -- ISO datetime
                    planli_gonderim  TEXT,                -- ISO date (bu tarihte gösterilsin)
                    durum            TEXT NOT NULL DEFAULT 'bekliyor',  -- bekliyor|gonderildi|iptal
                    UNIQUE(musteri_id, durum)
                );

                CREATE INDEX IF NOT EXISTS idx_mk_durum ON mesaj_kuyrugu(durum, planli_gonderim);

                CREATE TABLE IF NOT EXISTS gonderim_log (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    musteri_id   INTEGER NOT NULL,
                    hasta_adi    TEXT,
                    cep_tel      TEXT,
                    mesaj_metni  TEXT NOT NULL,
                    zaman        TEXT NOT NULL,
                    sonuc        TEXT,
                    isaret       TEXT,
                    not_metni    TEXT
                );
                """
            )
            # Migration: eski şemaya isaret/not_metni eklensin
            cur = c.execute("PRAGMA table_info(gonderim_log)").fetchall()
            kolonlar = {row[1] for row in cur}
            if "isaret" not in kolonlar:
                c.execute("ALTER TABLE gonderim_log ADD COLUMN isaret TEXT")
            if "not_metni" not in kolonlar:
                c.execute("ALTER TABLE gonderim_log ADD COLUMN not_metni TEXT")

            # Migration: mesaj_kuyrugu için hasta istatistik kolonları
            cur2 = c.execute("PRAGMA table_info(mesaj_kuyrugu)").fetchall()
            mk_kolonlar = {row[1] for row in cur2}
            for kol, tip in [
                ("tckn", "TEXT"),
                ("toplam_ziyaret", "INTEGER"),
                ("son_ziyaret", "TEXT"),
                ("takipli", "INTEGER DEFAULT 0"),
            ]:
                if kol not in mk_kolonlar:
                    c.execute(f"ALTER TABLE mesaj_kuyrugu ADD COLUMN {kol} {tip}")

    # -----------------------------------------------------------------
    # Kuyruk işlemleri
    # -----------------------------------------------------------------
    def hasta_mesajlarini_upsert(
        self, hasta_satirlari: List[Dict], ayarlar: HastaTakipAyarlari,
    ) -> int:
        """
        DB tarama sonucunu kuyruğa yazar/günceller.
        Aynı hasta için 'bekliyor' tek kayıt olur; yeni ilaçlar mevcut kayda eklenir.
        """
        if not hasta_satirlari:
            return 0

        # musteri_id bazlı grupla
        gruplu: Dict[int, Dict] = {}
        for s in hasta_satirlari:
            mid = s.get("musteri_id")
            if not mid:
                continue
            g = gruplu.setdefault(mid, {
                "musteri_id": mid,
                "hasta_adi": s.get("hasta_adi") or "",
                "cep_tel": (s.get("cep_tel") or "").strip(),
                "tckn": (s.get("tckn") or "").strip(),
                "toplam_ziyaret": s.get("toplam_ziyaret"),
                "son_ziyaret": str(s.get("son_ziyaret") or "")[:10],
                "takipli": 1 if s.get("takipli") else 0,
                "ilaclar": [],
            })
            g["ilaclar"].append({
                "urun_adi": s.get("urun_adi"),
                "bitis_tarihi": str(s.get("bitis_tarihi") or ""),
                "yazdirma_tarihi": str(s.get("yazdirma_tarihi") or ""),
                "kaynak": s.get("kaynak"),
                "kac_gun_kaldi": s.get("kac_gun_kaldi"),
            })

        planli = self._planli_gonderim_tarihi(ayarlar)
        simdi = datetime.now().isoformat(timespec="seconds")

        yeni = 0
        with self._conn() as c:
            for mid, g in gruplu.items():
                row = c.execute(
                    "SELECT id, ilac_json FROM mesaj_kuyrugu "
                    "WHERE musteri_id=? AND durum='bekliyor'",
                    (mid,),
                ).fetchone()

                if row is None:
                    c.execute(
                        "INSERT INTO mesaj_kuyrugu(musteri_id, hasta_adi, cep_tel, "
                        "tckn, toplam_ziyaret, son_ziyaret, takipli, "
                        "ilac_json, olusturma, planli_gonderim, durum) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?, 'bekliyor')",
                        (mid, g["hasta_adi"], g["cep_tel"],
                         g["tckn"], g["toplam_ziyaret"], g["son_ziyaret"], g["takipli"],
                         json.dumps(g["ilaclar"], ensure_ascii=False),
                         simdi, planli.isoformat()),
                    )
                    yeni += 1
                else:
                    mevcut = json.loads(row["ilac_json"])
                    anahtar = {i.get("urun_adi") for i in mevcut}
                    eklendi = False
                    for il in g["ilaclar"]:
                        if il.get("urun_adi") not in anahtar:
                            mevcut.append(il)
                            eklendi = True
                    # İstatistikleri her tarama sonunda güncelle
                    c.execute(
                        "UPDATE mesaj_kuyrugu SET ilac_json=?, planli_gonderim=?, "
                        "tckn=?, toplam_ziyaret=?, son_ziyaret=?, takipli=? "
                        "WHERE id=?",
                        (json.dumps(mevcut, ensure_ascii=False),
                         planli.isoformat(),
                         g["tckn"], g["toplam_ziyaret"], g["son_ziyaret"], g["takipli"],
                         row["id"]),
                    )
        return yeni

    @staticmethod
    def _planli_gonderim_tarihi(ayarlar: HastaTakipAyarlari) -> date:
        """Ayarlara göre bu kuyruk öğesinin gönderim gününü hesapla."""
        bugun = date.today()
        mod = ayarlar.gonderim_modu

        if mod == "anlik":
            return bugun

        if mod == "pazartesi":
            # Bu hafta veya sonraki toplu gönderim günü
            fark = (ayarlar.toplu_gonderim_gunu - bugun.weekday()) % 7
            if fark == 0 and datetime.now().time().hour >= 12:
                fark = 7  # aynı gün öğleden sonraysa haftaya
            return bugun + timedelta(days=fark)

        if mod == "periyodik":
            return bugun + timedelta(days=max(0, ayarlar.periyot_gun - 1))

        return bugun

    def gosterilecek_mesajlar(
        self, ayarlar: HastaTakipAyarlari, bugun: Optional[date] = None,
    ) -> List[Dict]:
        """
        Gönderim penceresi açık mı kontrol et, açıksa bugün gösterilecek
        kuyruk kayıtlarını döndür.
        """
        bugun = bugun or date.today()
        if not self._calisma_saati_mi(ayarlar):
            return []

        with self._conn() as c:
            rows = c.execute(
                "SELECT id, musteri_id, hasta_adi, cep_tel, tckn, "
                "toplam_ziyaret, son_ziyaret, takipli, ilac_json, "
                "olusturma, planli_gonderim "
                "FROM mesaj_kuyrugu "
                "WHERE durum='bekliyor' AND planli_gonderim <= ? "
                "ORDER BY planli_gonderim ASC, hasta_adi ASC",
                (bugun.isoformat(),),
            ).fetchall()

        sonuc: List[Dict] = []
        for r in rows:
            ilaclar = json.loads(r["ilac_json"])
            mesaj = self.mesaj_olustur(r["hasta_adi"], ilaclar, ayarlar)
            son = r["son_ziyaret"]
            gun_once = None
            if son:
                try:
                    g = datetime.strptime(son[:10], "%Y-%m-%d").date()
                    gun_once = (bugun - g).days
                except ValueError:
                    pass
            sonuc.append({
                "kuyruk_id": r["id"],
                "musteri_id": r["musteri_id"],
                "hasta_adi": r["hasta_adi"],
                "cep_tel": r["cep_tel"],
                "tckn": r["tckn"] or "",
                "toplam_ziyaret": r["toplam_ziyaret"],
                "son_ziyaret": son or "",
                "son_gun_once": gun_once,
                "takipli": bool(r["takipli"]),
                "ilaclar": ilaclar,
                "olusturma": r["olusturma"],
                "planli_gonderim": r["planli_gonderim"],
                "mesaj_metni": mesaj,
            })
        return sonuc

    @staticmethod
    def _calisma_saati_mi(ayarlar: HastaTakipAyarlari) -> bool:
        bas = _saat_parse(ayarlar.calisma_baslangic)
        bit = _saat_parse(ayarlar.calisma_bitis)
        if not bas or not bit:
            return True
        now = datetime.now().time()
        return (now.hour, now.minute) >= bas and (now.hour, now.minute) <= bit

    @staticmethod
    def rapor_bitis_mesaji_olustur(
        hasta_adi: str,
        tani_satirlari: List[Dict],
        etkin_maddeler_map: Dict[int, List[Dict]],
        ilaclar_map: Dict[int, List[Dict]],
        ayarlar: HastaTakipAyarlari,
    ) -> str:
        """Bir hasta için rapor bitiş mesajı.

        Args:
            tani_satirlari: yaklasan_rapor_bitisleri sonuçları (bu hastaya ait)
            etkin_maddeler_map: {rapor_id: [etken_madde_dict,...]}
            ilaclar_map: {rapor_id: [ilac_dict,...]}
        """
        satirlar = []
        for t in tani_satirlari:
            rapor_id = t.get("rapor_id")
            em_list = etkin_maddeler_map.get(rapor_id, [])
            il_list = ilaclar_map.get(rapor_id, [])

            em_metin = ", ".join(
                (em.get("etkin_madde") or "").strip()
                for em in em_list if em.get("etkin_madde")
            ) or "—"

            # İlaç listesi: tekil, en güncel olanlar
            gorulen = set()
            il_kisaltilmis = []
            for il in il_list:
                ad = (il.get("urun_adi") or "").strip()
                if ad and ad not in gorulen:
                    gorulen.add(ad)
                    il_kisaltilmis.append(ad)
            il_metin = ", ".join(il_kisaltilmis) if il_kisaltilmis else "—"

            satirlar.append(
                ayarlar.rapor_bitis_tani_satir_formati.format(
                    rapor_kodu=t.get("rapor_kodu") or "",
                    rapor_kod_aciklama=(t.get("rapor_kod_aciklama") or "").strip(),
                    icd_kodu=t.get("icd_kodu") or "",
                    icd_aciklamasi=(t.get("icd_aciklamasi") or "").strip(),
                    baslama=str(t.get("baslama") or "")[:10],
                    bitis=str(t.get("bitis") or "")[:10],
                    kalan_gun=t.get("kalan_gun") if t.get("kalan_gun") is not None else "",
                    etkin_maddeler=em_metin,
                    ilaclar=il_metin,
                )
            )

        rapor_listesi = "\n".join(satirlar)
        return ayarlar.rapor_bitis_mesaj_sablonu.format(
            hasta_adi=hasta_adi or "",
            rapor_listesi=rapor_listesi,
            eczane_adi=ayarlar.eczane_adi,
            eczane_tel=ayarlar.eczane_tel,
        )

    @staticmethod
    def mesaj_olustur(
        hasta_adi: str, ilaclar: List[Dict], ayarlar: HastaTakipAyarlari,
    ) -> str:
        """Ayarlar.mesaj_sablonu + her ilaç için satır formatı."""
        satirlar = []
        for il in ilaclar:
            satir = ayarlar.ilac_satir_formati.format(**{
                "urun_adi": il.get("urun_adi") or "",
                "bitis_tarihi": il.get("bitis_tarihi") or "",
                "yazdirma_tarihi": il.get("yazdirma_tarihi") or "",
                "kaynak": il.get("kaynak") or "",
            })
            satirlar.append(satir)

        ilac_listesi = "\n".join(satirlar)
        return ayarlar.mesaj_sablonu.format(
            hasta_adi=hasta_adi or "",
            ilac_listesi=ilac_listesi,
            eczane_adi=ayarlar.eczane_adi,
            eczane_tel=ayarlar.eczane_tel,
        )

    def gonderildi_isaretle(self, kuyruk_id: int, sonuc: str = "OK") -> None:
        simdi = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            row = c.execute(
                "SELECT musteri_id, hasta_adi, cep_tel, ilac_json "
                "FROM mesaj_kuyrugu WHERE id=?",
                (kuyruk_id,),
            ).fetchone()
            if row is None:
                return
            c.execute(
                "UPDATE mesaj_kuyrugu SET durum='gonderildi' WHERE id=?",
                (kuyruk_id,),
            )
            c.execute(
                "INSERT INTO gonderim_log(musteri_id, hasta_adi, cep_tel, "
                "mesaj_metni, zaman, sonuc) VALUES (?,?,?,?,?,?)",
                (row["musteri_id"], row["hasta_adi"], row["cep_tel"],
                 row["ilac_json"], simdi, sonuc),
            )

    def iptal_et(self, kuyruk_id: int) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE mesaj_kuyrugu SET durum='iptal' WHERE id=?",
                (kuyruk_id,),
            )

    def kuyrukta_bekleyen_sayisi(self) -> int:
        with self._conn() as c:
            r = c.execute(
                "SELECT COUNT(*) AS n FROM mesaj_kuyrugu WHERE durum='bekliyor'"
            ).fetchone()
            return int(r["n"]) if r else 0

    def log_getir(self, limit: int = 500) -> List[Dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM gonderim_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def log_isaret_guncelle(self, log_id: int, isaret: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE gonderim_log SET isaret=? WHERE id=?",
                (isaret, log_id),
            )

    def log_not_guncelle(self, log_id: int, not_metni: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE gonderim_log SET not_metni=? WHERE id=?",
                (not_metni, log_id),
            )
