"""
KDV Analiz Motoru
Botanik EOS veritabanından ay bazında KDV tahmin hesabı yapar.

KDV mevzuatı (Türkiye 2024+):
- %10 Beşeri tıbbi ürünler (ilaç), bazı medikal
- %20 İtriyat, dermokozmetik, parfümeri, kişisel bakım
- %1  Besin takviyesi, mama, bazı yağlar, tıbbi mama
- %0  Bazı medikal cihazlar, muafiyetli kalemler

DB üzerinde her ürünün UrunKDVId alanı KDV tablosunun (KDVId, KDVOran) kaydına işaret eder.
KDVId 1→%10, 2→%20, 3→%1, 4→%0.

Hesaplama mantığı:
- Satış fiyatları KDV DAHİL olarak kayıtlıdır (etiket/kurum fiyatı).
  Matrah = tutar / (1 + oran/100)
  KDV   = tutar - matrah  =  tutar * oran / (100 + oran)
- Alış faturalarındaki KDV doğrudan FGKDVTutar'dan toplanır.
- Ödenecek KDV = Hesaplanan satış KDV - İndirilecek alış KDV.

Fiş kesilmemiş satış tespiti:
- EldenAna kaydı + KesilenFisTakibi(KFTIlgiliTip=2, KFTFisDurumu=1) eşleşmesi yoksa
  → fiş kesilmemiş perakende satış sayılır.
- ReceteAna ve FaturaCikis için bu kontrol yapılmaz (her ikisi de fatura/belge ile çıkar).

KIRMIZI ÇİZGİ: Bu modül salt okuma yapar. Tüm sorgular SELECT. Botanik EOS'a yazma YOKTUR.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from botanik_db import BotanikDB

logger = logging.getLogger(__name__)


@dataclass
class OranOzeti:
    oran: int
    matrah: float = 0.0
    kdv: float = 0.0
    tutar: float = 0.0
    satir_adet: int = 0


@dataclass
class KDVAnalizSonucu:
    yil: int
    ay: Optional[int]  # None = tüm yıl
    elden: Dict[int, OranOzeti] = field(default_factory=dict)
    recete: Dict[int, OranOzeti] = field(default_factory=dict)
    fatura_cikis: Dict[int, OranOzeti] = field(default_factory=dict)
    alim: Dict[int, OranOzeti] = field(default_factory=dict)
    elden_kdvsiz_satir_adet: int = 0
    elden_kdvsiz_tutar: float = 0.0
    recete_kdvsiz_satir_adet: int = 0
    recete_kdvsiz_tutar: float = 0.0
    fis_kesilmis_adet: int = 0
    fis_kesilmis_tutar: float = 0.0
    fis_kesilmemis_adet: int = 0
    fis_kesilmemis_tutar: float = 0.0
    pos_dagilim: Dict[int, Dict] = field(default_factory=dict)
    hata: Optional[str] = None

    @property
    def toplam_satis_matrah(self) -> float:
        return sum(o.matrah for o in self.elden.values()) \
             + sum(o.matrah for o in self.recete.values()) \
             + sum(o.matrah for o in self.fatura_cikis.values())

    @property
    def toplam_satis_tutar(self) -> float:
        return sum(o.tutar for o in self.elden.values()) \
             + sum(o.tutar for o in self.recete.values()) \
             + sum(o.tutar for o in self.fatura_cikis.values())

    @property
    def toplam_hesaplanan_kdv(self) -> float:
        return sum(o.kdv for o in self.elden.values()) \
             + sum(o.kdv for o in self.recete.values()) \
             + sum(o.kdv for o in self.fatura_cikis.values())

    @property
    def toplam_alim_kdv(self) -> float:
        return sum(o.kdv for o in self.alim.values())

    @property
    def toplam_alim_tutar(self) -> float:
        return sum(o.tutar for o in self.alim.values())

    @property
    def odenecek_kdv(self) -> float:
        return self.toplam_hesaplanan_kdv - self.toplam_alim_kdv

    def toplam_oran_matrahlari(self) -> Dict[int, float]:
        """Tüm satış kaynaklarındaki KDV oranı bazlı matrah toplamı."""
        sonuc: Dict[int, float] = {}
        for kaynak in (self.elden, self.recete, self.fatura_cikis):
            for oran, ozet in kaynak.items():
                sonuc[oran] = sonuc.get(oran, 0.0) + ozet.matrah
        return sonuc

    def toplam_oran_kdvleri(self) -> Dict[int, float]:
        sonuc: Dict[int, float] = {}
        for kaynak in (self.elden, self.recete, self.fatura_cikis):
            for oran, ozet in kaynak.items():
                sonuc[oran] = sonuc.get(oran, 0.0) + ozet.kdv
        return sonuc


def _ay_aralik(yil: int, ay: Optional[int]) -> tuple:
    """ay=None ise tüm yıl (01.01 - 01.01 sonraki yıl), aksi halde tek ay."""
    if ay is None:
        bas = date(yil, 1, 1)
        bit = date(yil + 1, 1, 1)
    else:
        bas = date(yil, ay, 1)
        bit_yil = yil + (1 if ay == 12 else 0)
        bit_ay = 1 if ay == 12 else ay + 1
        bit = date(bit_yil, bit_ay, 1)
    return bas.strftime("%Y-%m-%d"), bit.strftime("%Y-%m-%d")


def _bos_ozet_dict() -> Dict[int, OranOzeti]:
    return {o: OranOzeti(oran=o) for o in (0, 1, 10, 20)}


def kdv_analiz_yap(yil: int, ay: Optional[int]) -> KDVAnalizSonucu:
    """
    Verilen dönem için KDV analizini hesaplar.
    ay=None  -> tüm yıl (01.01 - 31.12)
    ay=1..12 -> tek ay
    Tek bir BotanikDB bağlantısı üzerinden çalışır.
    """
    sonuc = KDVAnalizSonucu(yil=yil, ay=ay)
    sonuc.elden = _bos_ozet_dict()
    sonuc.recete = _bos_ozet_dict()
    sonuc.fatura_cikis = _bos_ozet_dict()
    sonuc.alim = _bos_ozet_dict()

    bas_str, bit_str = _ay_aralik(yil, ay)

    db = BotanikDB()
    if not db.baglan():
        sonuc.hata = "Veritabanına bağlanılamadı"
        return sonuc

    try:
        _elden_satislari_topla(db, bas_str, bit_str, sonuc)
        _recete_satislari_topla(db, bas_str, bit_str, sonuc)
        _fatura_cikis_topla(db, bas_str, bit_str, sonuc)
        _alim_faturalarini_topla(db, bas_str, bit_str, sonuc)
        _fis_kesilmis_durumunu_hesapla(db, bas_str, bit_str, sonuc)
        _pos_dagilimini_hesapla(db, bas_str, bit_str, sonuc)
    except Exception as e:
        logger.error("KDV analiz hatası: %s", e, exc_info=True)
        sonuc.hata = str(e)
    finally:
        db.kapat()

    return sonuc


def _ekle(oz: Dict[int, OranOzeti], oran: Optional[int], tutar: float,
          satir: int = 1, kdv_dahil: bool = True):
    """
    Bir oran grubuna kayıt ekler.
    kdv_dahil=True  -> tutar KDV dahildir; matrah = tutar/(1+oran/100)  [satışlar]
    kdv_dahil=False -> tutar KDV hariçtir;  matrah = tutar, kdv = tutar*oran/100 [alışlar]
    """
    if oran is None or oran < 0:
        oran = 0
    if oran not in oz:
        oz[oran] = OranOzeti(oran=oran)
    o = oz[oran]
    o.tutar += tutar
    if oran > 0:
        if kdv_dahil:
            matrah = tutar / (1.0 + oran / 100.0)
            o.matrah += matrah
            o.kdv += tutar - matrah
        else:
            o.matrah += tutar
            o.kdv += tutar * oran / 100.0
    else:
        o.matrah += tutar
    o.satir_adet += satir


def _elden_satislari_topla(db: BotanikDB, bas: str, bit: str, sonuc: KDVAnalizSonucu):
    sql = f"""
    SELECT
        ei.RIToplam AS Tutar,
        k.KDVOran AS KdvOran,
        u.UrunKDVId AS KdvId
    FROM EldenAna ea
    JOIN EldenIlaclari ei ON ea.RxId = ei.RIRxId
    JOIN Urun u ON ei.RIUrunId = u.UrunId
    LEFT JOIN KDV k ON u.UrunKDVId = k.KDVId
    WHERE ea.RxSilme = 0 AND ei.RISilme = 0
      AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
      AND CAST(ea.RxIslemTarihi AS date) >= '{bas}'
      AND CAST(ea.RxIslemTarihi AS date) <  '{bit}'
    """
    for satir in db.sorgu_calistir(sql):
        tutar = float(satir.get("Tutar") or 0)
        if tutar <= 0:
            continue
        oran = satir.get("KdvOran")
        if oran is None:
            sonuc.elden_kdvsiz_satir_adet += 1
            sonuc.elden_kdvsiz_tutar += tutar
        _ekle(sonuc.elden, oran, tutar)


def _recete_satislari_topla(db: BotanikDB, bas: str, bit: str, sonuc: KDVAnalizSonucu):
    """
    Reçeteli satışlarda kuruma satış için RIKurumFiyati + RIFiyatFarki, hastadan
    alınan ek için RIIskonto gibi alanlar kullanılır.
    Eczanenin toplam satış cirosu RIToplam (kurum + hasta toplamı) olarak alınır.
    """
    sql = f"""
    SELECT
        ri.RIToplam AS Tutar,
        k.KDVOran AS KdvOran,
        u.UrunKDVId AS KdvId
    FROM ReceteAna ra
    JOIN ReceteIlaclari ri ON ra.RxId = ri.RIRxId
    JOIN Urun u ON ri.RIUrunId = u.UrunId
    LEFT JOIN KDV k ON u.UrunKDVId = k.KDVId
    WHERE ra.RxSilme = 0 AND ri.RISilme = 0
      AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
      AND CAST(ra.RxIslemTarihi AS date) >= '{bas}'
      AND CAST(ra.RxIslemTarihi AS date) <  '{bit}'
    """
    for satir in db.sorgu_calistir(sql):
        tutar = float(satir.get("Tutar") or 0)
        if tutar <= 0:
            continue
        oran = satir.get("KdvOran")
        if oran is None:
            sonuc.recete_kdvsiz_satir_adet += 1
            sonuc.recete_kdvsiz_tutar += tutar
        _ekle(sonuc.recete, oran, tutar)


def _fatura_cikis_topla(db: BotanikDB, bas: str, bit: str, sonuc: KDVAnalizSonucu):
    """
    FaturaCikis: ReceteAna dışı manuel kurum/perakende faturaları.
    Satır bazında KDV oranı FaturaCikisSatir'da yoksa Urun.UrunKDVId üzerinden alınır.
    """
    sql = f"""
    SELECT
        fcs.FSUrunAdet * fcs.FSBirimFiyat AS Tutar,
        k.KDVOran AS KdvOran
    FROM FaturaCikis fc
    JOIN FaturaCikisSatir fcs ON fc.FGId = fcs.FSFGId
    JOIN Urun u ON fcs.FSUrunId = u.UrunId
    LEFT JOIN KDV k ON u.UrunKDVId = k.KDVId
    WHERE CAST(fc.FGFaturaTarihi AS date) >= '{bas}'
      AND CAST(fc.FGFaturaTarihi AS date) <  '{bit}'
    """
    for satir in db.sorgu_calistir(sql):
        tutar = float(satir.get("Tutar") or 0)
        if tutar <= 0:
            continue
        _ekle(sonuc.fatura_cikis, satir.get("KdvOran"), tutar)


def _alim_faturalarini_topla(db: BotanikDB, bas: str, bit: str, sonuc: KDVAnalizSonucu):
    """
    İki adımda hesaplanır:

    1) Fatura başlık seviyesi (KESİN rakam): FaturaGiris.FGToplamTutar ve FGKDVTutar
       toplamları alınır. Bu Botanik'in muhasebesindeki gerçek alış tutarı + indirilecek
       KDV'dir. Toplam matrah ve toplam KDV bunlardan üretilir.

    2) Satır seviyesi (oran DAĞILIMI için): FaturaSatir.FSKDVId + FSMaliyet × adet
       ağırlık olarak kullanılır. Her oran grubu fatura toplam matrahının kendi
       payına orantılı olarak doldurulur. Bu sayede oran dökümünün toplamı fatura
       seviyesindeki KESİN matrah/KDV'ye eşit kalır.
    """
    # 1) Fatura başlık toplamı
    sql_fatura = f"""
    SELECT
        SUM(fg.FGToplamTutar) AS ToplamTutar,
        SUM(fg.FGKDVTutar) AS ToplamKdv
    FROM FaturaGiris fg
    WHERE fg.FGFaturaTarihi >= '{bas}'
      AND fg.FGFaturaTarihi <  '{bit}'
    """
    r = db.sorgu_calistir(sql_fatura)
    if not r or not r[0]:
        return
    toplam_tutar_kdv_dahil = float(r[0].get("ToplamTutar") or 0)
    toplam_kdv = float(r[0].get("ToplamKdv") or 0)
    if toplam_tutar_kdv_dahil <= 0:
        return
    toplam_matrah = toplam_tutar_kdv_dahil - toplam_kdv

    # 2) Satır seviyesi oran ağırlığı (FSMaliyet × adet'i pay olarak kullan)
    sql_satir = f"""
    SELECT
        k.KDVOran AS KdvOran,
        SUM(fs.FSUrunAdet * fs.FSMaliyet) AS AgirlikTutar,
        COUNT(*) AS SatirAdet
    FROM FaturaGiris fg
    JOIN FaturaSatir fs ON fg.FGId = fs.FSFGId
    LEFT JOIN KDV k ON fs.FSKDVId = k.KDVId
    WHERE fg.FGFaturaTarihi >= '{bas}'
      AND fg.FGFaturaTarihi <  '{bit}'
    GROUP BY k.KDVOran
    """
    satir_sonuc = db.sorgu_calistir(sql_satir)
    # Ağırlıklı matrah/KDV pay et: matrahı oran ağırlığına ve KDV'yi
    # (matrah × oran) ağırlığına göre dağıt. Bu sayede:
    #  - sum(matrah_grup) = toplam_matrah
    #  - sum(kdv_grup)    = toplam_kdv (gerçek FGKDVTutar)
    matrah_agirlik = {}
    kdv_agirlik = {}
    satir_adetleri = {}
    for s in satir_sonuc:
        oran = s.get("KdvOran")
        if oran is None or oran < 0:
            oran = 0
        ag = float(s.get("AgirlikTutar") or 0)
        if ag <= 0:
            continue
        matrah_agirlik[oran] = matrah_agirlik.get(oran, 0) + ag
        kdv_agirlik[oran] = kdv_agirlik.get(oran, 0) + ag * oran  # oran * ag = göreli KDV
        satir_adetleri[oran] = satir_adetleri.get(oran, 0) + int(s.get("SatirAdet") or 0)

    matrah_ag_top = sum(matrah_agirlik.values()) or 1.0
    kdv_ag_top = sum(kdv_agirlik.values()) or 1.0

    for oran, ag in matrah_agirlik.items():
        if oran not in sonuc.alim:
            sonuc.alim[oran] = OranOzeti(oran=oran)
        o = sonuc.alim[oran]
        pay_matrah = toplam_matrah * (ag / matrah_ag_top)
        pay_kdv = toplam_kdv * (kdv_agirlik.get(oran, 0) / kdv_ag_top) if kdv_ag_top else 0
        o.matrah += pay_matrah
        o.kdv += pay_kdv
        o.tutar += pay_matrah + pay_kdv
        o.satir_adet += satir_adetleri.get(oran, 0)


def _fis_kesilmis_durumunu_hesapla(db: BotanikDB, bas: str, bit: str, sonuc: KDVAnalizSonucu):
    sql = f"""
    SELECT
        ea.RxId,
        ISNULL(SUM(ei.RIToplam), 0) AS Tutar,
        MAX(CASE WHEN kft.KFTIlgiliId IS NULL THEN 0 ELSE 1 END) AS FisVar
    FROM EldenAna ea
    LEFT JOIN EldenIlaclari ei ON ea.RxId = ei.RIRxId AND ei.RISilme = 0
    LEFT JOIN KesilenFisTakibi kft
        ON ea.RxId = kft.KFTIlgiliId AND kft.KFTIlgiliTip = 2 AND kft.KFTFisDurumu = 1
    WHERE ea.RxSilme = 0
      AND CAST(ea.RxIslemTarihi AS date) >= '{bas}'
      AND CAST(ea.RxIslemTarihi AS date) <  '{bit}'
    GROUP BY ea.RxId
    """
    for satir in db.sorgu_calistir(sql):
        tutar = float(satir.get("Tutar") or 0)
        if satir.get("FisVar"):
            sonuc.fis_kesilmis_adet += 1
            sonuc.fis_kesilmis_tutar += tutar
        else:
            sonuc.fis_kesilmemis_adet += 1
            sonuc.fis_kesilmemis_tutar += tutar


def _pos_dagilimini_hesapla(db: BotanikDB, bas: str, bit: str, sonuc: KDVAnalizSonucu):
    """
    PosTahsilat: belge tipine göre ne kadar POS girişi var.
    PTIlgiliTipi: 1=Reçete, 2=Elden, 3=FaturaCikis, 99=Diğer.
    """
    sql = f"""
    SELECT PTIlgiliTipi AS Tip, COUNT(*) AS Adet, SUM(PTTahsilatTutari) AS Tutar
    FROM PosTahsilat
    WHERE ISNULL(PTSilme, 0) = 0
      AND CAST(PTTahsilatTarihi AS date) >= '{bas}'
      AND CAST(PTTahsilatTarihi AS date) <  '{bit}'
    GROUP BY PTIlgiliTipi
    """
    tip_adi = {1: "Reçete", 2: "Elden", 3: "Fatura Çıkış", 99: "Diğer"}
    for satir in db.sorgu_calistir(sql):
        tip = satir.get("Tip")
        sonuc.pos_dagilim[tip] = {
            "ad": tip_adi.get(tip, f"Tip {tip}"),
            "adet": int(satir.get("Adet") or 0),
            "tutar": float(satir.get("Tutar") or 0),
        }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    yil = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    ay_arg = sys.argv[2] if len(sys.argv) > 2 else "5"
    ay = None if ay_arg.lower() in ("tum", "tumu", "all", "0", "*") else int(ay_arg)

    donem_etiket = f"{yil} (tüm yıl)" if ay is None else f"{yil}-{ay:02d}"
    print(f"\n=== KDV ANALİZİ {donem_etiket} ===\n")
    s = kdv_analiz_yap(yil, ay)
    if s.hata:
        print("HATA:", s.hata)
        sys.exit(1)

    def yazdir_grup(ad: str, grup: Dict[int, OranOzeti]):
        print(f"\n--- {ad} ---")
        for oran in sorted(grup.keys()):
            o = grup[oran]
            if o.tutar == 0:
                continue
            print(f"  KDV %{oran:>3} | tutar={o.tutar:>14,.2f} | matrah={o.matrah:>14,.2f} | kdv={o.kdv:>12,.2f} | satir={o.satir_adet}")

    yazdir_grup("Elden Satışlar", s.elden)
    yazdir_grup("Reçeteli Satışlar", s.recete)
    yazdir_grup("Fatura Çıkış", s.fatura_cikis)
    yazdir_grup("Alım Faturaları (KDV İndirimi)", s.alim)

    print("\n--- ÖZET ---")
    print(f"  Toplam Satış Tutarı (KDV dahil) : {s.toplam_satis_tutar:>14,.2f} TL")
    print(f"  Toplam Satış Matrahı            : {s.toplam_satis_matrah:>14,.2f} TL")
    print(f"  Hesaplanan KDV (satış)          : {s.toplam_hesaplanan_kdv:>14,.2f} TL")
    print(f"  İndirilecek KDV (alış)          : {s.toplam_alim_kdv:>14,.2f} TL")
    print(f"  ÖDENECEK KDV (tahmini)          : {s.odenecek_kdv:>14,.2f} TL")

    print("\n--- ORAN BAZLI MATRAH ---")
    for oran, m in sorted(s.toplam_oran_matrahlari().items()):
        kdv = s.toplam_oran_kdvleri().get(oran, 0)
        print(f"  %{oran:>3} | matrah={m:>14,.2f} | kdv={kdv:>12,.2f}")

    print("\n--- FİŞ DURUMU (Elden) ---")
    print(f"  Fiş kesilmiş   : {s.fis_kesilmis_adet:>5} adet | {s.fis_kesilmis_tutar:>14,.2f} TL")
    print(f"  Fiş kesilmemiş : {s.fis_kesilmemis_adet:>5} adet | {s.fis_kesilmemis_tutar:>14,.2f} TL")

    print("\n--- POS DAĞILIM ---")
    for tip, d in s.pos_dagilim.items():
        print(f"  {d['ad']:>14} | adet={d['adet']:>4} | tutar={d['tutar']:>14,.2f}")
