"""Reçete sorgusunda DIŞLANACAK kurum / kategori yönetimi.

Kullanıcı bazı kurumları (özel sigorta — örn. Türkiye İş Bankası) tüm
reçete sorgularından/SUT kontrollerinden çıkarmak isteyebilir. Bu modül
JSON'da saklar, SQL WHERE koşulu üretir ve ayar penceresini açar.

Kullanım:
    from dislama_ayarlari import (
        ayarlari_yukle, sql_kurum_dislama_kosulu, dislama_penceresi_ac
    )

    ay = ayarlari_yukle()
    where_extra = sql_kurum_dislama_kosulu(ay)  # "" veya "(...)"
    dislama_penceresi_ac(parent_root, db)
"""
from __future__ import annotations

import json
import logging
import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


AYAR_DOSYASI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "dislama_ayarlari.json"
)


VARSAYILAN: Dict = {
    # [{"id": 36, "ad": "TÜRKİYE İŞ BANKASI A.Ş"}, ...]
    "kurum_dislama": [],
}


# ─────────────────────────────────────────────────────────────────────
# JSON CRUD
# ─────────────────────────────────────────────────────────────────────

def ayarlari_yukle() -> Dict:
    """JSON'dan oku, eksikleri varsayılanla doldur."""
    sonuc = {k: list(v) if isinstance(v, list) else v
             for k, v in VARSAYILAN.items()}
    if not os.path.exists(AYAR_DOSYASI):
        return sonuc
    try:
        with open(AYAR_DOSYASI, "r", encoding="utf-8") as f:
            ay = json.load(f)
    except Exception as e:
        logger.warning("Dışlama ayarları okunamadı: %s", e)
        return sonuc

    kd = ay.get("kurum_dislama")
    if isinstance(kd, list):
        temiz = []
        for item in kd:
            if isinstance(item, dict) and "id" in item:
                try:
                    temiz.append({
                        "id": int(item["id"]),
                        "ad": str(item.get("ad", "")).strip(),
                    })
                except (ValueError, TypeError):
                    continue
        sonuc["kurum_dislama"] = temiz
    return sonuc


def ayarlari_kaydet(ay: Dict) -> bool:
    try:
        with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(ay, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.warning("Dışlama ayarları yazılamadı: %s", e)
        return False


# ─────────────────────────────────────────────────────────────────────
# SQL üretici
# ─────────────────────────────────────────────────────────────────────

def sql_kurum_dislama_kosulu(ay: Dict) -> str:
    """SQL WHERE'e eklenecek kurum dışlama koşulu üret.

    Returns:
        '(ra.RxKurumId IS NULL OR ra.RxKurumId NOT IN (36,37))'
        veya boş string (dışlanan kurum yoksa).

    NOT: NULL kurumlu reçeteler dışlanmaz (genelde elden satış / belirsiz).
    """
    kd = ay.get("kurum_dislama") or []
    idler = []
    for item in kd:
        if isinstance(item, dict) and "id" in item:
            try:
                idler.append(str(int(item["id"])))
            except (ValueError, TypeError):
                continue
    if not idler:
        return ""
    return f"(ra.RxKurumId IS NULL OR ra.RxKurumId NOT IN ({','.join(idler)}))"


# ─────────────────────────────────────────────────────────────────────
# AYAR PENCERESİ (Toplevel)
# ─────────────────────────────────────────────────────────────────────

def _kurum_listesini_db_den_cek(db) -> List[Dict]:
    """Tüm kurumları + son 365 gündeki reçete adedini birlikte getir."""
    if db is None:
        return []
    sql = """
    SELECT
        k.KurumId                                                    AS id,
        ISNULL(k.KurumAdi, N'(adsız)')                               AS ad,
        ISNULL((SELECT COUNT(DISTINCT ra.RxId)
                FROM ReceteAna ra
                WHERE ra.RxKurumId = k.KurumId
                  AND ra.RxSilme = 0
                  AND ra.RxKayitTarihi >= DATEADD(DAY, -365, GETDATE())
        ), 0)                                                        AS son_yil_recete
    FROM Kurum k
    ORDER BY ad
    """
    try:
        rows = db.sorgu_calistir(sql)
    except Exception as e:
        logger.warning("Kurum listesi çekilemedi: %s", e)
        return []
    sonuc = []
    for r in rows or []:
        try:
            sonuc.append({
                "id": int(r["id"]),
                "ad": str(r.get("ad") or "").strip(),
                "son_yil_recete": int(r.get("son_yil_recete") or 0),
            })
        except (ValueError, TypeError, KeyError):
            continue
    return sonuc


def dislama_penceresi_ac(parent: tk.Misc, db,
                          on_kaydet: Optional[Callable[[], None]] = None):
    """Dışlama Ayarları penceresini aç.

    Args:
        parent: ana Tk root / Toplevel
        db: BotanikDB instance (kurum listesini çekmek için)
        on_kaydet: kaydetme sonrası çağrılır (örn: sayım yenile)
    """
    win = tk.Toplevel(parent)
    win.title("🚫 Dışlama Ayarları — Kurum")
    win.geometry("760x620")
    win.transient(parent)

    ay = ayarlari_yukle()
    halen_dislanan_idler = {
        int(it["id"]) for it in ay.get("kurum_dislama", [])
        if isinstance(it, dict) and "id" in it
    }

    # Üst başlık + açıklama
    ttk.Label(
        win,
        text="Bu pencerede seçilen kurumlar TÜM reçete sorgularından "
             "ve SUT kontrol butonlarından dışlanır.",
        wraplength=720, justify="left",
    ).pack(padx=12, pady=(12, 6), anchor="w")
    ttk.Label(
        win,
        text="Kurumun yanındaki kutuyu işaretleyince o kurumun reçeteleri "
             "GELMEZ. Sayı: son 365 gün.",
        wraplength=720, justify="left", foreground="#666",
    ).pack(padx=12, pady=(0, 8), anchor="w")

    # Arama
    arama_cer = ttk.Frame(win)
    arama_cer.pack(fill="x", padx=12, pady=(0, 6))
    ttk.Label(arama_cer, text="🔍 Filtrele:").pack(side="left")
    arama_var = tk.StringVar()
    arama_ent = ttk.Entry(arama_cer, textvariable=arama_var, width=40)
    arama_ent.pack(side="left", padx=(6, 0))

    # Liste — Treeview + Checkbox sütunu (manuel)
    cer = ttk.Frame(win)
    cer.pack(fill="both", expand=True, padx=12, pady=(4, 6))

    kolonlar = ("disla", "id", "ad", "recete")
    tv = ttk.Treeview(cer, columns=kolonlar, show="headings",
                       selectmode="browse", height=20)
    tv.heading("disla", text="DIŞLA")
    tv.heading("id", text="ID")
    tv.heading("ad", text="Kurum Adı")
    tv.heading("recete", text="Reçete (1 yıl)")
    tv.column("disla", width=70, anchor="center")
    tv.column("id", width=60, anchor="center")
    tv.column("ad", width=460, anchor="w")
    tv.column("recete", width=110, anchor="e")

    sb = ttk.Scrollbar(cer, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    # Veri yükle
    tum_kurumlar = _kurum_listesini_db_den_cek(db)
    if not tum_kurumlar:
        messagebox.showwarning(
            "Veritabanı",
            "Kurum listesi çekilemedi. DB bağlantısını kontrol edin.",
            parent=win)

    # Mevcut state'i tutar (id → True/False)
    secimler: Dict[int, bool] = {
        k["id"]: (k["id"] in halen_dislanan_idler) for k in tum_kurumlar
    }

    def _disla_isaret(disli: bool) -> str:
        return "✅" if disli else "☐"

    def _doldur(filtre: str = ""):
        tv.delete(*tv.get_children())
        f = (filtre or "").strip().lower()
        for k in tum_kurumlar:
            if f and f not in k["ad"].lower() and f not in str(k["id"]):
                continue
            tv.insert("", "end", iid=str(k["id"]), values=(
                _disla_isaret(secimler.get(k["id"], False)),
                k["id"], k["ad"], k["son_yil_recete"],
            ))

    _doldur()

    # Tıklama → DIŞLA sütununu toggle
    def _on_click(event):
        rowid = tv.identify_row(event.y)
        col = tv.identify_column(event.x)
        if not rowid:
            return
        try:
            kid = int(rowid)
        except ValueError:
            return
        # Sadece DIŞLA sütununa tıklarsa toggle (column #1)
        if col != "#1":
            return
        secimler[kid] = not secimler.get(kid, False)
        tv.set(rowid, "disla", _disla_isaret(secimler[kid]))

    tv.bind("<Button-1>", _on_click)

    # Çift tıklama da toggle yapsın (her sütunda)
    def _on_dbl(event):
        rowid = tv.identify_row(event.y)
        if not rowid:
            return
        try:
            kid = int(rowid)
        except ValueError:
            return
        secimler[kid] = not secimler.get(kid, False)
        tv.set(rowid, "disla", _disla_isaret(secimler[kid]))

    tv.bind("<Double-Button-1>", _on_dbl)

    # Arama filtresi
    def _on_arama(*_):
        _doldur(arama_var.get())

    arama_var.trace_add("write", _on_arama)

    # Alt butonlar
    btn_cer = ttk.Frame(win)
    btn_cer.pack(fill="x", padx=12, pady=(4, 12))

    sayac_lbl = ttk.Label(btn_cer, text="", foreground="#a00")
    sayac_lbl.pack(side="left")

    def _sayac_guncelle():
        adet = sum(1 for v in secimler.values() if v)
        sayac_lbl.config(text=(f"⚠️ {adet} kurum dışlanacak"
                                  if adet else "Dışlanan kurum yok"))

    _sayac_guncelle()

    def _kaydet():
        # secimler dict → kurum_dislama listesi
        ad_map = {k["id"]: k["ad"] for k in tum_kurumlar}
        kd = [{"id": kid, "ad": ad_map.get(kid, "")}
              for kid, dis in secimler.items() if dis]
        ay["kurum_dislama"] = kd
        if ayarlari_kaydet(ay):
            messagebox.showinfo(
                "Kaydedildi",
                f"{len(kd)} kurum dışlanacak şekilde kaydedildi.\n\n"
                f"Bir sonraki SORGULA'da etkili olacak.",
                parent=win)
            if on_kaydet:
                try:
                    on_kaydet()
                except Exception as e:
                    logger.warning("on_kaydet hata: %s", e)
            win.destroy()
        else:
            messagebox.showerror(
                "Hata",
                "Ayarlar kaydedilemedi. Log'a bakın.",
                parent=win)

    def _hepsini_temizle():
        for kid in list(secimler.keys()):
            secimler[kid] = False
        for rowid in tv.get_children():
            tv.set(rowid, "disla", "☐")
        _sayac_guncelle()

    # Sayaç güncellemesi her toggle sonrası — basit yöntem: timer
    def _sayac_periyodik():
        _sayac_guncelle()
        win.after(300, _sayac_periyodik)

    win.after(300, _sayac_periyodik)

    ttk.Button(btn_cer, text="💾 Kaydet", command=_kaydet).pack(
        side="right", padx=(6, 0))
    ttk.Button(btn_cer, text="❌ İptal", command=win.destroy).pack(
        side="right")
    ttk.Button(btn_cer, text="🧹 Hepsini Temizle",
                command=_hepsini_temizle).pack(side="right", padx=(6, 6))

    win.grab_set()
    arama_ent.focus_set()
