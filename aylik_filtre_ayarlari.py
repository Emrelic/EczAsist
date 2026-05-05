"""
Aylık İnceleme — Gelişmiş Filtre Ayarları

İki katmanlı filtre sistemi:

1) İÇERİK FİLTRESİ (4 toggle):
   Bir satır en az birinden geçerse getirilir:
   - Renkli reçete (Kırmızı/Yeşil/Mor)
   - İlaç mesajı var
   - Uyarı kodu var
   - Rapor kodu var

2) LİSTE BAZLI FİLTRELER (4 liste, her biri whitelist/blacklist mod ile):
   - İlaç adları
   - Etken maddeler
   - ATC grupları
   - Farmasötik formlar

   Mod seçenekleri:
   - 'yok'        → liste devre dışı
   - 'getir'      → SADECE bu listedekiler gelsin (whitelist)
   - 'getirme'    → bu listedekiler GELMESİN (blacklist)

GÜVENLİK: Sadece SELECT — Botanik EOS'ta hiçbir veri değişmez.
"""
import json
import os
import logging

logger = logging.getLogger(__name__)


# Ayar JSON dosyası
AYAR_DOSYASI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "aylik_filtre_ayarlari.json"
)


# Liste tipleri
LISTE_TIPLERI = ("ilac", "etken", "atc", "farma", "tesis", "esdeger")
LISTE_ETIKETLERI = {
    "ilac":     "İlaç Adı",
    "etken":    "Etken Madde",
    "atc":      "ATC Grubu",
    "farma":    "Farmasötik Form",
    "tesis":    "Tesis (Hastane Kodu / Adı)",
    "esdeger":  "Eşdeğer Grubu",
}


VARSAYILAN = {
    # ── İçerik filtresi (her biri "getir mi?") ──
    "renkli_getir": True,       # Kırmızı/Yeşil/Mor reçeteler
    "mesaj_getir":  True,       # Mesajı olan ilaçlar
    "uyari_getir":  True,       # Uyarı kodu olanlar
    "rapor_getir":  True,       # Rapor kodu olanlar

    # ── Liste bazlı filtreler ──
    # Her tip için liste: [{"deger": "...", "mod": "icerir"|"icermez"}, ...]
    # mod="icerir"  → kural geçerli ise satır gelir (whitelist davranışı)
    # mod="icermez" → kural geçerli ise satır gelmez (blacklist davranışı)
    # Boş liste → o tip için kural yok
    "ilac":     [],
    "etken":    [],
    "atc":      [],
    "farma":    [],
    "tesis":    [],
    "esdeger":  [],
}


def _eski_format_mi(cfg) -> bool:
    """Eski format: {'mod': 'yok|getir|getirme', 'ogeler': [...]}"""
    return isinstance(cfg, dict) and "mod" in cfg and "ogeler" in cfg


def _eski_yeniye_donustur(cfg) -> list:
    """Eski format → yeni format (per-item içerir/içermez)."""
    if not _eski_format_mi(cfg):
        return []
    mod = cfg.get("mod", "yok")
    ogeler = cfg.get("ogeler", []) or []
    if mod == "yok" or not ogeler:
        return []
    yeni_mod = "icerir" if mod == "getir" else "icermez"
    return [{"deger": str(s).strip(), "mod": yeni_mod}
            for s in ogeler if str(s).strip()]


def ayarlari_yukle() -> dict:
    """JSON'dan oku, eksikleri varsayılanla doldur. Eski formatı yeniye
    çevirir."""
    sonuc = {k: (list(v) if isinstance(v, list) else v)
              for k, v in VARSAYILAN.items()}
    if not os.path.exists(AYAR_DOSYASI):
        return sonuc
    try:
        with open(AYAR_DOSYASI, "r", encoding="utf-8") as f:
            ay = json.load(f)
    except Exception as e:
        logger.warning("Filtre ayarları okunamadı: %s", e)
        return sonuc

    # İçerik toggle'ları
    for k in ("renkli_getir", "mesaj_getir", "uyari_getir", "rapor_getir"):
        if k in ay:
            sonuc[k] = bool(ay[k])

    # Liste bazlı filtreler — eski/yeni format desteği
    for tip in LISTE_TIPLERI:
        v = ay.get(tip)
        if isinstance(v, list):
            # Yeni format
            kurallar = []
            for item in v:
                if isinstance(item, dict):
                    deger = (item.get("deger") or "").strip()
                    mod = item.get("mod", "icerir")
                    if mod not in ("icerir", "icermez"):
                        mod = "icerir"
                    if deger:
                        kurallar.append({"deger": deger, "mod": mod})
                elif isinstance(item, str) and item.strip():
                    # Düz string listesi → tümü içerir kabul et
                    kurallar.append({"deger": item.strip(), "mod": "icerir"})
            sonuc[tip] = kurallar
        elif _eski_format_mi(v):
            sonuc[tip] = _eski_yeniye_donustur(v)
        else:
            sonuc[tip] = []
    return sonuc


def ayarlari_kaydet(ay: dict):
    """JSON'a yaz."""
    try:
        with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(ay, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Filtre ayarları yazılamadı: %s", e)


def hicbir_icerik_secili_mi(ay: dict) -> bool:
    """4 içerik toggle'ından hiçbiri açık değilse True."""
    return not (ay.get("renkli_getir") or ay.get("mesaj_getir")
                or ay.get("uyari_getir") or ay.get("rapor_getir"))


def sql_icerik_kosullari(ay: dict, renkli_recete_idler: list) -> str:
    """İçerik filtresine göre SQL WHERE parçası üret.

    Args:
        ay: filtre ayarları dict
        renkli_recete_idler: ReceteRenk tablosundan Kırmızı/Yeşil/Mor ID'leri

    Returns:
        WHERE'e eklenecek koşul (parantezsiz, "AND" ile birleştirilmesi
        bekleyen) — boş string ise filtre yok demektir.
    """
    or_kosullar = []
    if ay.get("renkli_getir") and renkli_recete_idler:
        renkli_in = ",".join(str(int(i)) for i in renkli_recete_idler)
        or_kosullar.append(f"ra.RxReceteRenkId IN ({renkli_in})")
    if ay.get("mesaj_getir"):
        or_kosullar.append(
            "EXISTS ("
            "  SELECT 1 FROM UMTUrunMesaj umt"
            "  LEFT JOIN UMTMesaj m ON m.UMTMId = umt.UMTUMUMTMesajId"
            "  WHERE umt.UMTUMUrunId = ri.RIUrunId"
            "    AND m.UMTMMesaj IS NOT NULL"
            "    AND LEN(LTRIM(RTRIM(m.UMTMMesaj))) > 0"
            ")"
        )
    if ay.get("uyari_getir"):
        or_kosullar.append(
            "EXISTS ("
            "  SELECT 1 FROM ReceteTeshis rt"
            "  WHERE rt.RTRxId = ra.RxId"
            "    AND rt.RTTeshisKodu IS NOT NULL"
            "    AND LEN(LTRIM(RTRIM(rt.RTTeshisKodu))) > 0"
            "    AND (rt.RTUrunId IS NULL OR rt.RTUrunId = ri.RIUrunId)"
            ")"
        )
    if ay.get("rapor_getir"):
        or_kosullar.append(
            "(ri.RIRaporKodId IS NOT NULL AND ri.RIRaporKodId > 0)")

    if not or_kosullar:
        # 4 kriter de KAPALI → hiçbir satır gelmez
        return "1 = 0"
    return "(" + " OR ".join(or_kosullar) + ")"


def _q(s: str) -> str:
    """SQL nvarchar literal — single-quote escape."""
    return "N'" + str(s).replace("'", "''").strip() + "'"


def _esit_kosul(kolon: str, deger: str) -> str:
    """Tam eşitlik (= operatörü)."""
    return f"{kolon} = {_q(deger)}"


def _like_kosul(kolon: str, deger: str) -> str:
    """LIKE %deger% (case-insensitive) — etken/farma için."""
    safe = str(deger).replace("'", "''").strip()
    return f"UPPER({kolon}) LIKE UPPER(N'%{safe}%')"


def _kategori_kosul(kurallar: list, kosul_fn) -> str:
    """Bir kategori için içerir/içermez kurallarını SQL'e çevir.

    İçerir kuralları OR ile birleşir (en az biri sağlansa yeter).
    İçermez kuralları AND NOT ile birleşir (hiçbiri eşleşmemeli).
    İkisi de varsa: (içerir OR ...) AND (NOT içermez1 AND NOT içermez2)
    """
    if not kurallar:
        return ""
    icerir = [k for k in kurallar if k.get("mod") == "icerir"
              and k.get("deger")]
    icermez = [k for k in kurallar if k.get("mod") == "icermez"
               and k.get("deger")]
    parcalar = []
    if icerir:
        parcalar.append("(" + " OR ".join(kosul_fn(k["deger"])
                                            for k in icerir) + ")")
    if icermez:
        parcalar.append(" AND ".join("NOT " + kosul_fn(k["deger"])
                                       for k in icermez))
    return " AND ".join(parcalar)


def sql_liste_kosullari(ay: dict) -> str:
    """Liste bazlı filtrelerden SQL WHERE parçası üret. Her kategorideki
    kurallar içerir/içermez moduna göre birleşir; kategoriler arası VE."""
    parcalar = []

    # İlaç adı — tam eşitlik
    p = _kategori_kosul(ay.get("ilac") or [],
                         lambda v: _esit_kosul("u.UrunAdi", v))
    if p:
        parcalar.append(p)

    # Etken madde — UrunAdi VEYA ATCTurkce VEYA ATCKodu içinde ara
    # (tablo etken sütunu bu üçünden besleniyor)
    def _etken_kosul(v):
        return ("(" + _like_kosul("u.UrunAdi", v) + " OR "
                + _like_kosul("atc.ATCTurkce", v) + " OR "
                + _like_kosul("atc.ATCKodu", v) + ")")

    p = _kategori_kosul(ay.get("etken") or [], _etken_kosul)
    if p:
        parcalar.append(p)

    # ATC — kod veya Türkçe ad eşitliği (her ikisi OR)
    def _atc_kosul(v):
        return f"(atc.ATCKodu = {_q(v)} OR atc.ATCTurkce = {_q(v)})"

    p = _kategori_kosul(ay.get("atc") or [], _atc_kosul)
    if p:
        parcalar.append(p)

    # Farmasötik form — LIKE
    p = _kategori_kosul(ay.get("farma") or [],
                         lambda v: _like_kosul("u.UrunAdi", v))
    if p:
        parcalar.append(p)

    # Tesis — hastane kodu veya adı (subquery)
    def _tesis_kosul(v):
        return (f"EXISTS (SELECT 1 FROM Hastane h "
                f"WHERE h.HastaneId = ra.RxHastaneId AND "
                f"(h.HastaneKodu = {_q(v)} OR h.HastaneAdi = {_q(v)}))")

    p = _kategori_kosul(ay.get("tesis") or [], _tesis_kosul)
    if p:
        parcalar.append(p)

    # Eşdeğer grubu — u.UrunEsdegerId numerik eşitliği.
    # Değer "12345" veya "12345 — CALPOL ŞURUP" formatında olabilir;
    # baştaki sayıyı çekip SQL'e koyarız.
    import re as _re

    def _esdeger_kosul(v):
        m = _re.match(r"^\s*(\d+)", str(v))
        if not m:
            return "1 = 0"  # geçersiz değer → eşleşme yok
        return f"u.UrunEsdegerId = {int(m.group(1))}"

    p = _kategori_kosul(ay.get("esdeger") or [], _esdeger_kosul)
    if p:
        parcalar.append(p)

    return " AND ".join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# AYAR PENCERESİ (Toplevel dialog)
# ═══════════════════════════════════════════════════════════════════════

def _liste_secici_pencere_ac(parent, db, tip, on_select):
    """Veritabanından arama+seçim popup'ı.
    tip: 'ilac', 'etken', 'atc', 'farma', 'tesis'
    on_select(secilen_degerler_listesi, mod) — modu içerir/içermez
    """
    import tkinter as tk
    from tkinter import ttk, messagebox

    # Tipe göre SQL ve gösterim
    # Tabloda etken madde sütunu HEM ATC.ATCTurkce HEM RaporEtkinMadde'den
    # geldiği için picker iki kaynağı UNION'la birleştirir.
    SORGULAR = {
        "ilac": ("SELECT DISTINCT u.UrunAdi AS deger, '' AS ek "
                  "FROM Urun u WHERE u.UrunSilme = 0 "
                  "AND u.UrunAdi IS NOT NULL "
                  "AND LEN(u.UrunAdi) > 0 "
                  "ORDER BY u.UrunAdi", "İlaç Adı"),
        "etken": ("SELECT deger, MAX(ek) AS ek FROM ("
                   "  SELECT DISTINCT a.ATCTurkce AS deger, a.ATCKodu AS ek"
                   "  FROM ATC a "
                   "  WHERE a.ATCTurkce IS NOT NULL "
                   "    AND LEN(LTRIM(RTRIM(a.ATCTurkce))) > 0 "
                   "  UNION "
                   "  SELECT DISTINCT em.EtkinMaddeAdi AS deger, "
                   "    ISNULL(em.EtkinMaddeSGKKodu, '') AS ek "
                   "  FROM EtkinMadde em "
                   "  WHERE em.EtkinMaddeSilme = 0 "
                   "    AND em.EtkinMaddeAdi IS NOT NULL "
                   "    AND LEN(LTRIM(RTRIM(em.EtkinMaddeAdi))) > 0"
                   ") x GROUP BY deger ORDER BY deger",
                   "Etken Madde / ATC Türkçe"),
        "atc": ("SELECT a.ATCKodu AS deger, "
                 "ISNULL(a.ATCTurkce, '') AS ek "
                 "FROM ATC a "
                 "WHERE a.ATCKodu IS NOT NULL "
                 "ORDER BY a.ATCKodu", "ATC Kodu"),
        "farma": ("SELECT DISTINCT uf.UMTFarmasotikAdi AS deger, '' AS ek "
                   "FROM UMTFarmasotik uf "
                   "WHERE uf.UMTFarmasotikAdi IS NOT NULL "
                   "ORDER BY uf.UMTFarmasotikAdi", "Farmasötik Form"),
        "tesis": ("SELECT h.HastaneKodu AS deger, "
                   "ISNULL(h.HastaneAdi, '') AS ek "
                   "FROM Hastane h WHERE h.HastaneSilme = 0 "
                   "AND h.HastaneKodu IS NOT NULL "
                   "ORDER BY h.HastaneAdi", "Tesis"),
        # Eşdeğer grubu — picker'da "EsdegerId — Örnek İlaç Adı" gösterir.
        # Aynı eşdeğer grubundaki tüm ilaçlar paylaşır, kullanıcı bir
        # tanesini seçince grup ID'si rule'a yazılır.
        "esdeger": (
            "SELECT CAST(g.UrunEsdegerId AS NVARCHAR(20)) "
            "       + N' — ' + ISNULL(g.OrnekIlac, N'') AS deger,"
            "       CAST(g.IlacSayisi AS NVARCHAR(10)) + N' ilaç' AS ek "
            "FROM ("
            "  SELECT u.UrunEsdegerId, "
            "         COUNT(*) AS IlacSayisi, "
            "         (SELECT TOP 1 u2.UrunAdi FROM Urun u2 "
            "          WHERE u2.UrunEsdegerId = u.UrunEsdegerId "
            "            AND u2.UrunSilme = 0 "
            "          ORDER BY u2.UrunAdi) AS OrnekIlac "
            "  FROM Urun u "
            "  WHERE u.UrunSilme = 0 "
            "    AND u.UrunEsdegerId IS NOT NULL "
            "    AND u.UrunEsdegerId > 0 "
            "  GROUP BY u.UrunEsdegerId"
            ") g "
            "ORDER BY g.OrnekIlac",
            "Eşdeğer Grubu"),
    }
    sql, baslik = SORGULAR.get(tip, ("", "Liste"))
    if not sql or db is None:
        messagebox.showinfo(
            "Bilgi", "Bu tip için veritabanı listesi mevcut değil.")
        return

    # Veriyi çek
    try:
        rows = db.sorgu_calistir(sql)
    except Exception as e:
        messagebox.showerror("Veritabanı Hatası",
                              f"{baslik} listesi okunamadı:\n{e}")
        return

    veri = []   # [(deger, ek)]
    for r in rows:
        d = (r.get("deger") or "").strip()
        if not d:
            continue
        e = (r.get("ek") or "").strip()
        veri.append((d, e))

    if not veri:
        messagebox.showinfo("Bilgi", f"{baslik} listesi boş.")
        return

    # Pencere
    win = tk.Toplevel(parent)
    win.title(f"📂 {baslik} — Listeden Seç")
    win.geometry("680x600")
    win.minsize(540, 420)
    win.configure(bg="#FAFAFA")
    win.transient(parent)

    tk.Label(win,
              text=f"📋 {baslik} listesi ({len(veri)} kayıt) — "
                   f"Ctrl/Shift ile çoklu seçim, çift tık veya butonla ekle",
              bg="#FAFAFA", fg="#37474F",
              font=("Segoe UI", 9, "bold")
              ).pack(anchor="w", padx=8, pady=(8, 4))

    # Arama kutusu
    arama_frm = tk.Frame(win, bg="#FAFAFA")
    arama_frm.pack(fill="x", padx=8, pady=2)
    tk.Label(arama_frm, text="🔍 Ara:", bg="#FAFAFA",
              font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
    var_ara = tk.StringVar()
    ent_ara = tk.Entry(arama_frm, textvariable=var_ara,
                        font=("Segoe UI", 10))
    ent_ara.pack(side="left", fill="x", expand=True)
    ent_ara.focus_set()

    # Sayım etiketi
    lbl_sayim = tk.Label(arama_frm, text="", bg="#FAFAFA", fg="#546E7A",
                          font=("Segoe UI", 9))
    lbl_sayim.pack(side="left", padx=(8, 0))

    # Treeview
    tv_frm = tk.Frame(win, bg="#FAFAFA")
    tv_frm.pack(fill="both", expand=True, padx=8, pady=4)
    sb = ttk.Scrollbar(tv_frm)
    sb.pack(side="right", fill="y")
    tv = ttk.Treeview(tv_frm, columns=("d", "e"), show="headings",
                       yscrollcommand=sb.set, selectmode="extended")
    tv.heading("d", text="Değer")
    tv.heading("e", text="Açıklama / Kod")
    tv.column("d", width=320, stretch=True)
    tv.column("e", width=320, stretch=True)
    tv.pack(side="left", fill="both", expand=True)
    sb.config(command=tv.yview)

    def _norm(s: str) -> str:
        """Türkçe karakter güvenli, büyük harfe çevirip Latin'e indirgeyen
        normalizasyon. 'FLURBİPROFEN' = 'flurbiprofen' = 'FLURBIPROFEN'
        eşleştirmesi için."""
        if not s:
            return ""
        s = s.upper()
        # Türkçe → Latin
        s = (s.replace("İ", "I").replace("I", "I").replace("Ş", "S")
              .replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O")
              .replace("Ç", "C").replace("ı", "i"))
        return s

    def _doldur(filtre=""):
        for iid in list(tv.get_children()):
            tv.delete(iid)
        flt = _norm(filtre.strip())
        n = 0
        # En fazla 5000 kayıt göster (büyük listelerde performans)
        for d, e in veri:
            if flt and flt not in _norm(d) and flt not in _norm(e):
                continue
            tv.insert("", "end", values=(d, e))
            n += 1
            if n >= 5000:
                break
        toplam = len(veri)
        if filtre.strip() and n == 0:
            lbl_sayim.config(
                text=f"⚠ '{filtre.strip()}' için 0 sonuç — "
                     f"'{baslik}' tablosunda yok. Manuel ekle.",
                fg="#B71C1C")
        else:
            lbl_sayim.config(
                text=f"Gösterilen: {n} / {toplam}", fg="#546E7A")
    _doldur()

    var_ara.trace_add("write",
                       lambda *a: _doldur(var_ara.get()))

    # Mod seçici + Ekle butonları
    bot = tk.Frame(win, bg="#ECEFF1")
    bot.pack(fill="x", side="bottom")

    mod_var = tk.StringVar(value="icermez")
    rad_frm = tk.Frame(bot, bg="#ECEFF1")
    rad_frm.pack(fill="x", padx=8, pady=(6, 2))
    tk.Label(rad_frm, text="Eklenirken mod:",
              bg="#ECEFF1", font=("Segoe UI", 9, "bold")
              ).pack(side="left")
    tk.Radiobutton(rad_frm, text="✅ İçerir (sadece bu gelsin)",
                    variable=mod_var, value="icerir", bg="#ECEFF1"
                    ).pack(side="left", padx=4)
    tk.Radiobutton(rad_frm, text="❌ İçermez (bu gelmesin)",
                    variable=mod_var, value="icermez", bg="#ECEFF1"
                    ).pack(side="left", padx=4)

    btn_frm = tk.Frame(bot, bg="#ECEFF1")
    btn_frm.pack(fill="x", padx=8, pady=(2, 6))

    def _ekle():
        secilenler = [tv.item(iid, "values")[0]
                      for iid in tv.selection()]
        if not secilenler:
            messagebox.showwarning("Uyarı",
                                       "Önce listeden öğe seç (Ctrl/Shift "
                                       "ile çoklu seçim).")
            return
        try:
            on_select(secilenler, mod_var.get())
        except Exception as e:
            messagebox.showerror("Hata", f"Eklenemedi: {e}")
            return
        win.destroy()

    tk.Button(btn_frm, text="➕ Seçilenleri Ekle ve Kapat",
               bg="#43A047", fg="white", bd=0, padx=12, pady=4,
               font=("Segoe UI", 10, "bold"),
               command=_ekle).pack(side="left", padx=2)
    tk.Button(btn_frm, text="❌ İptal", bg="#90A4AE", fg="white",
               bd=0, padx=10, pady=4, font=("Segoe UI", 9, "bold"),
               command=win.destroy).pack(side="right", padx=2)

    # Çift tık → seçileni ekle (tek satır)
    tv.bind("<Double-1>", lambda e: _ekle())

    win.grab_set()


def ayar_penceresini_ac(parent, db=None, on_save=None):
    """Filtre ayar penceresini aç.
    db: Botanik DB bağlantısı (Listeden Seç özelliği için)
    on_save: kaydet sonrası callback (yeni ayarları alır)."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    win = tk.Toplevel(parent)
    win.title("⚙ Aylık İnceleme — Detaylı Filtre Ayarları")
    # İçeriğe yeten kompakt boyut — tüm bölümler ve butonlar görünür
    win.minsize(820, 680)
    win.resizable(True, True)
    win.configure(bg="#FAFAFA")
    win.transient(parent)
    # Ekrana ortala (ekran küçükse ekrandan taşmasın)
    try:
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        ww = min(1000, sw - 80)
        wh = min(780, sh - 80)
        x = max(0, (sw - ww) // 2)
        y = max(0, (sh - wh) // 2)
        win.geometry(f"{ww}x{wh}+{x}+{y}")
    except Exception:
        win.geometry("1000x780")
    win.lift()
    try:
        win.focus_force()
    except Exception:
        pass

    ay = ayarlari_yukle()

    # ÖNEMLİ: Alt buton bar'ı sec2'nin (expand=True) önünde rezerve etmek
    # için EN ÖNCE paketleniyor (içeriği aşağıda doldurulur). Aksi halde
    # sec2 tüm alanı yutar ve alt bar görünmez kalır.
    alt = tk.Frame(win, bg="#ECEFF1")
    alt.pack(fill="x", side="bottom")

    # ════════════════════════════════════════════════════════════════
    # KOMPAKT BANNER (tek satır)
    # ════════════════════════════════════════════════════════════════
    banner = tk.Frame(win, bg="#B71C1C")
    banner.pack(fill="x")
    tk.Label(banner,
              text="🚫  Hangi Satırlar Tabloya GELMEYECEK?  ─  "
                   "Ana ekrandaki '🚫 Boş Satırları Gizle' AÇIKKEN bu "
                   "kurallar SQL'e uygulanır.",
              bg="#B71C1C", fg="white",
              font=("Segoe UI", 10, "bold"), padx=14, pady=8
              ).pack(anchor="w")

    # ════════════════════════════════════════════════════════════════
    # SECTION 1 — İÇERİK FİLTRESİ (TEK SATIR — 4 toggle yan yana)
    # ════════════════════════════════════════════════════════════════
    var_renkli = tk.BooleanVar(value=ay.get("renkli_getir", True))
    var_mesaj = tk.BooleanVar(value=ay.get("mesaj_getir", True))
    var_uyari = tk.BooleanVar(value=ay.get("uyari_getir", True))
    var_rapor = tk.BooleanVar(value=ay.get("rapor_getir", True))

    sec1 = tk.LabelFrame(
        win, text=" 1️⃣  İÇERİK DIŞLAMA KURALLARI "
                  "(işaretliler 'boş' tanımına dahil edilir) ",
        bg="#FFEBEE", fg="#B71C1C",
        font=("Segoe UI", 10, "bold"), padx=10, pady=6,
        bd=2, relief="ridge")
    sec1.pack(fill="x", padx=10, pady=(6, 4))

    icerik_grid = tk.Frame(sec1, bg="#FFEBEE")
    icerik_grid.pack(fill="x")
    icerik_grid.columnconfigure((0, 1, 2, 3), weight=1, uniform="ic")

    icerik_secimleri = [
        (var_uyari, "⚠ Uyarısız Gelmesin",
         "Uyarı kodu OLMAYAN satırlar boş kabul edilsin"),
        (var_mesaj, "💬 Mesajsız Gelmesin",
         "İlaç mesajı OLMAYAN satırlar boş kabul edilsin"),
        (var_rapor, "📋 Raporsuz Gelmesin",
         "Rapor kodu OLMAYAN satırlar boş kabul edilsin"),
        (var_renkli, "🟥🟩🟪 Beyaz Reçete Gelmesin",
         "Kırmızı/Yeşil/Mor olmayan beyaz reçeteler boş kabul edilsin"),
    ]
    for i, (v, baslik, tip_text) in enumerate(icerik_secimleri):
        kart = tk.Frame(icerik_grid, bg="white", bd=1, relief="solid")
        kart.grid(row=0, column=i, sticky="nsew", padx=2, pady=2)
        cb = tk.Checkbutton(kart, text=baslik, variable=v, bg="white",
                             font=("Segoe UI", 10, "bold"), fg="#B71C1C",
                             padx=4, pady=4)
        cb.pack(anchor="w")
        # Tooltip yerine küçük bir alt metin
        tk.Label(kart, text=tip_text, bg="white", fg="#546E7A",
                 font=("Segoe UI", 8), wraplength=240,
                 justify="left").pack(anchor="w", padx=24, pady=(0, 4))

    # Canlı önizleme — tek satır
    onizleme_lbl = tk.Label(sec1, text="", bg="#FFF9C4", fg="#5D4037",
                              font=("Consolas", 9, "bold"),
                              anchor="w", padx=8, pady=4,
                              bd=1, relief="solid")
    onizleme_lbl.pack(fill="x", pady=(4, 0))

    def _onizleme_guncelle(*_):
        kurallar = []
        if var_uyari.get():    kurallar.append("uyarı yok")
        if var_mesaj.get():    kurallar.append("mesaj yok")
        if var_rapor.get():    kurallar.append("rapor yok")
        if var_renkli.get():   kurallar.append("beyaz reçete")
        if not kurallar:
            txt = ("✅ Hiçbir dışlama kuralı işaretli değil — "
                   "tüm satırlar tabloya gelir.")
        else:
            txt = "🚫 GETİRME koşulu:  " + "  VE  ".join(kurallar)
        onizleme_lbl.config(text=txt)

    for v in (var_uyari, var_mesaj, var_rapor, var_renkli):
        v.trace_add("write", _onizleme_guncelle)
    _onizleme_guncelle()

    # ════════════════════════════════════════════════════════════════
    # SECTION 2 — LİSTE BAZLI KURALLAR (notebook ile, tüm kalan alanı dolduruyor)
    # ════════════════════════════════════════════════════════════════
    sec2 = tk.LabelFrame(
        win,
        text=" 2️⃣  LİSTE BAZLI KURALLAR  ─  Veritabanından seç veya manuel ekle ",
        bg="#FFF8E1", fg="#E65100",
        font=("Segoe UI", 10, "bold"),
        padx=6, pady=4, bd=2, relief="ridge")
    sec2.pack(fill="both", expand=True, padx=10, pady=(0, 4))

    nb = ttk.Notebook(sec2)
    nb.pack(fill="both", expand=True, padx=2, pady=2)

    # Her tip için açıklama metni
    SEKME_ACIKLAMALARI = {
        "ilac": ("🏷️ Tam ilaç adı eşleşmesi (UrunAdi). Örn: "
                  "'TRAVAZOL %1+%0,1 KREM (15 G)'. Liste içinden "
                  "seçilenler eşit (=) karşılaştırmasıyla SQL'de filtrelenir."),
        "etken": ("🧪 Etken madde adının ilaç adı içinde geçtiği satırlar. "
                   "LIKE %X% kullanır. Örn: 'METFORMIN' yazınca tüm "
                   "metformin içeren ilaçlar etkilenir."),
        "atc": ("🧬 ATC kodu veya Türkçe adı (Urun.UrunATCId → ATC tablosu). "
                 "Örn: 'C09AA' (ACE inhibitörleri) veya 'NÖROPATİK AĞRI'."),
        "farma": ("💊 Farmasötik form — ilaç adında geçen anahtar kelime. "
                   "LIKE %X% kullanır. Örn: 'KREM', 'ŞURUP', 'AMPUL'."),
        "tesis": ("🏥 Hastane kodu veya adı (Hastane tablosu). "
                   "Örn: '11340187' veya 'BAĞCILAR EĞİTİM HASTANESİ'."),
        "esdeger": ("🔁 Eşdeğer grubu — aynı etken/doz/form'a sahip "
                     "ilaçlar tek bir grup ID'si paylaşır. Bir CALPOL ŞURUP "
                     "seçtiğinde tüm muadil şuruplar (PAROL, TYLOL vb.) "
                     "aynı kuralla etkilenir. Picker'da ID + örnek ilaç adı "
                     "görürsün; SQL filtresi UrunEsdegerId ile çalışır."),
    }

    # Her tip için aynı arayüz — per-item içerir/içermez
    sekmeler = {}
    for tip in LISTE_TIPLERI:
        kurallar = ay.get(tip) or []
        sekme = tk.Frame(nb, bg="#FAFAFA")
        nb.add(sekme, text=LISTE_ETIKETLERI[tip])

        # Açıklama
        tk.Label(sekme, text=SEKME_ACIKLAMALARI.get(tip, ""),
                  bg="#FFFDE7", fg="#5D4037",
                  font=("Segoe UI", 9), justify="left",
                  wraplength=800, anchor="w", padx=8, pady=4,
                  bd=1, relief="solid"
                  ).pack(fill="x", padx=8, pady=(8, 4))

        # Kural listesi (Treeview: Mod | Değer)
        tv_frm = tk.Frame(sekme, bg="#FAFAFA")
        tv_frm.pack(fill="both", expand=True, padx=8, pady=4)

        sb = ttk.Scrollbar(tv_frm)
        sb.pack(side="right", fill="y")
        tv = ttk.Treeview(tv_frm, columns=("mod", "deger"),
                            show="headings", height=8,
                            yscrollcommand=sb.set, selectmode="browse")
        tv.heading("mod", text="Mod")
        tv.heading("deger", text="Değer")
        tv.column("mod", width=110, stretch=False, anchor="w")
        tv.column("deger", width=600, stretch=True, anchor="w")
        tv.pack(side="left", fill="both", expand=True)
        sb.config(command=tv.yview)
        # Renk tag'leri
        tv.tag_configure("icerir", background="#E8F5E9", foreground="#1B5E20")
        tv.tag_configure("icermez", background="#FFEBEE", foreground="#B71C1C")

        # Mevcut kuralları yükle
        for kural in kurallar:
            mod = kural.get("mod", "icerir")
            deger = kural.get("deger", "")
            etiket = "✅ İçerir" if mod == "icerir" else "❌ İçermez"
            tv.insert("", "end", values=(etiket, deger), tags=(mod,))

        # ── Yeni kural ekleme bar ──
        ekle_frm = tk.LabelFrame(sekme, text=" ➕ Yeni Kural Ekle ",
                                    bg="#E3F2FD", fg="#0D47A1",
                                    font=("Segoe UI", 9, "bold"))
        ekle_frm.pack(fill="x", padx=8, pady=4)

        yeni_mod_var = tk.StringVar(value="icermez")
        rad_frm = tk.Frame(ekle_frm, bg="#E3F2FD")
        rad_frm.pack(fill="x", padx=4, pady=4)
        tk.Label(rad_frm, text="Mod:", bg="#E3F2FD",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=(2, 6))
        tk.Radiobutton(rad_frm, text="✅ İçerir (sadece bu gelsin)",
                        variable=yeni_mod_var, value="icerir",
                        bg="#E3F2FD"
                        ).pack(side="left", padx=4)
        tk.Radiobutton(rad_frm, text="❌ İçermez (bu gelmesin)",
                        variable=yeni_mod_var, value="icermez",
                        bg="#E3F2FD"
                        ).pack(side="left", padx=4)

        # Listeden seç butonu — DB'den arama+seçim popup'ı açar
        def _liste_ac(tv=tv, mod_var=yeni_mod_var, _tip=tip):
            def _on_secim(degerler, mod):
                for v in degerler:
                    v = (v or "").strip()
                    if not v:
                        continue
                    # Aynı (mod, deger) varsa atla
                    var = False
                    for iid in tv.get_children():
                        vals = tv.item(iid, "values")
                        tags = tv.item(iid, "tags") or ()
                        if vals[1] == v and (
                                ("icerir" in tags and mod == "icerir") or
                                ("icermez" in tags and mod == "icermez")):
                            var = True
                            break
                    if var:
                        continue
                    etiket = "✅ İçerir" if mod == "icerir" else "❌ İçermez"
                    tv.insert("", "end", values=(etiket, v), tags=(mod,))
            _liste_secici_pencere_ac(win, db, _tip, _on_secim)

        tk.Button(rad_frm, text="📂 Veritabanından Listeden Seç...",
                   bg="#1976D2", fg="white", bd=0, padx=10, pady=2,
                   font=("Segoe UI", 9, "bold"),
                   command=_liste_ac
                   ).pack(side="right", padx=4)

        # Manuel giriş satırı (mevcut)
        ent_frm = tk.Frame(ekle_frm, bg="#E3F2FD")
        ent_frm.pack(fill="x", padx=4, pady=(0, 4))
        tk.Label(ent_frm, text="Manuel:", bg="#E3F2FD",
                  font=("Segoe UI", 9)).pack(side="left", padx=(2, 4))
        ent_yeni = tk.Entry(ent_frm, font=("Segoe UI", 10))
        ent_yeni.pack(side="left", fill="x", expand=True, padx=(0, 4))

        def _ekle(tv=tv, ent=ent_yeni, mv=yeni_mod_var):
            v = (ent.get() or "").strip()
            if not v:
                return
            # Aynı (mod, değer) varsa atla
            for iid in tv.get_children():
                vals = tv.item(iid, "values")
                if vals[1] == v and (
                        ("icerir" in vals[0] and mv.get() == "icerir") or
                        ("İçermez" in vals[0] and mv.get() == "icermez")):
                    ent.delete(0, tk.END)
                    return
            mod = mv.get()
            etiket = "✅ İçerir" if mod == "icerir" else "❌ İçermez"
            tv.insert("", "end", values=(etiket, v), tags=(mod,))
            ent.delete(0, tk.END)

        def _sil(tv=tv):
            for iid in list(tv.selection()):
                tv.delete(iid)

        def _modu_degistir(tv=tv):
            # Seçili satırların modunu içerir↔içermez tersine çevir
            for iid in list(tv.selection()):
                vals = tv.item(iid, "values")
                tags = tv.item(iid, "tags") or ()
                yeni = "icermez" if "icerir" in tags else "icerir"
                etiket = "✅ İçerir" if yeni == "icerir" else "❌ İçermez"
                tv.item(iid, values=(etiket, vals[1]), tags=(yeni,))

        def _temizle(tv=tv):
            if messagebox.askyesno(
                    "Onay",
                    "Bu listedeki tüm kuralları silmek istediğine "
                    "emin misin?"):
                for iid in list(tv.get_children()):
                    tv.delete(iid)

        tk.Button(ent_frm, text="➕ Ekle", bg="#43A047", fg="white",
                   bd=0, padx=10, command=_ekle,
                   font=("Segoe UI", 9, "bold")
                   ).pack(side="left", padx=2)

        # Çift tık → mod değiştir
        tv.bind("<Double-1>", lambda e, fn=_modu_degistir: fn())
        # Enter → ekle
        ent_yeni.bind("<Return>", lambda e, fn=_ekle: fn())

        # ── Liste işlemleri butonları ──
        btn_frm = tk.Frame(sekme, bg="#FAFAFA")
        btn_frm.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(btn_frm, text="🔄 Modu Değiştir",
                   bg="#1976D2", fg="white", bd=0, padx=10,
                   command=_modu_degistir
                   ).pack(side="left", padx=2)
        tk.Button(btn_frm, text="➖ Seçileni Sil",
                   bg="#E53935", fg="white", bd=0, padx=10,
                   command=_sil
                   ).pack(side="left", padx=2)
        tk.Button(btn_frm, text="🧹 Tümünü Temizle",
                   bg="#FFE082", fg="#5D4037", bd=0, padx=10,
                   command=_temizle
                   ).pack(side="left", padx=2)
        tk.Label(btn_frm, text=" 💡 Çift tık ile satırın modunu hızlı "
                                "değiştirebilirsin",
                  bg="#FAFAFA", fg="#546E7A",
                  font=("Segoe UI", 8, "italic")
                  ).pack(side="left", padx=8)

        sekmeler[tip] = {"tv": tv}

    # ───── ALT BUTON BAR İÇERİĞİ (frame zaten yukarıda paketlendi) ─────

    def _kaydet_kapat():
        yeni = {
            "renkli_getir": var_renkli.get(),
            "mesaj_getir":  var_mesaj.get(),
            "uyari_getir":  var_uyari.get(),
            "rapor_getir":  var_rapor.get(),
        }
        for tip, w in sekmeler.items():
            tv = w["tv"]
            kurallar = []
            for iid in tv.get_children():
                vals = tv.item(iid, "values")
                tags = tv.item(iid, "tags") or ()
                mod = "icerir" if "icerir" in tags else "icermez"
                kurallar.append({"deger": vals[1], "mod": mod})
            yeni[tip] = kurallar
        ayarlari_kaydet(yeni)
        if on_save:
            try:
                on_save(yeni)
            except Exception as e:
                logger.exception("on_save hatası: %s", e)
        win.destroy()

    def _varsayilana_don():
        if not messagebox.askyesno("Onay",
                                       "Tüm ayarlar varsayılana dönecek "
                                       "(4 içerik açık, liste kuralları "
                                       "boş). Devam edilsin mi?"):
            return
        var_renkli.set(True)
        var_mesaj.set(True)
        var_uyari.set(True)
        var_rapor.set(True)
        for w in sekmeler.values():
            tv = w["tv"]
            for iid in list(tv.get_children()):
                tv.delete(iid)

    tk.Button(alt, text="↺ Varsayılana Dön", bg="#FFE082", fg="#5D4037",
               bd=0, padx=10, command=_varsayilana_don,
               font=("Segoe UI", 9, "bold")
               ).pack(side="left", padx=8, pady=8)
    tk.Button(alt, text="❌ İptal", bg="#90A4AE", fg="white",
               bd=0, padx=12, command=win.destroy,
               font=("Segoe UI", 9, "bold")
               ).pack(side="right", padx=4, pady=8)
    tk.Button(alt, text="💾 Kaydet & Uygula", bg="#1976D2", fg="white",
               bd=0, padx=12, command=_kaydet_kapat,
               font=("Segoe UI", 9, "bold")
               ).pack(side="right", padx=4, pady=8)

    win.grab_set()
