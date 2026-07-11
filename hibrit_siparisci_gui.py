"""
Hibrit Siparişçi v2
===================
EczAsist "Sipariş Ver" modülünün ürettiği kesin sipariş listesini
(siparis_db.kesin_siparisler), Fatih Mazı'nın kurulu Siparişçi programının
(%LOCALAPPDATA%\\Siparisci) tarama/kıyas/sepet motoruna enjekte eder.

Nasıl çalışır?
--------------
Fatih'in `MainController.run_fast_scan()` akışı Botanik EOS'a yalnızca
`self.botanik` (BotanikEOSController) nesnesi üzerinden dokunur. Hibrit,
bu nesneyi `SanalBotanik` ile değiştirir:

- `get_all_products_data_only()` Botanik penceresini okumak yerine bizim
  kesin sipariş listemizi ürün ürün akıtır (depo araması paralel başlar).
- `calculate_order_quantity()` bizim belirlediğimiz miktarı döndürür
  (Fatih'in Ort/MinStk hesabı devreye girmez).
- Tüm yazma metotları (set_adet/mf/aciklama/tevzi) no-op'tur: Botanik'e
  TEK DOKUNUŞ yapılmaz — Botanik'in açık olması bile gerekmez.

Böylece Fatih'in dosyalarına dokunulmaz (otomatik güncelleme onun kurulu
kodunu her an değiştirebilir); depo kıyası, en kârlı depo seçimi, oto-sepet
ve onun tanıdık arayüzü sıfır değişiklikle bizim listeyle çalışır.

Ayrı süreç olarak çalışır (kendi Tk mainloop'u):
    pythonw hibrit_siparisci_gui.py

Güvenlik:
- Fatih'in kendi tek-örnek mutex'i (BotSiparis_Siparisci_SingleInstance)
  alınır: Siparişçi zaten açıksa hibrit başlamaz (aynı Chrome profillerini
  paylaştıkları için ikisi aynı anda ÇALIŞAMAZ); hibrit açıkken de
  Siparişçi açılmaz.
- Sürüm kontrolü: kurulu sürüm TEST_EDILEN_SURUM'den farklıysa uyarı
  gösterilir ama çalışma engellenmez.
"""

import os
import re
import sys
import json
import ctypes
import logging
import traceback
from pathlib import Path

ECZASIST_DIZIN = Path(__file__).resolve().parent
SIPARISCI_DIZIN = Path(os.environ.get("LOCALAPPDATA", "")) / "Siparisci"

# Adaptörün birebir doğrulandığı Siparişçi sürümü (src/surum.py:SURUM_TAM).
# Yeni sürümde ürün dict alanları / MainController imzaları değişmiş olabilir.
# Sürüm geçmişi: 1.8 → 1.13 (2026-07-04) → 1.22 (2026-07-11). Her seferinde
# aynı doğrulama seti uygulandı: botanik.* yüzey grep'i (28 kullanım, yeni
# metot yok), get_all_products_data_only imzası, on_product_read(product,
# idx, total) sözleşmesi, adet=max(siparis_adet,min_adet) semantiği,
# bul_en_karli_secenek anahtarları, "MM.YY" ay formatı, mutex adı —
# hepsi değişmemiş; duman testi (gerçek EOS kırılım turu dahil) PASS.
TEST_EDILEN_SURUM = "1.22"

# Fatih'in Siparisci.pyw'sindeki tek-örnek mutex'i ile AYNI ad (bilinçli):
# hibrit bu kilidi alınca gerçek Siparişçi açılmaz, o açıkken hibrit açılmaz.
MUTEX_ADI = "BotSiparis_Siparisci_SingleInstance"
_MUTEX = None  # GC kapatmasın diye süreç boyunca global tutulur

logger = logging.getLogger("hibrit_siparisci")


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────────────────────────────────────

def _tek_ornek_kilidi_al() -> bool:
    """Mutex'i almayı dene. False dönerse Siparişçi/hibrit zaten açık."""
    global _MUTEX
    try:
        kernel32 = ctypes.windll.kernel32
        _MUTEX = kernel32.CreateMutexW(None, False, MUTEX_ADI)
        ERROR_ALREADY_EXISTS = 183
        return kernel32.GetLastError() != ERROR_ALREADY_EXISTS
    except Exception:
        return True  # kontrol yapılamazsa kullanıcıyı kilitleme


def _hata_kutusu(baslik: str, mesaj: str):
    import tkinter as tk
    from tkinter import messagebox
    kok = tk.Tk()
    kok.withdraw()
    messagebox.showerror(baslik, mesaj)
    kok.destroy()


def _kesin_liste_yukle():
    """EczAsist SQLite'ından aktif çalışmanın kesin siparişlerini getir."""
    if str(ECZASIST_DIZIN) not in sys.path:
        sys.path.insert(0, str(ECZASIST_DIZIN))
    from siparis_db import get_siparis_db
    db = get_siparis_db()
    calisma = db.aktif_calisma_getir()
    if not calisma:
        return None, []
    siparisler = db.calisma_siparisleri_getir(calisma["id"]) or []
    return calisma, siparisler


def _urunleri_hazirla(siparisler):
    """kesin_siparisler satırlarını Fatih'in ürün dict formatına çevir.

    Alan sözleşmesi: eos_controller._get_product_data_fast +
    get_all_products_data_only'nin ürettiği şema (row/stok/urun_adi/mf/
    minstk/mevcut_adet/ort/barkod/monthly_sales/mf_info/mevcut_aciklama).

    hibrit_ihtiyac = bizim MIKTAR (ödenecek kutu). Fatih motorunda
    siparis_adet = ödenen adettir; depo MF bedavası üstüne gelir
    (controller._auto_add_to_cart: adet = max(siparis_adet, min_adet)).
    """
    products, barkodsuz = [], []
    row = 0
    for s in siparisler:
        try:
            miktar = int(float(s.get("miktar") or 0))
        except (TypeError, ValueError):
            miktar = 0
        if miktar <= 0:
            continue

        barkod = str(s.get("barkod") or "").strip()
        if barkod.endswith(".0"):
            barkod = barkod[:-2]
        if not barkod or not barkod.replace(" ", "").isdigit():
            barkodsuz.append(str(s.get("urun_adi") or "?"))
            continue

        row += 1
        try:
            toplam = int(float(s.get("toplam") or miktar))
        except (TypeError, ValueError):
            toplam = miktar

        # MF planı ayrıştır ("100+30" → min=100, mf=30). Kalem bazında karma
        # kural (kullanıcı kararı 2026-07-04): plan varsa depo şartlarında
        # önce BİREBİR plan aranır (HibritController.bul_en_karli_secenek);
        # bulunamazsa motor serbest seçer.
        plan_min = plan_mf = None
        m = re.match(r"^\s*(\d+)\s*\+\s*(\d+)\s*$", str(s.get("mf") or ""))
        if m:
            plan_min, plan_mf = int(m.group(1)), int(m.group(2))

        products.append({
            # Fatih şeması (zorunlu alanlar)
            "row": row,
            "barkod": barkod,
            "urun_adi": str(s.get("urun_adi") or "?"),
            "stok": int(float(s.get("stok") or 0)),
            "mf": 0,            # 0 → siparis_adet, calculate_order_quantity'den gelir
            "minstk": 0,
            "mevcut_adet": 0,
            "ort": float(s.get("aylik_ort") or 0),
            "monthly_sales": {},
            "mf_info": None,
            "mevcut_aciklama": "",
            "tarih": "",
            # Hibrit alanları
            "hibrit_urun_id": s.get("urun_id"),     # EOS UrunId (aylık kırılım için)
            "hibrit_ihtiyac": miktar,               # ödenecek kutu (bizim karar)
            "hibrit_mf_plan": str(s.get("mf") or ""),  # bizim MF planı (metin)
            "hibrit_mf_plan_min": plan_min,         # plan: ödenen (100+30 → 100)
            "hibrit_mf_plan_mf": plan_mf,           # plan: bedava (100+30 → 30)
            "hibrit_toplam": toplam,                # miktar + MF bedavası (bilgi)
            "hibrit_db_id": s.get("id"),            # kesin_siparisler.id (geri bildirim)
            "hibrit_kaynak": "EczAsist",
        })
    return products, barkodsuz


def _aylik_kirilim_topla(products):
    """Ürünlerin 13 aylık ay-ay çıkışını Botanik EOS'tan çek (SADECE SELECT).

    Fatih'in mevsim/trend katsayısı (`hesapla_mevsim_katsayisi`) 13 tam aylık
    seri ister (geçen yıl aynı ay + son 12 ay ortalaması). Sipariş Ver'in
    tablosu kullanıcının seçtiği ay sayısıyla sınırlı olduğundan kırılım
    burada, devir anında EOS'tan taze çekilir. Filtreler Sipariş Ver'in
    CikisVerileri CTE'si ile birebir (Reçete+Elden, silme=0, iadeler hariç).

    Erişim yalnız BotanikDB guard'ı üzerinden; EOS erişilemezse sessizce
    vazgeçilir (monthly_sales boş kalır → katsayı nötr 1.0).

    Returns:
        int: kırılımı doldurulan ürün sayısı (0 = EOS yok/veri yok)
    """
    urunlu = [p for p in products if p.get("hibrit_urun_id")]
    if not urunlu:
        return 0
    try:
        from dateutil.relativedelta import relativedelta
        from datetime import datetime
        from botanik_db import BotanikDB

        bugun = datetime.now()
        # 13 kova: bu ay (kısmi) + geriye 12 tam ay; etiket "MM.YY"
        etiketler = []
        for i in range(12, -1, -1):
            t = bugun - relativedelta(months=i)
            etiketler.append((t.year, t.month, f"{t.month:02d}.{t.year % 100:02d}"))
        baslangic = (bugun - relativedelta(months=12)).replace(day=1).strftime("%Y-%m-%d")

        ids = ",".join(str(int(p["hibrit_urun_id"])) for p in urunlu)
        sql = f"""
        ;WITH CikisVerileri AS (
            SELECT ri.RIUrunId as UrunId, ri.RIAdet as Adet,
                   CAST(ra.RxKayitTarihi as date) as Tarih
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
              AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
              AND ra.RxKayitTarihi >= '{baslangic}'
              AND ri.RIUrunId IN ({ids})
            UNION ALL
            SELECT ei.RIUrunId, ei.RIAdet, CAST(ea.RxKayitTarihi as date)
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
              AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
              AND ea.RxKayitTarihi >= '{baslangic}'
              AND ei.RIUrunId IN ({ids})
        )
        SELECT UrunId, YEAR(Tarih) as Yil, MONTH(Tarih) as Ay, SUM(Adet) as Adet
        FROM CikisVerileri
        GROUP BY UrunId, YEAR(Tarih), MONTH(Tarih)
        """
        db = BotanikDB()
        satirlar = db.sorgu_calistir(sql) or []

        # (UrunId, Yil, Ay) → Adet
        adetler = {}
        for r in satirlar:
            adetler[(int(r["UrunId"]), int(r["Yil"]), int(r["Ay"]))] = int(r["Adet"] or 0)

        dolan = 0
        for p in urunlu:
            uid = int(p["hibrit_urun_id"])
            # 13 kovanın hepsi doldurulur (satışsız ay = 0 — ortalamaya girmeli)
            kirilim = {etiket: str(adetler.get((uid, y, m), 0))
                       for (y, m, etiket) in etiketler}
            p["monthly_sales"] = kirilim
            if any(v != "0" for v in kirilim.values()):
                dolan += 1
        logger.info(f"[HİBRİT] 13 aylık kırılım EOS'tan yüklendi: "
                    f"{dolan}/{len(urunlu)} üründe satış verisi var")
        return dolan
    except Exception as e:
        logger.warning(f"[HİBRİT] Aylık kırılım çekilemedi (mevsim katsayısı nötr kalır): {e}")
        return 0


def hibrit_baslat_subprocess(parent=None):
    """Hibrit Siparişçi'yi ayrı süreç olarak başlat (EczAsist içinden çağrılır).

    Sipariş Ver modülündeki "Depolara Gönder" butonu ve ana menü butonu bu
    ortak fonksiyonu kullanır. Ayrı süreç şart: Fatih'in MainWindow'u kendi
    Tk mainloop'unu ister, ayrıca Selenium EczAsist'i kilitlememeli.

    Returns:
        subprocess.Popen | None
    """
    import subprocess
    from tkinter import messagebox
    try:
        runner = str(Path(__file__).resolve())
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        cmd = str(pythonw) if pythonw.exists() else sys.executable

        creationflags = 0
        if os.name == "nt":
            creationflags = (subprocess.CREATE_NO_WINDOW
                             | subprocess.DETACHED_PROCESS)

        proc = subprocess.Popen(
            [cmd, runner],
            cwd=str(ECZASIST_DIZIN),
            creationflags=creationflags,
            close_fds=True,
        )
        logger.info(f"Hibrit Siparişçi başlatıldı: {cmd} {runner}")
        return proc
    except Exception as e:
        logger.error(f"Hibrit Siparişçi başlatma hatası: {e}")
        messagebox.showerror("Hibrit Siparişçi",
                             f"Başlatılamadı:\n{e}", parent=parent)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Fatih modülleri import edildikten sonra kurulan sınıflar (factory)
# ─────────────────────────────────────────────────────────────────────────────

def _siniflari_kur(BotanikEOSController, MainController, sip_logger):
    """SanalBotanik + HibritController sınıflarını üret.

    Fatih'in modülleri ancak sys.path/chdir sonrası import edilebildiği
    için sınıflar modül seviyesinde değil burada tanımlanır.
    """

    class SanalBotanik(BotanikEOSController):
        """Botanik EOS'a hiç dokunmayan sahte controller.

        Okuma → enjekte edilen ürün listesinden; yazma → no-op.
        Saf hesap metotları (calculate_order_quantity fallback,
        aylik_satis_efektif, _count_sales_months...) üst sınıftan
        değişmeden miras alınır.
        """

        def __init__(self, urunler):
            super().__init__()
            self.urunler = list(urunler)
            self._satir = {p["row"]: p for p in self.urunler}

        # ── bağlantı / pencere (no-op) ──────────────────────────────────
        def connect(self):
            sip_logger.info(f"[HİBRİT] Sanal Botanik: {len(self.urunler)} "
                            f"ürünlük EczAsist listesi bağlı (Botanik penceresi KULLANILMIYOR)")
            return True

        def is_connected(self):
            return True

        def bring_siparis_to_front(self):
            return True

        def position_for_ordering(self):
            return True

        def click_yenile_button(self):
            return True

        def prepare_table_for_scan(self):
            self.table_prepared = True
            return True

        def ensure_date_sorted(self):
            return True

        # ── okuma (enjekte listeden) ────────────────────────────────────
        def get_row_numbers(self):
            return [p["row"] for p in self.urunler]

        def get_total_row_count(self, refresh=False):
            return len(self.urunler)

        def get_product_data(self, row_num):
            p = self._satir.get(row_num)
            return dict(p) if p else None

        def get_product_name_at_row(self, row_num):
            p = self._satir.get(row_num)
            return p.get("urun_adi") if p else None

        def get_all_product_names_with_rows(self):
            return {p["urun_adi"].lower(): p["row"] for p in self.urunler}

        def get_all_product_names_fast(self):
            return self.get_all_product_names_with_rows()

        def get_aciklama_value(self, row_num):
            p = self._satir.get(row_num)
            return p.get("mevcut_aciklama", "") if p else ""

        def click_depo_personel_cell(self, row_num, fast_mode=True):
            p = self._satir.get(row_num)
            return p.get("barkod") if p else None

        # ── muadil akışı Botanik UI ister → hibritte kapalı ─────────────
        def get_muadil_list(self):
            return []

        def get_muadil_barcode(self, muadil_rect):
            return None

        # ── yazma (no-op; değer ürün dict'inde saklanır, GUI tutarlı kalır)
        def set_adet_value(self, row_num, value):
            p = self._satir.get(row_num)
            if p is not None:
                p["hibrit_yazilan_adet"] = value
            sip_logger.info(f"[HİBRİT] Botanik'e Adet yazma ATLANDI (satır {row_num} → {value})")
            return True

        def set_mf_value(self, row_num, value):
            p = self._satir.get(row_num)
            if p is not None:
                p["hibrit_yazilan_mf"] = value
            sip_logger.info(f"[HİBRİT] Botanik'e MF yazma ATLANDI (satır {row_num} → {value})")
            return True

        def set_aciklama_value(self, row_num, text, skip_scroll=False):
            p = self._satir.get(row_num)
            if p is not None:
                p["mevcut_aciklama"] = text or ""
            sip_logger.info(f"[HİBRİT] Botanik'e açıklama yazma ATLANDI (satır {row_num})")
            return True

        def set_tevzi_ilac(self, row_num, tam_alindi=False):
            sip_logger.info(f"[HİBRİT] Botanik tevzi işareti ATLANDI (satır {row_num})")
            return True

        # ── sipariş adedi: bizim karar ──────────────────────────────────
        def calculate_order_quantity(self, product):
            ihtiyac = product.get("hibrit_ihtiyac")
            if ihtiyac is not None:
                return int(ihtiyac)
            return super().calculate_order_quantity(product)

        # ── ana okuyucu: gerçek get_all_products_data_only'nin birebir
        #    sözleşmesi (controller.run_fast_scan bunu çağırır) ───────────
        def get_all_products_data_only(self, on_product_read=None,
                                       start_depo_search=None,
                                       start_from_row=None, only_rows=None,
                                       stok_filter_func=None):
            products = []
            rows = [p["row"] for p in self.urunler]

            if start_from_row:
                kalan = [r for r in rows if r >= start_from_row]
                if kalan:
                    rows = kalan
            if only_rows is not None:
                rows = [r for r in rows if r in only_rows]

            total = len(rows)
            sip_logger.info(f"[HİBRİT] EczAsist listesi akıtılıyor: {total} ürün")

            for idx, row_num in enumerate(rows, 1):
                try:
                    if self.gui and hasattr(self.gui, "pause_event"):
                        self.gui.pause_event.wait()
                    if self.gui and getattr(self.gui, "stop_scan", False):
                        sip_logger.info(f"[HİBRİT] Kullanıcı durdurdu (satır {row_num})")
                        break

                    p = self._satir[row_num]

                    if stok_filter_func is not None:
                        try:
                            stok_int = int(p.get("stok") or 0)
                        except (TypeError, ValueError):
                            stok_int = 0
                        if not stok_filter_func(stok_int):
                            continue

                    if self.gui:
                        self.gui.root.after(0, lambda i=idx, t=total, ad=p.get("urun_adi", "-"):
                                            self.gui.update_status(f"Hibrit liste {i}/{t}: {ad}"))

                    # Barkod hazır → depo aramasını hemen başlat (paralel)
                    depo_future = None
                    barkod = p.get("barkod")
                    if barkod and start_depo_search:
                        try:
                            depo_future = start_depo_search(barkod)
                        except Exception as e:
                            sip_logger.debug(f"[HİBRİT] Depo araması başlatılamadı: {e}")

                    # Sipariş adedi (gerçek okuyucudaki mantıkla aynı):
                    # mf==0 → calculate_order_quantity → hibrit_ihtiyac
                    if p.get("mf", 0) == 0:
                        p["siparis_adet"] = self.calculate_order_quantity(p)
                    else:
                        p["siparis_adet"] = p["mf"]

                    # Depo sonuçlarını bekle ve ürüne işle
                    if depo_future:
                        try:
                            depo_sonuclari = depo_future.result(timeout=30)
                            if depo_sonuclari:
                                p.update(depo_sonuclari)
                        except Exception as e:
                            sip_logger.warning(f"[HİBRİT] Depo sonuçları alınamadı "
                                               f"({p.get('urun_adi')}): {e}")

                    products.append(p)

                    if on_product_read:
                        try:
                            on_product_read(p, idx, total)
                        except Exception as cb_err:
                            sip_logger.debug(f"[HİBRİT] Callback hatası: {cb_err}")

                except Exception as e:
                    sip_logger.error(f"[HİBRİT] Satır {row_num} hatası: {e}")
                    continue

            sip_logger.info(f"[HİBRİT] {len(products)} ürün işlendi")
            return products

        # Eski (ölü) controller.run() yolu da çağırırsa aynı listeyi akıt
        def get_all_products(self, filter_mf_zero=False, skip_mf_write=True,
                             on_product=None, start_from_row=None, **kwargs):
            products = []
            rows = [p["row"] for p in self.urunler]
            if start_from_row:
                rows = [r for r in rows if r >= start_from_row] or rows
            total = len(rows)
            for idx, row_num in enumerate(rows, 1):
                p = self._satir[row_num]
                if p.get("mf", 0) == 0:
                    p["siparis_adet"] = self.calculate_order_quantity(p)
                else:
                    p["siparis_adet"] = p["mf"]
                products.append(p)
                if on_product:
                    try:
                        on_product(p, idx, total)
                    except Exception as cb_err:
                        sip_logger.error(f"[HİBRİT] on_product hatası: {cb_err}")
            return products

    class HibritController(MainController):
        """Fatih MainController'ı, Botanik yerine SanalBotanik ile."""

        def __init__(self, urunler):
            super().__init__(gui_window=None)
            sanal = SanalBotanik(urunler)
            # MainController.__init__ gun_sayisi'ni gerçek botanik'e yazmıştı;
            # takas sonrası sanal nesneye taşı.
            sanal.gun_sayisi = getattr(self, "gun_sayisi", 30)
            self.botanik = sanal

        def bul_en_karli_secenek(self, product):
            """Kalem bazında karma MF kuralı (kullanıcı kararı 2026-07-04):

            Kalemde MF planı varsa (Sipariş Ver'de NPV ile seçilmiş, örn.
            100+30) depo şartları içinde BİREBİR eşleşen (min_adet+mf aynı)
            seçenek öne alınır → oto-sepet ve GUI 'en kârlı' olarak planı
            görür. Birebir eşleşme yoksa motor tamamen serbest (normal
            efektif sıralaması). MF plansız kalemler zaten serbest.
            """
            sonuc = super().bul_en_karli_secenek(product)
            plan_min = product.get("hibrit_mf_plan_min")
            plan_mf = product.get("hibrit_mf_plan_mf")
            if not sonuc or not plan_min or not plan_mf:
                return sonuc
            try:
                secenekler = sonuc.get("tum_secenekler") or []
                eslesen = [s for s in secenekler
                           if s.get("min_adet") == plan_min and s.get("mf") == plan_mf]
                if eslesen:
                    kalan = [s for s in secenekler if s not in eslesen]
                    sonuc["tum_secenekler"] = eslesen + kalan
                    sonuc["en_karli"] = eslesen[0]
                    if (not eslesen[0].get("sadece_oneri")
                            and eslesen[0].get("depo") not in ("farmazon", "farmazonrx")):
                        sonuc["en_karli_eklenebilir"] = eslesen[0]
                    product["hibrit_mf_plan_durum"] = (
                        f"PLAN {plan_min}+{plan_mf} bulundu: {eslesen[0].get('depo')}")
                    sip_logger.info(f"[HİBRİT] MF planı öne alındı "
                                    f"({product.get('urun_adi')}): {plan_min}+{plan_mf} "
                                    f"→ {eslesen[0].get('depo')}")
                else:
                    product["hibrit_mf_plan_durum"] = (
                        f"PLAN {plan_min}+{plan_mf} depoda yok → motor serbest")
                    sip_logger.info(f"[HİBRİT] MF planı depoda bulunamadı "
                                    f"({product.get('urun_adi')}): {plan_min}+{plan_mf} "
                                    f"→ serbest seçim")
            except Exception as e:
                sip_logger.warning(f"[HİBRİT] MF plan önceliklendirme hatası: {e}")
            return sonuc

    return HibritController


# ─────────────────────────────────────────────────────────────────────────────
# Ana akış
# ─────────────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO)

    # 1) Kurulum var mı?
    if not (SIPARISCI_DIZIN / "Siparisci.pyw").exists():
        try:
            if str(ECZASIST_DIZIN) not in sys.path:
                sys.path.insert(0, str(ECZASIST_DIZIN))
            from fatih_siparisci_launcher import _kurulum_yok_uyarisi
            _kurulum_yok_uyarisi(parent=None)
        except Exception:
            _hata_kutusu("Hibrit Siparişçi",
                         f"Fatih Siparişçi kurulu değil:\n{SIPARISCI_DIZIN}\n\n"
                         "Önce SiparisciKurulum.exe ile kurulum yapın.")
        return 1

    # 2) Tek örnek: Siparişçi (veya başka bir hibrit) açıksa çalışma.
    #    Aynı Chrome profillerini (data/chrome_profiles) paylaştıkları için
    #    ikisi aynı anda çalışamaz.
    if not _tek_ornek_kilidi_al():
        _hata_kutusu(
            "Hibrit Siparişçi — Siparişçi Açık",
            "Fatih Siparişçi (veya başka bir Hibrit Siparişçi) şu anda açık.\n\n"
            "İkisi aynı depo oturumlarını (Chrome profillerini) paylaştığı için\n"
            "aynı anda çalışamaz.\n\n"
            "Lütfen önce Siparişçi penceresini kapatın, sonra tekrar deneyin."
        )
        return 1

    # 3) EczAsist kesin sipariş listesini yükle
    try:
        calisma, siparisler = _kesin_liste_yukle()
    except Exception as e:
        _hata_kutusu("Hibrit Siparişçi",
                     f"Sipariş listesi okunamadı (siparis_db):\n{e}")
        return 1

    if not calisma:
        _hata_kutusu("Hibrit Siparişçi",
                     "Aktif sipariş çalışması bulunamadı.\n\n"
                     "Önce Sipariş Ver modülünde bir çalışma oluşturup\n"
                     "kesin sipariş listesine ürün ekleyin.")
        return 1

    products, barkodsuz = _urunleri_hazirla(siparisler)
    if not products:
        _hata_kutusu("Hibrit Siparişçi",
                     f"'{calisma.get('ad', '?')}' çalışmasında işlenebilir sipariş yok.\n\n"
                     f"(Toplam kayıt: {len(siparisler)}, barkodsuz/miktarsız: {len(barkodsuz)})")
        return 1

    # 3b) 13 aylık gidiş kırılımını EOS'tan çek (mevsim katsayısı için;
    #     chdir'den ÖNCE — botanik_db EczAsist dizininden import edilir)
    kirilim_sayisi = _aylik_kirilim_topla(products)

    # 4) Fatih ortamına geç (config/.env, data/, logs/ göreli yolları için)
    sys.path.insert(0, str(SIPARISCI_DIZIN))
    os.chdir(SIPARISCI_DIZIN)

    # 5) Sürüm kontrolü (uyar ama engelleme)
    surum_uyari = None
    try:
        from src import surum as _surum
        kurulu = str(getattr(_surum, "SURUM_TAM", "?"))
        if kurulu != TEST_EDILEN_SURUM:
            surum_uyari = (
                f"Kurulu Siparişçi sürümü V{kurulu}, hibrit adaptörü ise "
                f"V{TEST_EDILEN_SURUM} ile test edildi.\n\n"
                "Genellikle sorunsuz çalışır; ama tarama/sepet davranışında "
                "tuhaflık görürsen adaptörün yeni sürüme uyarlanması gerekir."
            )
    except Exception:
        pass

    # 6) Fatih modüllerini yükle
    try:
        from src.controller import MainController
        from src.botanik.eos_controller import BotanikEOSController
        from src.gui.main_window import MainWindow
        from src.utils import logger as sip_logger
    except Exception as e:
        _hata_kutusu("Hibrit Siparişçi",
                     f"Siparişçi modülleri yüklenemedi:\n{e}\n\n{traceback.format_exc()}")
        return 1

    HibritController = _siniflari_kur(BotanikEOSController, MainController, sip_logger)

    # 7) Controller + Fatih GUI (Siparisci.pyw main() ile aynı kablolama)
    sip_logger.info("=" * 60)
    sip_logger.info(f"HİBRİT SİPARİŞÇİ başlatılıyor — çalışma: {calisma.get('ad', '?')}, "
                    f"{len(products)} ürün (EczAsist kesin sipariş listesi)")
    sip_logger.info("=" * 60)

    controller = HibritController(products)
    gui = MainWindow(controller)
    controller.gui = gui
    controller.botanik.gui = gui

    try:
        gui.root.title(gui.root.title() + "  —  🔀 HİBRİT · EczAsist listesi")
    except Exception:
        pass

    # 8) Geri bildirim döngüsü: tarama/sepet sonuçlarını EczAsist kesin
    #    listesine işle (kesin_siparisler.depo_bilgileri → Sipariş Ver'in
    #    depo sütunlarında görünür). Kullanıcı kararı 2026-07-04.
    depo_gorunen = {"selcuk": "Selcuk", "alliance": "Alliance", "sancak": "Sancak",
                    "iskoop": "Iskoop", "farmazon": "Farmazon",
                    "yusufpasa": "YusufPasa", "bursa": "Bursa",
                    "farmazonrx": "FarmazonRX"}
    try:
        from siparis_db import get_siparis_db  # singleton, mutlak yol (chdir'den etkilenmez)
        ecz_db = get_siparis_db()
    except Exception as e:
        sip_logger.warning(f"[HİBRİT] Geri bildirim kapalı (siparis_db yok): {e}")
        ecz_db = None

    def _sonuc_ozeti(p):
        """Ürünün depo sonucunu kesin liste sütun formatına (dict) çevir."""
        ozet = {}
        enk = (p.get("en_karli_sonuc") or {}).get("en_karli") or {}
        if enk:
            ad = depo_gorunen.get(enk.get("depo"), str(enk.get("depo")))
            parca = [x for x in (enk.get("sart"),
                                 f"{enk.get('efektif_birim')} TL" if enk.get("efektif_birim") else None)
                     if x]
            ozet[ad] = ("★ " + " ".join(str(x) for x in parca)).strip()
        if p.get("sepete_eklendi") is True:
            ad = depo_gorunen.get(p.get("sepete_eklenen_depo"), str(p.get("sepete_eklenen_depo")))
            ozet[ad] = f"✓ SEPETTE {p.get('sepete_eklenen_adet', 0)} ad"
        elif p.get("sepete_eklendi") is False and p.get("sepete_eklenmeme_sebebi"):
            ozet["HibritDurum"] = p["sepete_eklenmeme_sebebi"]
        if p.get("hibrit_mf_plan_durum"):
            ozet["MFPlan"] = p["hibrit_mf_plan_durum"]
        return ozet

    _yazilan = {}

    def _geri_bildirim_dongusu():
        try:
            for p in list(getattr(controller, "products", [])):
                sid = p.get("hibrit_db_id")
                if not sid or not ecz_db:
                    continue
                ozet = _sonuc_ozeti(p)
                if ozet and ozet != _yazilan.get(sid):
                    if ecz_db.siparis_guncelle(
                            sid, depo_bilgileri=json.dumps(ozet, ensure_ascii=False)):
                        _yazilan[sid] = ozet
        except Exception as e:
            sip_logger.debug(f"[HİBRİT] Geri bildirim hatası: {e}")
        try:
            gui.root.after(7000, _geri_bildirim_dongusu)
        except Exception:
            pass  # pencere kapandı

    if ecz_db:
        gui.root.after(7000, _geri_bildirim_dongusu)

    # 9) Açılış bilgisi (pencere kurulduktan sonra)
    def _acilis_bilgisi():
        from tkinter import messagebox
        mesaj = (
            f"EczAsist sipariş listesi yüklendi:\n\n"
            f"   Çalışma:  {calisma.get('ad', '?')}\n"
            f"   Ürün:  {len(products)} adet\n"
        )
        if barkodsuz:
            mesaj += (f"   ⚠ Barkodu olmadığı için atlanan: {len(barkodsuz)}\n"
                      f"      ({', '.join(barkodsuz[:5])}"
                      f"{' ...' if len(barkodsuz) > 5 else ''})\n")
        if kirilim_sayisi:
            mesaj += (f"   📈 13 aylık gidiş EOS'tan yüklendi "
                      f"({kirilim_sayisi} ürün) — mevsim katsayısı aktif\n")
        else:
            mesaj += "   📈 Aylık gidiş alınamadı — mevsim düzeltmesi nötr (1.0)\n"
        mesaj += (
            "\nBotanik penceresi KULLANILMAZ ve Botanik'e hiçbir şey yazılmaz.\n"
            "⚡ SİPARİŞ butonuna basınca depolar açılır ve bu liste taranır."
        )
        if surum_uyari:
            mesaj += f"\n\n⚠ SÜRÜM UYARISI:\n{surum_uyari}"
        messagebox.showinfo("Hibrit Siparişçi", mesaj, parent=gui.root)

    gui.root.after(700, _acilis_bilgisi)

    # 10) Çalıştır
    gui.run()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        _hata_kutusu("Hibrit Siparişçi — Beklenmeyen Hata",
                     f"{e}\n\n{traceback.format_exc()}")
        sys.exit(1)
