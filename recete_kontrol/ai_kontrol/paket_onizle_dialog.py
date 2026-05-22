"""Paket Önizle Dialog — AI'a gönderilmeden önce paket JSON'unu göster.

Kullanıcı AI butonuna basmadan önce seçili satırın TAM paket içeriğini
görür. Şeffaflık + güven + KVKK uyumu.

İçerik:
    • Üst sekmeli görünüm (Notebook):
        - "Paket JSON"   → paket_olusturucu.paket_olustur() çıktısı
        - "Tam Prompt"   → AI'a gidecek sistem + few-shot + paket birleşimi
    • Kopyala butonu (panoya kopyala)
    • Dosyaya Kaydet butonu (.json / .txt)
    • Karakter sayısı + tahmini token bilgisi
"""
from __future__ import annotations

import json
import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Kabaca token tahmini (1 token ~ 3.5 karakter Türkçe metinde)
def _tahmini_token(metin: str) -> int:
    if not metin:
        return 0
    return int(len(metin) / 3.5)


class PaketOnizleDialog(tk.Toplevel):
    """Bir reçete paketini AI'a göndermeden önizleyen modal pencere."""

    def __init__(
        self,
        parent: tk.Misc,
        paket: Dict[str, Any],
        *,
        baslik: str = "🔍 AI Paketi Önizleme",
        ai_gonder_callback: Optional[callable] = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.paket = paket
        self.ai_gonder_callback = ai_gonder_callback

        self.title(baslik)
        self.geometry("980x720")
        self.minsize(720, 560)
        self.transient(parent)
        self.grab_set()

        self._kur_ui()
        self._doldur()

        self.protocol("WM_DELETE_WINDOW", self._kapat)
        self.bind("<Escape>", lambda _e: self._kapat())

    def _kur_ui(self) -> None:
        # Üst başlık + meta bilgi
        ust = tk.Frame(self, bg="#0277BD", height=46)
        ust.pack(fill="x", side="top")
        ust.pack_propagate(False)
        tk.Label(ust, text="🔍 AI'a Gönderilecek Paket — Önizleme",
                 bg="#0277BD", fg="white",
                 font=("Segoe UI", 12, "bold")).pack(side="left", padx=12, pady=10)

        recete = self.paket.get("recete") or {}
        ilac = recete.get("ilac") or {}
        hasta = self.paket.get("hasta") or {}
        meta_metin = (
            f"Reçete: {recete.get('recete_no', '?')}  |  "
            f"İlaç: {ilac.get('urun_adi', '?')[:40]}  |  "
            f"Hasta: {hasta.get('yas', '?')}y/{hasta.get('cinsiyet', '?')}  "
            f"(TC hash {hasta.get('tc_hash', '')[:8]}...)"
        )
        tk.Label(ust, text=meta_metin, bg="#0277BD", fg="#E1F5FE",
                 font=("Segoe UI", 9)).pack(side="right", padx=12)

        # Notebook (sekmeli içerik)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # Sekme 1: Paket JSON
        frame_paket = tk.Frame(nb, bg="white")
        nb.add(frame_paket, text="📦 Paket JSON (AI'a giden veri)")
        self.txt_paket = self._scrollable_text(frame_paket)

        # Sekme 2: Tam Prompt
        frame_prompt = tk.Frame(nb, bg="white")
        nb.add(frame_prompt, text="📝 Tam Prompt (sistem + few-shot + paket)")
        self.txt_prompt = self._scrollable_text(frame_prompt)

        # Sekme 3: Veri Kapsamı (dolu/boş özet)
        frame_kapsam = tk.Frame(nb, bg="white")
        nb.add(frame_kapsam, text="📋 Veri Kapsamı")
        self._veri_kapsami_kur(frame_kapsam)

        # Sekme 4: Anonimleştirme özeti
        frame_anon = tk.Frame(nb, bg="white")
        nb.add(frame_anon, text="🔒 Anonimleştirme")
        self._anonim_ozeti_kur(frame_anon)

        # Alt — istatistik + butonlar
        alt = tk.Frame(self, bg="#ECEFF1", height=64)
        alt.pack(fill="x", side="bottom")
        alt.pack_propagate(False)

        self.lbl_istat = tk.Label(
            alt, text="", bg="#ECEFF1", fg="#37474F",
            font=("Consolas", 9), anchor="w",
        )
        self.lbl_istat.pack(side="left", padx=12, pady=6, fill="x")

        btn_frame = tk.Frame(alt, bg="#ECEFF1")
        btn_frame.pack(side="right", padx=8, pady=6)

        ttk.Button(btn_frame, text="📋 Aktif sekmeyi kopyala",
                    command=self._kopyala).pack(side="right", padx=3)
        ttk.Button(btn_frame, text="💾 Dosyaya kaydet",
                    command=self._dosyaya_kaydet).pack(side="right", padx=3)
        if self.ai_gonder_callback:
            ttk.Button(btn_frame, text="🤖 Şimdi AI'a Gönder",
                        command=self._ai_gonder).pack(side="right", padx=3)
        ttk.Button(btn_frame, text="Kapat",
                    command=self._kapat).pack(side="right", padx=3)

        self._nb = nb

    def _scrollable_text(self, parent: tk.Misc) -> tk.Text:
        f = tk.Frame(parent, bg="white")
        f.pack(fill="both", expand=True)
        ysb = ttk.Scrollbar(f, orient="vertical")
        ysb.pack(side="right", fill="y")
        xsb = ttk.Scrollbar(f, orient="horizontal")
        xsb.pack(side="bottom", fill="x")
        txt = tk.Text(
            f, wrap="none",
            font=("Consolas", 9),
            yscrollcommand=ysb.set, xscrollcommand=xsb.set,
            bg="#FAFAFA", fg="#212121",
            bd=1, relief="solid",
        )
        txt.pack(fill="both", expand=True)
        ysb.config(command=txt.yview)
        xsb.config(command=txt.xview)
        return txt

    def _veri_kapsami_kur(self, parent: tk.Misc) -> None:
        """'Veri Kapsamı' sekmesi — hangi alanlar dolu, hangileri boş."""
        kapsam = self.paket.get("veri_kapsami") or {}
        recete = self.paket.get("recete") or {}
        ilac = (recete.get("ilac") or {})
        rapor = self.paket.get("rapor") or {}

        # Renkli durum etiketi üretici
        def renk(deger) -> tuple[str, str, str]:
            """(simge, etiket, renk)"""
            if isinstance(deger, bool):
                if deger:
                    return ("✓", "VAR", "#2E7D32")
                return ("✗", "YOK", "#C62828")
            if isinstance(deger, int):
                if deger > 0:
                    return ("✓", f"{deger} adet", "#2E7D32")
                return ("○", "0 adet", "#9E9E9E")
            if deger:
                return ("✓", str(deger)[:40], "#2E7D32")
            return ("✗", "YOK", "#C62828")

        # Tablo
        f = tk.Frame(parent, bg="white")
        f.pack(fill="both", expand=True, padx=8, pady=8)

        sutunlar = ("alan", "durum", "deger")
        tv = ttk.Treeview(f, columns=sutunlar, show="headings", height=24)
        tv.heading("alan", text="Alan")
        tv.heading("durum", text="Durum")
        tv.heading("deger", text="Değer / Sayı")
        tv.column("alan", width=320, anchor="w")
        tv.column("durum", width=60, anchor="center")
        tv.column("deger", width=300, anchor="w")
        ysb = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=ysb.set)
        ysb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)

        tv.tag_configure("dolu", background="#E8F5E9")
        tv.tag_configure("bos", background="#FFEBEE")
        tv.tag_configure("nokta", background="#F5F5F5")
        tv.tag_configure("baslik", background="#1A237E", foreground="white",
                          font=("Segoe UI", 9, "bold"))

        def ekle(baslik=None, alan=None, deger=None, ham=None):
            if baslik:
                tv.insert("", "end", values=(baslik, "", ""), tags=("baslik",))
                return
            simge, etiket, _renk = renk(deger if ham is None else ham)
            tag = "dolu" if simge == "✓" else ("nokta" if simge == "○" else "bos")
            tv.insert("", "end", values=(alan, simge, etiket if not deger or isinstance(deger, (bool, int)) else str(deger)[:60]),
                      tags=(tag,))

        # Reçete
        ekle(baslik="── REÇETE ──")
        ekle(alan="Reçete numarası", deger=recete.get("recete_no"))
        ekle(alan="Reçete tarihi", deger=recete.get("recete_tarihi"))
        ekle(alan="Reçete teşhis (ICD)", deger=recete.get("recete_teshis"))
        ekle(alan="Reçete açıklama", deger=recete.get("recete_aciklama"))
        ekle(alan="Reçete uyarı kodları", deger=recete.get("uyari_kodlari"))

        # İlaç
        ekle(baslik="── KONTROL EDİLEN İLAÇ ──")
        ekle(alan="Ürün adı", deger=ilac.get("urun_adi"))
        ekle(alan="ATC kodu", deger=ilac.get("atc_kodu"))
        ekle(alan="ATC açıklama", deger=ilac.get("atc_aciklama"))
        ekle(alan="Adet", deger=ilac.get("adet"))
        ekle(alan="Doz", deger=ilac.get("doz"))
        ekle(alan="Toplam kutu", deger=ilac.get("toplam_kutu"))

        # Doktor
        doktor = recete.get("doktor") or {}
        ekle(baslik="── DOKTOR ──")
        ekle(alan="Reçete doktor branş", deger=doktor.get("brans"))
        ekle(alan="Rapor doktor branş", deger=doktor.get("rapor_doktor_brans"))
        ekle(alan="Tesis", deger=doktor.get("tesis"))

        # Hasta
        hasta = self.paket.get("hasta") or {}
        ekle(baslik="── HASTA (anonim) ──")
        ekle(alan="Yaş", deger=hasta.get("yas"))
        ekle(alan="Cinsiyet", deger=hasta.get("cinsiyet"))
        ekle(alan="Kapsam", deger=hasta.get("kapsam"))
        ekle(alan="TC hash (ilk 8)",
              deger=(hasta.get("tc_hash") or "")[:8] + "..." if hasta.get("tc_hash") else "")

        # Rapor
        ekle(baslik="── AKTİF RAPOR ──")
        if rapor:
            ekle(alan="Rapor numarası", deger=rapor.get("rapor_no"))
            ekle(alan="Rapor tarihi", deger=rapor.get("rapor_tarihi"))
            ekle(alan="Rapor kodu", deger=rapor.get("rapor_kodu"))
            ekle(alan="Rapor teşhis",
                  deger=rapor.get("rapor_teshis"))
            ekle(alan="Rapor metni uzunluk",
                  ham=kapsam.get("rapor_metni_uzunluk", 0))
            ekle(alan="ICD listesi",
                  ham=kapsam.get("rapor_icd_sayisi", 0))
            ekle(alan="Etken madde listesi",
                  ham=kapsam.get("rapor_etken_madde_sayisi", 0))
            ekle(alan="Ek bilgiler",
                  ham=kapsam.get("rapor_ek_bilgi_sayisi", 0))
            ekle(alan="Rapor doktor branşları",
                  ham=kapsam.get("rapor_doktor_brans_sayisi", 0))
        else:
            ekle(alan="Aktif rapor", ham=False)

        # Hasta geçmişi
        ekle(baslik="── HASTA GEÇMİŞİ (Botanik DB) ──")
        ekle(alan="Diğer raporları (son 5 yıl)",
              ham=kapsam.get("hasta_diger_rapor_sayisi", 0))
        zen = kapsam.get("hasta_diger_rapor_zenginlik") or {}
        if kapsam.get("hasta_diger_rapor_sayisi", 0) > 0:
            ekle(alan="  ↳ rapor metni dolu olan",
                  ham=zen.get("metni_dolu_rapor", 0))
            ekle(alan="  ↳ toplam ICD kodu (tüm raporlar)",
                  ham=zen.get("toplam_icd", 0))
            ekle(alan="  ↳ toplam etken madde",
                  ham=zen.get("toplam_etken_madde", 0))
            ekle(alan="  ↳ toplam ek bilgi (REBTuru/Deger)",
                  ham=zen.get("toplam_ek_bilgi", 0))
            ekle(alan="  ↳ toplam doktor branş (sağlık kurulu)",
                  ham=zen.get("toplam_doktor_brans", 0))
            ekle(alan="  ↳ toplam rapor kodu",
                  ham=zen.get("toplam_rapor_kodu", 0))
        ekle(alan="İlaç geçmişi (son 24 ay)",
              ham=kapsam.get("hasta_ilac_gecmisi_sayisi", 0))
        ekle(alan="Reçetenin diğer ilaçları",
              ham=kapsam.get("recete_diger_ilac_sayisi", 0))

        # Uyarılar
        uyarilar = self.paket.get("uyarilar") or []
        ekle(baslik="── UYARILAR (DB sorgu hataları) ──")
        if uyarilar:
            for u in uyarilar:
                ekle(alan=f"[{u.get('kaynak', '')}]",
                      deger=u.get("hata") or u.get("not") or str(u))
        else:
            ekle(alan="Uyarı yok", ham=True)

    def _anonim_ozeti_kur(self, parent: tk.Misc) -> None:
        hasta = self.paket.get("hasta") or {}
        metin = (
            "═══════ KVKK ANONİMLEŞTİRME ÖZETİ ═══════\n\n"
            "Aşağıdaki veriler AI'a GÖNDERİLMEDİ:\n"
            "  ✗ Hasta TC kimlik numarası (ham)  → SHA-256 hash[:16] gönderildi\n"
            "  ✗ Hasta adı-soyadı                → Tamamen atıldı\n"
            "  ✗ Hasta doğum tarihi (ham)        → Yaş (yıl) hesaplanıp gönderildi\n"
            "  ✗ Doktor adı-soyadı               → Tamamen atıldı (branş kalır)\n\n"
            "Aşağıdaki veriler AI'a GÖNDERİLDİ (anonim):\n"
            f"  ✓ TC hash[:16]      = {hasta.get('tc_hash', '')!s}\n"
            f"  ✓ Yaş               = {hasta.get('yas', '?')}\n"
            f"  ✓ Cinsiyet          = {hasta.get('cinsiyet', '')!s}\n"
            f"  ✓ Kapsam            = {hasta.get('kapsam', '')!s}\n"
            f"  ✓ Emeklilik         = {hasta.get('emeklilik', '')!s}\n\n"
            "Reçete + ilaç + rapor klinik verisi anonimleştirme dışı\n"
            "(SUT kontrolü için zorunlu, kişi tanımlayıcı değil).\n\n"
            "Dayanak: KVKK Madde 6 (özel nitelikli kişisel veri) +\n"
            "         CLAUDE.md projesi gizlilik prensipleri.\n"
        )
        txt = tk.Text(parent, wrap="word",
                       font=("Consolas", 10),
                       bg="#FFF8E1", fg="#3E2723",
                       bd=0, padx=14, pady=12)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", metin)
        txt.config(state="disabled")

    def _doldur(self) -> None:
        # Sekme 1 — paket JSON
        paket_str = json.dumps(self.paket, ensure_ascii=False, indent=2)
        self.txt_paket.config(state="normal")
        self.txt_paket.delete("1.0", "end")
        self.txt_paket.insert("1.0", paket_str)
        self.txt_paket.config(state="disabled")

        # Sekme 2 — tam prompt
        try:
            from . import prompt_sablonlari
            tam_prompt = (
                "=== SİSTEM TALİMATLARI ===\n"
                f"{prompt_sablonlari.SISTEM_PROMPT}\n\n"
                "=== FEW-SHOT ÖRNEK ===\n"
            )
            for ornek in prompt_sablonlari.FEWSHOT_ORNEKLERI:
                etiket = ("[ÖRNEK — KULLANICI MESAJI]" if ornek["rol"] == "kullanici"
                          else "[ÖRNEK — ASİSTAN CEVABI]")
                tam_prompt += f"{etiket}\n{ornek['icerik']}\n\n"
            tam_prompt += "=== ŞİMDİKİ GÖREV (yukarıdaki paket) ===\n"
            tam_prompt += prompt_sablonlari.kullanici_mesaji_olustur(self.paket)
            tam_prompt += (
                "\n\nCevabını **sadece JSON olarak** ver. Başka açıklama, "
                "markdown fence (```) veya konuşma metni KOYMA — pür JSON."
            )
        except Exception as e:
            tam_prompt = f"(Prompt yüklenemedi: {e})"
        self.txt_prompt.config(state="normal")
        self.txt_prompt.delete("1.0", "end")
        self.txt_prompt.insert("1.0", tam_prompt)
        self.txt_prompt.config(state="disabled")

        # İstatistik
        p_char = len(paket_str)
        t_char = len(tam_prompt)
        self.lbl_istat.config(text=(
            f"Paket: {p_char:,} karakter (~{_tahmini_token(paket_str):,} token)  |  "
            f"Tam Prompt: {t_char:,} karakter (~{_tahmini_token(tam_prompt):,} token)"
        ))

    # ──────────────────────────────────────────────
    # Aksiyonlar
    # ──────────────────────────────────────────────
    def _aktif_metin(self) -> str:
        idx = self._nb.index(self._nb.select())
        if idx == 0:
            return self.txt_paket.get("1.0", "end")
        if idx == 1:
            return self.txt_prompt.get("1.0", "end")
        # anonim sekmesinde durağan metin
        return ""

    def _kopyala(self) -> None:
        metin = self._aktif_metin()
        if not metin.strip():
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(metin)
            self.update()
            messagebox.showinfo("Panoya kopyalandı",
                                f"{len(metin):,} karakter panoya kopyalandı.",
                                parent=self)
        except Exception as e:
            messagebox.showerror("Hata", f"Kopyalanamadı: {e}", parent=self)

    def _dosyaya_kaydet(self) -> None:
        metin = self._aktif_metin()
        if not metin.strip():
            return
        idx = self._nb.index(self._nb.select())
        if idx == 0:
            varsayilan = "ai_paket.json"
            tipler = [("JSON", "*.json"), ("Tüm dosyalar", "*.*")]
        else:
            varsayilan = "ai_prompt.txt"
            tipler = [("Metin", "*.txt"), ("Tüm dosyalar", "*.*")]
        yol = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".json" if idx == 0 else ".txt",
            initialfile=varsayilan,
            filetypes=tipler,
        )
        if not yol:
            return
        try:
            Path(yol).write_text(metin, encoding="utf-8")
            messagebox.showinfo("Kaydedildi", f"{yol}", parent=self)
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydedilemedi: {e}", parent=self)

    def _ai_gonder(self) -> None:
        if not self.ai_gonder_callback:
            return
        if not messagebox.askyesno(
            "AI'a Gönder",
            "Bu paket AI'a gönderilecek. Devam edilsin mi?",
            parent=self,
        ):
            return
        try:
            self.ai_gonder_callback(self.paket)
        except Exception as e:
            messagebox.showerror("Hata", f"{e}", parent=self)
        self._kapat()

    def _kapat(self) -> None:
        self.destroy()


def onizle(parent: tk.Misc, paket: Dict[str, Any],
           ai_gonder_callback: Optional[callable] = None) -> None:
    """Bir paket için modal önizleme penceresi aç."""
    PaketOnizleDialog(parent, paket, ai_gonder_callback=ai_gonder_callback)
