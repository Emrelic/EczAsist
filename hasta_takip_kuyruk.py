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

    # Sadece raporlu ilaçlar (raporsuz ilaçlar listelenmez — istisnalar hariç)
    sadece_raporlu: bool = True

    # Raporsuz olsa bile listelenecek ürün kimlikleri (Urun.UrunId listesi)
    raporsuz_istisna_urunler: list = field(default_factory=list)

    # Raporsuz olsa bile takip edilecek ilaç kategorileri (isim anahtar kelimesi)
    # Her kategori açıkken, ilaç adında anahtar kelime geçenler raporsuz olsa
    # da listeye dahil edilir.
    kategori_takibi: dict = field(default_factory=lambda: {
        "b12_vitamini": False,
        "d_vitamini": False,
        "mide_ilaclari": False,
        "demir": False,
        "magnezyum": False,
        "hemoroid": False,
        "hormonlar": False,
        "ozel": False,   # Kullanıcı tanımlı anahtar listesi
    })
    # Özel kategori için kullanıcı tanımlı anahtar kelimeler (virgülle ayrılmış)
    # Örn: "KREATIN, OMEGA 3, ASPIRIN" — ilaç adında bunlardan biri geçenler
    # raporsuz olsa da listeye dahil edilir.
    kategori_ozel_anahtarlar: str = ""

    # Toplu gönderim (batch) bekleme penceresi. Bugün atılması gereken bir mesaj
    # varsa, bu kadar gün içinde başka ilaç da yazdırılacaksa beraber atmak için
    # mesaj ertelenir. 0 = erteleme yok (anlık gönder). Maksimum bekleme süresi.
    batch_bekleme_gun: int = 5

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
    ilac_satir_formati: str = "{sayi}- {urun_adi}"

    eczane_adi: str = "İKİZLER ECZANESİ"
    eczane_tel: str = "0542 515 74 40"

    # Pazartesi mod için gönderim günü (0=Pazartesi, 6=Pazar)
    toplu_gonderim_gunu: int = 0

    # --- MEDULA oturum canlı tutma ---
    oturum_canli_tut: bool = False

    # --- Tablo sütun görünürlüğü (sekme 1) ---
    # Anahtarlar: planli_tarih, hasta, tc, tel, ilac_sayi, menzil,
    #             ziyaret, son_gelis, gun, takip
    sutun_gorunurlugu: dict = field(default_factory=lambda: {
        "planli_tarih": True,
        "hasta": True,
        "tc": False,
        "tel": False,
        "ilac_sayi": True,
        "menzil": True,
        "ziyaret": True,
        "son_gelis": False,
        "gun": True,
        "takip": False,
    })

    # --- Rapor bitiş takibi ---
    rapor_bitis_uyari_gun: int = 30  # Bu kadar gün kala raporla
    rapor_bitis_mesaj_sablonu: str = (
        "Sayın {hasta_adi}\n"
        "Aşağıdaki raporlarınız yaklaşan tarihlerde bitmektedir:\n\n"
        "{rapor_listesi}\n"
        "Lütfen yenilemek için doktorunuza başvurunuz.\n"
        "{eczane_adi}  {eczane_tel}"
    )
    # Rapor başına bir paragraf. Rapor numarası benzersiz, tanıları virgülle ayrılı.
    rapor_bitis_rapor_formati: str = (
        "• {rapor_ozet} (Bitiş: {bitis} — {kalan_gun} gün kaldı)\n"
        "  Kullandığınız ilaçlar: {ilaclar}\n"
    )
    # (Eski alan geriye-uyum icin korunuyor — yeni akis kullanmaz)
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
            # Eski varsayılan satır formatını yeni numaralı formata migrate et
            if data.get("ilac_satir_formati") == "{urun_adi},":
                data["ilac_satir_formati"] = "{sayi}- {urun_adi}"
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
                # Bekleyen ilaç manuel olarak indirildiyse 1 (açık sarı gösterim)
                ("bekleteni_indirildi", "INTEGER DEFAULT 0"),
            ]:
                if kol not in mk_kolonlar:
                    c.execute(f"ALTER TABLE mesaj_kuyrugu ADD COLUMN {kol} {tip}")

    # -----------------------------------------------------------------
    # Kuyruk işlemleri
    # -----------------------------------------------------------------
    def bekleyen_raporsuz_temizle(self) -> int:
        """Bekleyen kuyruk kayıtlarındaki raporsuz ilaçları Botanik DB'den
        doğrulayarak temizle.

        Geçmiş tarama sadece_raporlu=False iken yapılmışsa kuyruğa raporsuz
        ilaçlar girmiş olabilir. Bu metod her bekleyen kaydın ilac_json'ındaki
        ürünleri Botanik DB'de kontrol eder; rapor_kod_id'si 0/null olanları
        (raporsuz) çıkarır. İlac_json boş kalan kayıtları iptal eder.

        Returns: temizlenen ilaç adedi.
        """
        try:
            from botanik_db import BotanikDB
            bdb = BotanikDB()
            bdb.baglan()
        except Exception as e:
            logger.warning("Raporsuz temizlik: Botanik DB açılamadı: %s", e)
            return 0

        silinen = 0
        bos_kayitlar: list = []
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, musteri_id, ilac_json FROM mesaj_kuyrugu "
                "WHERE durum='bekliyor'"
            ).fetchall()

            for row in rows:
                try:
                    ilaclar = json.loads(row["ilac_json"])
                except Exception:
                    continue
                if not isinstance(ilaclar, list):
                    continue

                kalan: list = []
                degisti = False
                for il in ilaclar:
                    urun_adi = (il.get("urun_adi") or "").strip()
                    if not urun_adi:
                        continue

                    raporlu = self._urun_raporlu_mu(bdb, row["musteri_id"], urun_adi)
                    if raporlu is True:
                        kalan.append(il)
                    elif raporlu is False:
                        silinen += 1
                        degisti = True
                    else:
                        # Bilinmiyor — güvenlik için koru
                        kalan.append(il)

                if not degisti:
                    continue
                if not kalan:
                    bos_kayitlar.append(row["id"])
                else:
                    c.execute(
                        "UPDATE mesaj_kuyrugu SET ilac_json=? WHERE id=?",
                        (json.dumps(kalan, ensure_ascii=False), row["id"]),
                    )

            for kid in bos_kayitlar:
                c.execute("DELETE FROM mesaj_kuyrugu WHERE id=?", (kid,))

        if silinen:
            logger.info(
                "Raporsuz temizlik: %d ilaç silindi, %d boş kayıt kaldırıldı.",
                silinen, len(bos_kayitlar),
            )
        return silinen

    @staticmethod
    def _urun_raporlu_mu(bdb, musteri_id: int, urun_adi: str) -> Optional[bool]:
        """Botanik DB'de (musteri_id + urun_adi) için rapor durumu.
        True=raporlu, False=raporsuz, None=bilinmiyor.
        Hem ReceteIlaclari hem MedulaHastaIlaclari kontrol edilir."""
        try:
            sql = """
            SELECT TOP 1 ri.RIRaporKodId AS rk
            FROM ReceteIlaclari ri
            INNER JOIN ReceteAna ra ON ra.RxId = ri.RIRxId
            LEFT  JOIN Urun      u  ON u.UrunId = ri.RIUrunId
            WHERE ra.RxMusteriId = ?
              AND LTRIM(RTRIM(u.UrunAdi)) = ?
              AND ri.RISilme = 0 AND ra.RxSilme = 0
              AND (ri.RIIade IS NULL OR ri.RIIade = 0)
            ORDER BY ri.RIBitisTarihi DESC
            """
            res = bdb.sorgu_calistir(sql, (musteri_id, urun_adi))
            if res:
                rk = res[0].get("rk")
                try:
                    return int(rk or 0) > 0
                except (TypeError, ValueError):
                    return False

            sql_m = """
            SELECT TOP 1 mhi.RaporKodu AS rk
            FROM MedulaHastaIlaclari mhi
            WHERE mhi.MusteriId = ?
              AND LTRIM(RTRIM(mhi.UrunAdi)) = ?
            ORDER BY mhi.VerilecekTarih DESC
            """
            res = bdb.sorgu_calistir(sql_m, (musteri_id, urun_adi))
            if res:
                rk = res[0].get("rk")
                if rk is None:
                    return False
                if isinstance(rk, str):
                    return bool(rk.strip())
                try:
                    return int(rk) > 0
                except (TypeError, ValueError):
                    return False
        except Exception as e:
            logger.debug("Rapor durumu sorgu hatası (%s, %s): %s", musteri_id, urun_adi, e)
        return None

    def hasta_mesajlarini_upsert(
        self, hasta_satirlari: List[Dict], ayarlar: HastaTakipAyarlari,
    ) -> int:
        """
        DB tarama sonucunu kuyruğa yazar/günceller.
        Aynı hasta için 'bekliyor' tek kayıt olur; yeni ilaçlar mevcut kayda eklenir.
        sadece_raporlu aktifse, tarama öncesi bekleyen kayıtlardaki raporsuz
        ilaçlar Botanik DB üzerinden doğrulanarak temizlenir.
        """
        if ayarlar.sadece_raporlu:
            try:
                self.bekleyen_raporsuz_temizle()
            except Exception as e:
                logger.warning("Raporsuz temizlik başarısız: %s", e)

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

        simdi = datetime.now().isoformat(timespec="seconds")

        yeni = 0
        with self._conn() as c:
            for mid, g in gruplu.items():
                row = c.execute(
                    "SELECT id, ilac_json, "
                    "COALESCE(bekleteni_indirildi, 0) AS bayrak "
                    "FROM mesaj_kuyrugu "
                    "WHERE musteri_id=? AND durum='bekliyor'",
                    (mid,),
                ).fetchone()

                if row is None:
                    planli = self._planli_gonderim_tarihi(ayarlar, g["ilaclar"])
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
                    # SENKRONİZASYON: kuyruk ilaç listesini DB sonucuna göre
                    # yeniden kur (eski/taşıl ilaçlar düşer — örn. hasta yeni
                    # reçeteyle aynı ilacı tekrar almışsa).
                    bayrak = bool(row["bayrak"])
                    bugun_iso = date.today().isoformat()

                    # DB sonucu zaten her (müşteri, ilaç) için son alımı içerir
                    mevcut = list(g["ilaclar"])
                    # Bekleteni indirildi → ileri tarihli ilaçları atla
                    if bayrak:
                        mevcut = [
                            il for il in mevcut
                            if str(il.get("yazdirma_tarihi") or "")[:10] <= bugun_iso
                        ]
                    if bayrak:
                        planli = date.today()
                    else:
                        planli = self._planli_gonderim_tarihi(ayarlar, mevcut)
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
    def _planli_gonderim_tarihi(
        ayarlar: HastaTakipAyarlari,
        ilaclar: Optional[List[Dict]] = None,
    ) -> date:
        """Ayarlara göre bu kuyruk öğesinin gönderim gününü hesapla.

        anlık modda batch_bekleme_gun > 0 ise ilaçların yazdırma tarihlerinden
        batch hesaplanır: en erken ilaçtan itibaren pencere_gun içindeki
        ilaçların beraber atılacağı son gün planlı gönderim tarihidir.
        """
        bugun = date.today()
        mod = ayarlar.gonderim_modu

        if mod == "anlik":
            pencere = getattr(ayarlar, "batch_bekleme_gun", 0) or 0
            if pencere > 0 and ilaclar:
                return MesajKuyrugu._batch_planli_gonderim(ilaclar, bugun, pencere)
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

    @staticmethod
    def _batch_planli_gonderim(
        ilaclar: List[Dict], bugun: date, pencere_gun: int,
    ) -> date:
        """Toplu (batch) gönderim planı.

        En erken yazdırma tarihinden (ya da bugünden, hangisi geç) itibaren
        pencere_gun'luk bir pencere açılır; pencere içindeki ilaçların en geç
        yazdırma tarihi planlı gönderim günü olur. Pencere dışındaki ilaçlar
        (daha uzak tarihliler) bu batch'e dahil edilmez; kendi batch'lerini
        oluştururlar (sonraki tarama döngüsünde).

        Örnek: bugün Perşembe, ilaçlar Perşembe + Salı (5 gün sonra) →
        pencere Perşembe → Salı, planlı = Salı (beraber atılır).
        """
        tarihler: List[date] = []
        for il in ilaclar:
            tstr = str(il.get("yazdirma_tarihi") or "")[:10]
            if not tstr:
                continue
            try:
                tarihler.append(datetime.strptime(tstr, "%Y-%m-%d").date())
            except ValueError:
                continue
        if not tarihler:
            return bugun
        # Pencere BUGÜNDEN itibaren pencere_gun gün açılır. Geçmiş (overdue)
        # ilaçlar zaten "bekliyor" sayılır — pencereyi geriye itmezler. Pencere
        # içindeki en geç yazdırma tarihi batch gönderim günü olur.
        pencere_son = bugun + timedelta(days=pencere_gun)
        pencere_icindekiler = [t for t in tarihler if t <= pencere_son]
        if not pencere_icindekiler:
            return bugun
        # Planlı = pencere içindeki en geç tarih, ama geçmişe gidemez
        return max(bugun, max(pencere_icindekiler))

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

        bugun_iso = bugun.isoformat()
        with self._conn() as c:
            # Ertelenenler (planli_gonderim > bugün) en üstte, ardından
            # atılmaya hazır olanlar (planli_gonderim <= bugün).
            # Her grupta planli_gonderim ASC, aynı tarihte hasta_adi ASC.
            rows = c.execute(
                "SELECT id, musteri_id, hasta_adi, cep_tel, tckn, "
                "toplam_ziyaret, son_ziyaret, takipli, ilac_json, "
                "olusturma, planli_gonderim, "
                "COALESCE(bekleteni_indirildi, 0) AS bekleteni_indirildi "
                "FROM mesaj_kuyrugu "
                "WHERE durum='bekliyor' "
                "ORDER BY "
                "  CASE WHEN planli_gonderim > ? THEN 0 ELSE 1 END ASC, "
                "  planli_gonderim ASC, hasta_adi ASC",
                (bugun_iso,),
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
            planli_str = (r["planli_gonderim"] or "")[:10]
            ertelenen = bool(planli_str) and planli_str > bugun_iso
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
                "ertelenen": ertelenen,
                "bekleteni_indirildi": bool(r["bekleteni_indirildi"]),
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
        """Bir hasta için rapor bitiş mesajı — rapor başına bir paragraf.

        Her rapor (rapor_id) tek bir paragrafta özetlenir. Aynı rapor altındaki
        birden fazla tanı virgülle birleştirilir. "Kullandığınız ilaçlar" kısmı
        önce etken madde bazında hasta ilacından (em['hasta_ilaclari']) derlenir;
        yoksa rapor_no üzerinden eşleşen ilaçlara (ilaclar_map) düşer.
        """
        # Rapor bazında grupla: rapor_id -> {"ozet_set": {(kod, aciklama)},
        #                                   "bitis": en yakın tarih,
        #                                   "kalan": en küçük kalan_gun,
        #                                   "sample": ilk tanı satırı}
        gruplar: Dict[int, Dict] = {}
        for t in tani_satirlari:
            rid = t.get("rapor_id")
            if not rid:
                continue
            g = gruplar.setdefault(rid, {
                "ozet_set": [],        # sıralı ekleme için liste+set
                "ozet_gorulen": set(),
                "bitis": None,
                "kalan": None,
                "sample": t,
            })
            kod = (t.get("rapor_kodu") or "").strip()
            aciklama = (t.get("rapor_kod_aciklama") or "").strip()
            anahtar = (kod, aciklama)
            if anahtar not in g["ozet_gorulen"] and (kod or aciklama):
                g["ozet_gorulen"].add(anahtar)
                g["ozet_set"].append(anahtar)
            bitis = str(t.get("bitis") or "")[:10]
            if bitis and (g["bitis"] is None or bitis < g["bitis"]):
                g["bitis"] = bitis
            kalan = t.get("kalan_gun")
            if kalan is not None and (g["kalan"] is None or kalan < g["kalan"]):
                g["kalan"] = kalan

        # Raporları bitiş tarihine göre sırala
        sirali_rid = sorted(
            gruplar.keys(),
            key=lambda rid: (gruplar[rid]["bitis"] or "9999-12-31"),
        )

        satirlar = []
        for rid in sirali_rid:
            g = gruplar[rid]
            em_list = etkin_maddeler_map.get(rid, [])
            il_list = ilaclar_map.get(rid, [])

            # Kullanılan ilaçlar: önce her etken madde için hastanın ilacı
            gorulen = set()
            ilac_adlari: List[str] = []
            for em in em_list:
                for hi in (em.get("hasta_ilaclari") or []):
                    ad = (hi.get("urun_adi") or "").strip()
                    if ad and ad not in gorulen:
                        gorulen.add(ad)
                        ilac_adlari.append(ad)
            # Fallback: rapor_no bazlı ilaçlar
            if not ilac_adlari:
                for il in il_list:
                    ad = (il.get("urun_adi") or "").strip()
                    if ad and ad not in gorulen:
                        gorulen.add(ad)
                        ilac_adlari.append(ad)
            ilac_metin = ", ".join(ilac_adlari) if ilac_adlari else "—"

            # Rapor özeti: "ICD tanım, ICD tanım"
            ozet_parcalar = []
            for kod, aciklama in g["ozet_set"]:
                if kod and aciklama:
                    ozet_parcalar.append(f"{kod} - {aciklama}")
                else:
                    ozet_parcalar.append(kod or aciklama)
            rapor_ozet = ", ".join(ozet_parcalar) if ozet_parcalar else "—"

            # Güvenli biçimlendirme: eski şablonu kullananlar için fallback
            fmt = getattr(ayarlar, "rapor_bitis_rapor_formati", None) or (
                "• {rapor_ozet} (Bitiş: {bitis} — {kalan_gun} gün kaldı)\n"
                "  Kullandığınız ilaçlar: {ilaclar}\n"
            )
            satirlar.append(fmt.format(
                rapor_ozet=rapor_ozet,
                bitis=g["bitis"] or "",
                kalan_gun=g["kalan"] if g["kalan"] is not None else "",
                ilaclar=ilac_metin,
            ))

        rapor_listesi = "\n".join(satirlar)
        return ayarlar.rapor_bitis_mesaj_sablonu.format(
            hasta_adi=hasta_adi or "",
            rapor_listesi=rapor_listesi,
            eczane_adi=ayarlar.eczane_adi,
            eczane_tel=ayarlar.eczane_tel,
        )

    # mesaj_olustur tarafından eklenen gün etiketlerini eşler:
    # " (bugün)", " (yarın)", " (dün)", " (N gün önce)", " (N gün sonra)"
    _GUN_ETIKET_PAT = None  # lazy init

    @staticmethod
    def gun_etiketlerini_temizle(mesaj: str) -> str:
        """Mesaj metninden pharmacist-only gün etiketlerini çıkar.

        '(bugün)', '(yarın)', '(dün)', '(N gün önce)', '(N gün sonra)' gibi
        parantezli işaretler hasta görmesin diye gönderim öncesi bu fonksiyon
        ile temizlenir. Önizlemede kalmaya devam eder (eczacıya yardımcı).
        """
        import re
        global _GUN_ETIKET_RE
        try:
            re_obj = _GUN_ETIKET_RE  # noqa: F821
        except NameError:
            re_obj = None
        if re_obj is None:
            re_obj = re.compile(
                r"\s*\((?:bugün|yarın|dün|\d+\s+gün\s+(?:önce|sonra))\)"
            )
            globals()["_GUN_ETIKET_RE"] = re_obj
        # Satır sonu virgül kalıntılarını da temizle
        temiz = re_obj.sub("", mesaj or "")
        # Satır içi fazla boşlukları sadece satır sonunda düzelt
        satirlar = [s.rstrip().rstrip(",").rstrip() for s in temiz.splitlines()]
        return "\n".join(satirlar)

    @staticmethod
    def _gun_metni(yazdirma_iso: str, bugun: date) -> str:
        """'bugün', 'yarın', '3 gün sonra', 'dün', '5 gün önce' gibi
        göreceli gün etiketi üret. Hatalı/boş tarih → boş."""
        if not yazdirma_iso:
            return ""
        try:
            d = datetime.strptime(yazdirma_iso[:10], "%Y-%m-%d").date()
        except ValueError:
            return ""
        fark = (d - bugun).days
        if fark == 0:
            return "bugün"
        if fark == 1:
            return "yarın"
        if fark == -1:
            return "dün"
        if fark > 1:
            return f"{fark} gün sonra"
        return f"{-fark} gün önce"

    @staticmethod
    def mesaj_olustur(
        hasta_adi: str, ilaclar: List[Dict], ayarlar: HastaTakipAyarlari,
    ) -> str:
        """Ayarlar.mesaj_sablonu + her ilaç için satır formatı.

        Her ilaç satırının sonuna göreceli gün etiketi eklenir
        (ör. 'DIAMICRON (bugün)', 'BRIMOGUT (yarın)'). Kullanıcı kendi
        ilac_satir_formati'nda {gun_str} placeholder'ı kullanırsa orada basılır;
        yoksa satır sonuna otomatik olarak '({gun_str})' eklenir.
        """
        bugun = date.today()
        sablon = ayarlar.ilac_satir_formati or "{sayi}- {urun_adi}"
        has_gun = "{gun_str}" in sablon
        has_sayi = "{sayi}" in sablon
        satirlar = []
        for idx, il in enumerate(ilaclar, start=1):
            yt = str(il.get("yazdirma_tarihi") or "")[:10]
            gun_str = MesajKuyrugu._gun_metni(yt, bugun)
            try:
                satir = sablon.format(
                    sayi=idx,
                    urun_adi=il.get("urun_adi") or "",
                    bitis_tarihi=il.get("bitis_tarihi") or "",
                    yazdirma_tarihi=il.get("yazdirma_tarihi") or "",
                    kaynak=il.get("kaynak") or "",
                    gun_str=gun_str,
                )
            except (KeyError, IndexError):
                satir = str(il.get("urun_adi") or "")
                if not has_sayi:
                    satir = f"{idx}- {satir}"
            if not has_gun and gun_str:
                satir = f"{satir.rstrip(', ').rstrip()} ({gun_str})"
            satirlar.append(satir)

        ilac_listesi = "\n".join(satirlar)
        return ayarlar.mesaj_sablonu.format(
            hasta_adi=hasta_adi or "",
            ilac_listesi=ilac_listesi,
            eczane_adi=ayarlar.eczane_adi,
            eczane_tel=ayarlar.eczane_tel,
        )

    def gonderildi_isaretle(self, kuyruk_id: int, sonuc: str = "OK") -> None:
        """Kuyruk kaydını 'gonderildi' olarak işaretle.

        Kayıttaki ilac_json'da yazdırma_tarihi > bugün olan ilaçlar varsa
        (mesaja alınmamış ileri tarihli ilaçlar), onlar YENİ bir 'bekliyor'
        kaydına aktarılır. Böylece bu batch gönderildikten sonra ileri tarihli
        ilaçlar kaybolmaz, bir sonraki batch döngüsünde mesajlanır.
        """
        simdi = datetime.now().isoformat(timespec="seconds")
        bugun_iso = date.today().isoformat()
        with self._conn() as c:
            row = c.execute(
                "SELECT musteri_id, hasta_adi, cep_tel, tckn, toplam_ziyaret, "
                "son_ziyaret, takipli, ilac_json, planli_gonderim "
                "FROM mesaj_kuyrugu WHERE id=?",
                (kuyruk_id,),
            ).fetchone()
            if row is None:
                return

            try:
                ilaclar = json.loads(row["ilac_json"]) or []
            except Exception:
                ilaclar = []

            gonderilen = [i for i in ilaclar
                          if not (str(i.get("yazdirma_tarihi") or "")[:10] > bugun_iso)]
            ileri = [i for i in ilaclar
                     if str(i.get("yazdirma_tarihi") or "")[:10] > bugun_iso]

            # Gönderilecek mesaj metnine sadece gönderilenleri koymak için
            # ilac_json'u güncelle.
            c.execute(
                "UPDATE mesaj_kuyrugu SET ilac_json=?, durum='gonderildi' "
                "WHERE id=?",
                (json.dumps(gonderilen, ensure_ascii=False), kuyruk_id),
            )
            c.execute(
                "INSERT INTO gonderim_log(musteri_id, hasta_adi, cep_tel, "
                "mesaj_metni, zaman, sonuc) VALUES (?,?,?,?,?,?)",
                (row["musteri_id"], row["hasta_adi"], row["cep_tel"],
                 json.dumps(gonderilen, ensure_ascii=False), simdi, sonuc),
            )

            # İleri tarihli ilaçları yeni bir 'bekliyor' kaydı olarak aktar
            if ileri:
                # Yeni planlı: ileri tarihli ilaçlar kendi batch'lerini oluştursun.
                # Burada dataclass ayarına erişimimiz yok — varsayılan 5 günlük
                # pencere ile hesapla (gerçek değer bir sonraki upsert taramasında
                # zaten yeniden hesaplanacak).
                from datetime import timedelta
                tarihler = []
                for il in ileri:
                    t = str(il.get("yazdirma_tarihi") or "")[:10]
                    try:
                        tarihler.append(datetime.strptime(t, "%Y-%m-%d").date())
                    except Exception:
                        pass
                if tarihler:
                    baslangic = min(tarihler)
                    pencere_son = baslangic + timedelta(days=5)
                    pencere_ici = [t for t in tarihler if t <= pencere_son]
                    yeni_planli = max(pencere_ici) if pencere_ici else baslangic
                    yeni_planli = max(date.today(), yeni_planli)
                else:
                    yeni_planli = date.today()
                c.execute(
                    "INSERT INTO mesaj_kuyrugu(musteri_id, hasta_adi, cep_tel, "
                    "tckn, toplam_ziyaret, son_ziyaret, takipli, "
                    "ilac_json, olusturma, planli_gonderim, durum) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?, 'bekliyor')",
                    (row["musteri_id"], row["hasta_adi"], row["cep_tel"],
                     row["tckn"], row["toplam_ziyaret"], row["son_ziyaret"],
                     row["takipli"],
                     json.dumps(ileri, ensure_ascii=False),
                     simdi, yeni_planli.isoformat()),
                )

    def bekleteni_indir(self, kuyruk_id: int) -> int:
        """Kayıttan ileri tarihli (bekleten) ilaçları çıkar.

        "Otobüsten yolcu indirme": yazdırma_tarihi > bugün olan ilaçlar bu
        kayıttan silinir, planli_gonderim bugün'e çekilir, bekleteni_indirildi
        bayrağı açılır (ekranda açık sarı gösterilir). Silinen ilaçlar sonraki
        taramalarda bayrak korunurken yeniden eklenmez — kayıt 'gonderildi'
        veya 'iptal' olduktan sonra sonraki taramada doğal olarak tekrar
        kuyruğa girerler.

        Dönüş: indirilen ilaç sayısı. 0 ise indirilecek ileri tarihli ilaç yok.
        """
        bugun_iso = date.today().isoformat()
        with self._conn() as c:
            row = c.execute(
                "SELECT ilac_json FROM mesaj_kuyrugu WHERE id=?",
                (kuyruk_id,),
            ).fetchone()
            if row is None:
                return 0
            try:
                ilaclar = json.loads(row["ilac_json"]) or []
            except Exception:
                return 0
            kalan = [i for i in ilaclar
                     if str(i.get("yazdirma_tarihi") or "")[:10] <= bugun_iso]
            indirilen = [i for i in ilaclar
                         if str(i.get("yazdirma_tarihi") or "")[:10] > bugun_iso]
            if not indirilen:
                return 0
            if not kalan:
                # Tüm ilaçlar ileri tarihli — indirme anlamsız, değişiklik yapma
                return 0
            c.execute(
                "UPDATE mesaj_kuyrugu SET ilac_json=?, planli_gonderim=?, "
                "bekleteni_indirildi=1 WHERE id=?",
                (json.dumps(kalan, ensure_ascii=False), bugun_iso, kuyruk_id),
            )
        return len(indirilen)

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

    def log_getir(
        self,
        limit: int = 500,
        tarih_filtresi: str = "hepsi",  # "bugun" | "hafta" | "ay" | "hepsi"
    ) -> List[Dict]:
        """Gönderim log kayıtlarını getir — opsiyonel tarih filtresi."""
        where = ""
        params: tuple = ()
        if tarih_filtresi == "bugun":
            bugun = date.today().isoformat()
            where = "WHERE substr(zaman,1,10) = ?"
            params = (bugun,)
        elif tarih_filtresi == "hafta":
            baslangic = (date.today() - timedelta(days=6)).isoformat()
            where = "WHERE substr(zaman,1,10) >= ?"
            params = (baslangic,)
        elif tarih_filtresi == "ay":
            baslangic = (date.today() - timedelta(days=29)).isoformat()
            where = "WHERE substr(zaman,1,10) >= ?"
            params = (baslangic,)

        sql = f"SELECT * FROM gonderim_log {where} ORDER BY id DESC LIMIT ?"
        with self._conn() as c:
            rows = c.execute(sql, params + (limit,)).fetchall()
            return [dict(r) for r in rows]

    def log_ozet(self) -> Dict[str, int]:
        """Gönderim log için sayaçlar: toplam, bugün, bu hafta."""
        bugun = date.today().isoformat()
        hafta_bas = (date.today() - timedelta(days=6)).isoformat()
        with self._conn() as c:
            tot = c.execute("SELECT COUNT(*) AS n FROM gonderim_log").fetchone()["n"]
            bug = c.execute(
                "SELECT COUNT(*) AS n FROM gonderim_log WHERE substr(zaman,1,10) = ?",
                (bugun,),
            ).fetchone()["n"]
            haf = c.execute(
                "SELECT COUNT(*) AS n FROM gonderim_log WHERE substr(zaman,1,10) >= ?",
                (hafta_bas,),
            ).fetchone()["n"]
            bug_ok = c.execute(
                "SELECT COUNT(*) AS n FROM gonderim_log WHERE substr(zaman,1,10) = ? AND sonuc = 'OK'",
                (bugun,),
            ).fetchone()["n"]
        return {"toplam": tot, "bugun": bug, "bugun_ok": bug_ok, "hafta": haf}

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
