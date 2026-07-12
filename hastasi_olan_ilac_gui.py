"""
Hastasi Olan Ilaclar Penceresi

Siparis modulunden acilan ayri pencere. Son 12 ayda en az 2 alimi olan ve
tahmini bitisi cari ay icine dusen ilaclari hasta bazli listeler. Kullanici
checkbox'la sectigi satirlari ana siparis listesine aktarabilir.

Algoritma siparis_verme_gui'den bagimsiz - kendi sorgusunu hastasi_olan_ilac_db
uzerinden calistirir; ana listeye geri donus on_ekle callback'i uzerinden olur.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
from typing import Callable, List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

TURKCE_AYLAR = ('Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz',
                'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara')


def _son_12_ay_listesi() -> List[Tuple[int, int, str, str]]:
    """En eski → en yeni sırayla son 12 ayı (yil, ay, 'YYYY-MM' anahtar, kisa etiket).

    Bugun cari ay olarak en sonda yer alir; 11 ay geri gidilir.
    """
    bugun = date.today()
    base = bugun.year * 12 + (bugun.month - 1)
    aylar: List[Tuple[int, int, str, str]] = []
    for i in range(12):
        toplam = base - (11 - i)
        ay_y, ay_idx = divmod(toplam, 12)
        ay_m = ay_idx + 1
        anahtar = f"{ay_y:04d}-{ay_m:02d}"
        etiket = f"{TURKCE_AYLAR[ay_m - 1]} {ay_y % 100:02d}"
        aylar.append((ay_y, ay_m, anahtar, etiket))
    return aylar


class HastasiOlanIlacGUI:
    """Hastasi olan ilac onerileri penceresi."""

    FILTRELER = (
        ('bu_ay', 'Bu Ay'),
        ('gelecek_ay', 'Gelecek Ay'),
        ('gecikmis', 'Gecikmis'),
        ('tumu', 'Tumu'),
    )

    def __init__(self, parent, on_ekle: Callable[[List[Dict]], int],
                 db=None):
        """
        Args:
            parent: Ust pencere (siparis_verme_gui ana penceresi).
            on_ekle: Secilen urunleri ana listeye ekleyen callback. Liste alir
                     ve eklenen sayiyi (int) dondurur.
            db: Opsiyonel BotanikDB; verilmezse modul kendi baglantisini kurar.
        """
        self.parent = parent
        self.on_ekle = on_ekle
        self.db = db
        self.window = tk.Toplevel(parent)
        self.window.title("Hastasi Olan Ilaclar - Siparis Onerisi")
        self.window.geometry("1820x720")

        self.tum_kayitlar: List[Dict] = []
        self.gosterilen: List[Dict] = []
        self.secili_idler = set()
        self.aylik_data: Dict[int, Dict[str, int]] = {}
        self._aylar = _son_12_ay_listesi()
        self._scroll_kilit = False

        self.filtre_var = tk.StringVar(value='bu_ay')

        self._ui_olustur()
        self.window.after(100, self._verileri_yukle)

    def _ui_olustur(self):
        # Ust filtre cubugu
        ust = tk.Frame(self.window, bg='#37474F')
        ust.pack(fill=tk.X, padx=4, pady=4)

        tk.Label(ust, text="Filtre:", bg='#37474F', fg='white',
                 font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=(8, 4),
                                                  pady=6)
        for kod, etiket in self.FILTRELER:
            tk.Radiobutton(ust, text=etiket, variable=self.filtre_var,
                           value=kod, bg='#37474F', fg='white',
                           selectcolor='#263238', activebackground='#455A64',
                           activeforeground='white',
                           font=('Arial', 10),
                           command=self._filtre_uygula
                           ).pack(side=tk.LEFT, padx=4, pady=4)

        tk.Button(ust, text="Yenile", command=self._verileri_yukle,
                  bg='#1976D2', fg='white', font=('Arial', 9, 'bold'),
                  relief='flat', padx=10
                  ).pack(side=tk.LEFT, padx=(20, 4), pady=4)

        self.durum_label = tk.Label(ust, text="Yukleniyor...",
                                    bg='#37474F', fg='#B0BEC5',
                                    font=('Arial', 9))
        self.durum_label.pack(side=tk.LEFT, padx=12)

        # Tablo
        orta = tk.Frame(self.window)
        orta.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Sol cerceve: ana tablo + dikey scrollbar
        sol_frame = tk.Frame(orta)
        sol_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        kolonlar = [
            ('Sec', 'Sec', 50),
            ('Detay', 'Detay', 50),
            ('UrunAdi', 'Ilac Adi', 280),
            ('Hasta', 'Hasta', 180),
            ('TCKN', 'TCKN', 110),
            ('SonAlim', 'Son Alim', 100),
            ('SonKutu', 'Kutu', 50),
            ('TahminiBitis', 'Tahmini Bitis', 110),
            ('AlimSayisi', 'Alim', 50),
            ('Olasilik', 'Ihtimal', 70),
            ('Onerilen', 'Onerilen', 80),
            ('Stok', 'Stok', 60),
        ]

        self.tree = ttk.Treeview(sol_frame, columns=[k[0] for k in kolonlar],
                                  show='headings', selectmode='none',
                                  height=20)
        for kod, baslik, w in kolonlar:
            self.tree.heading(kod, text=baslik)
            anchor = ('center' if kod in ('Sec', 'Detay', 'SonKutu',
                                          'AlimSayisi', 'Olasilik',
                                          'Onerilen', 'Stok')
                      else 'w')
            self.tree.column(kod, width=w, minwidth=30, anchor=anchor)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Sol/sag ayirici (1 px soluk lila dikey cizgi)
        # NOT: bu cizgi disinda sag tarafa USTTEN ek dolgu/etiket EKLEME!
        # Aksi halde aylik tablo basligi ana tablonun altina kayar.
        tk.Frame(orta, bg='#B39DDB', width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Sag cerceve: aylik cikis tablosu (son 12 ay) — dogrudan, sarmalayicisiz.
        sag_frame = tk.Frame(orta)
        sag_frame.pack(side=tk.LEFT, fill=tk.Y)

        ay_kodlari = [f"ay_{i}" for i in range(12)]
        self.aylik_tree = ttk.Treeview(sag_frame, columns=ay_kodlari,
                                       show='headings', selectmode='none',
                                       height=20)
        for i, kod in enumerate(ay_kodlari):
            etiket = self._aylar[i][3]
            self.aylik_tree.heading(kod, text=etiket)
            self.aylik_tree.column(kod, width=52, minwidth=40,
                                   anchor='center', stretch=False)
        self.aylik_tree.pack(side=tk.LEFT, fill=tk.Y)

        # Sag kenarlik (vsb'den once, soluk lila 1 px dikey cizgi)
        tk.Frame(orta, bg='#B39DDB', width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Paylasilan dikey scrollbar (en saga)
        vsb = ttk.Scrollbar(orta, orient='vertical')
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        def _tree_scroll_set(first, last):
            vsb.set(first, last)
            if not self._scroll_kilit:
                self._scroll_kilit = True
                try:
                    self.aylik_tree.yview_moveto(first)
                finally:
                    self._scroll_kilit = False

        def _aylik_scroll_set(first, last):
            vsb.set(first, last)
            if not self._scroll_kilit:
                self._scroll_kilit = True
                try:
                    self.tree.yview_moveto(first)
                finally:
                    self._scroll_kilit = False

        def _vsb_command(*args):
            self.tree.yview(*args)
            self.aylik_tree.yview(*args)

        self.tree.configure(yscrollcommand=_tree_scroll_set)
        self.aylik_tree.configure(yscrollcommand=_aylik_scroll_set)
        vsb.configure(command=_vsb_command)

        def _on_mw(event):
            adim = -1 if event.delta > 0 else 1
            self.tree.yview_scroll(adim, 'units')
            self.aylik_tree.yview_scroll(adim, 'units')
            return 'break'

        self.tree.bind('<MouseWheel>', _on_mw)
        self.aylik_tree.bind('<MouseWheel>', _on_mw)

        style = ttk.Style()
        style.configure('Hasta.Treeview', font=('Arial', 10), rowheight=26)
        style.configure('Hasta.Treeview.Heading', font=('Arial', 10, 'bold'))
        self.tree.configure(style='Hasta.Treeview')

        # Aylik tablo: ana tablonun renkleriyle KARISMASIN diye mor paleti.
        # Yesil/sari/turuncu/kirmizi/mavi tag'lerden ayrismasi icin secildi.
        # ONEMLI: rowheight ve heading font ana tabloyla AYNI olmali, yoksa
        # satirlar arasi hiza kayar.
        style.configure('Aylik.Treeview',
                        font=('Arial', 10), rowheight=26,
                        background='#EDE7F6',
                        fieldbackground='#EDE7F6',
                        foreground='#311B92',
                        bordercolor='#B39DDB',
                        borderwidth=0)
        style.configure('Aylik.Treeview.Heading',
                        font=('Arial', 10, 'bold'),
                        background='#7E57C2',
                        foreground='white',
                        relief='flat',
                        borderwidth=1,
                        bordercolor='#B39DDB')
        self.aylik_tree.configure(style='Aylik.Treeview')

        # Zebra cok hafif: birbirine yakin iki ton -> satirlar arasi
        # ince silik yatay cizgi efekti.
        self.aylik_tree.tag_configure('aylik_normal',
                                      background='#EDE7F6',
                                      foreground='#311B92')
        self.aylik_tree.tag_configure('aylik_zebra',
                                      background='#E5DDF2',
                                      foreground='#311B92')

        self.tree.tag_configure('o100', background='#C8E6C9',
                                foreground='#1B5E20')
        self.tree.tag_configure('o75', background='#FFF9C4',
                                foreground='#827717')
        self.tree.tag_configure('o50', background='#FFE0B2',
                                foreground='#E65100')
        self.tree.tag_configure('secili', background='#1565C0',
                                foreground='white')
        self.tree.tag_configure('gecikmis', background='#FFCDD2',
                                foreground='#B71C1C')

        self.tree.bind('<Button-1>', self._tikla_toggle)

        # Alt buton cubugu
        alt = tk.Frame(self.window, bg='#263238')
        alt.pack(fill=tk.X, padx=4, pady=4)

        tk.Button(alt, text="Tumunu Sec", command=self._tumunu_sec,
                  bg='#455A64', fg='white', font=('Arial', 9),
                  relief='flat', padx=10
                  ).pack(side=tk.LEFT, padx=4, pady=4)
        tk.Button(alt, text="Secimi Temizle", command=self._secimi_temizle,
                  bg='#455A64', fg='white', font=('Arial', 9),
                  relief='flat', padx=10
                  ).pack(side=tk.LEFT, padx=4, pady=4)

        tk.Button(alt, text="Kapat", command=self.window.destroy,
                  bg='#B71C1C', fg='white', font=('Arial', 9),
                  relief='flat', padx=10
                  ).pack(side=tk.RIGHT, padx=4, pady=4)
        tk.Button(alt, text="Secilenleri Ana Listeye Ekle",
                  command=self._secilileri_ekle,
                  bg='#2E7D32', fg='white', font=('Arial', 10, 'bold'),
                  relief='raised', padx=14, pady=4
                  ).pack(side=tk.RIGHT, padx=4, pady=4)

    def _verileri_yukle(self):
        try:
            from hastasi_olan_ilac_db import HastasiOlanIlacDB
            analiz = HastasiOlanIlacDB(db=self.db)
            self.tum_kayitlar = analiz.hastasi_olan_ilaclari_getir()

            urun_ids = [r.get('UrunId') for r in self.tum_kayitlar
                        if r.get('UrunId')]
            try:
                self.aylik_data = analiz.aylik_cikis_topla(urun_ids)
            except Exception as e:
                logger.warning("Aylik cikis verisi alinamadi: %s", e)
                self.aylik_data = {}

            self.durum_label.config(
                text=f"Toplam: {len(self.tum_kayitlar)} kayit"
            )
            self.secili_idler.clear()
            self._filtre_uygula()
        except Exception as e:
            logger.exception("Veri yukleme hatasi")
            messagebox.showerror("Hata", f"Veri yuklenemedi:\n{e}",
                                 parent=self.window)
            self.durum_label.config(text=f"Hata: {e}")

    def _tarihe_cevir(self, deger) -> Optional[date]:
        if deger is None:
            return None
        if isinstance(deger, datetime):
            return deger.date()
        if isinstance(deger, date):
            return deger
        try:
            return datetime.strptime(str(deger)[:10], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    def _filtre_uygula(self):
        f = self.filtre_var.get()
        bugun = date.today()
        ay_simdi = (bugun.year, bugun.month)
        if bugun.month == 12:
            ay_gelecek = (bugun.year + 1, 1)
        else:
            ay_gelecek = (bugun.year, bugun.month + 1)
        ay_basi = bugun.replace(day=1)

        sonuc = []
        for r in self.tum_kayitlar:
            tb_d = self._tarihe_cevir(r.get('TahminiBitis'))
            if tb_d is None:
                continue
            ay_kayit = (tb_d.year, tb_d.month)
            if f == 'bu_ay':
                if ay_kayit != ay_simdi:
                    continue
            elif f == 'gelecek_ay':
                if ay_kayit != ay_gelecek:
                    continue
            elif f == 'gecikmis':
                if tb_d >= ay_basi:
                    continue
            sonuc.append(r)

        self.gosterilen = sonuc
        self._tabloyu_doldur()

    def _tabloyu_doldur(self):
        self.tree.delete(*self.tree.get_children())
        self.aylik_tree.delete(*self.aylik_tree.get_children())
        bugun = date.today()
        ay_basi = bugun.replace(day=1)

        # Ilac basina toplam hasta sayisi (filtreden BAGIMSIZ, tum kayitlar
        # uzerinden) — hasta adinin yanina "(n)" olarak yazilir; ayni ilaci
        # kac hastanin kullandigi siparis miktari kararinda onemli.
        urun_hastalari: Dict[int, set] = {}
        for k in self.tum_kayitlar:
            uid = k.get('UrunId')
            if uid is not None:
                urun_hastalari.setdefault(uid, set()).add(k.get('MusteriId'))
        hasta_sayisi = {uid: len(m) for uid, m in urun_hastalari.items()}

        for idx, r in enumerate(self.gosterilen):
            urun_id = r.get('UrunId')
            musteri_id = r.get('MusteriId')
            anahtar = (urun_id, musteri_id)
            sec_isaret = '[X]' if anahtar in self.secili_idler else '[ ]'

            tb_d = self._tarihe_cevir(r.get('TahminiBitis'))
            tb_str = tb_d.strftime('%Y-%m-%d') if tb_d else ''
            sa_d = self._tarihe_cevir(r.get('SonAlimTarihi'))
            sa_str = sa_d.strftime('%Y-%m-%d') if sa_d else ''

            ad = (r.get('MusteriAdiSoyadi') or '').strip()
            n_hasta = hasta_sayisi.get(urun_id, 1)
            ad = f"{ad}  ({n_hasta})"
            tckn = (r.get('MusteriTCKN') or '').strip() if r.get('MusteriTCKN') else ''

            olasilik = r.get('Olasilik', 0)
            olasilik_str = f"%{olasilik}"

            tags = []
            if anahtar in self.secili_idler:
                tags.append('secili')
            elif tb_d and tb_d < ay_basi:
                tags.append('gecikmis')
            elif olasilik >= 100:
                tags.append('o100')
            elif olasilik >= 75:
                tags.append('o75')
            elif olasilik >= 50:
                tags.append('o50')

            iid = f"row_{urun_id}_{musteri_id}"
            self.tree.insert('', tk.END, iid=iid, values=(
                sec_isaret,
                '📋',
                r.get('UrunAdi', ''),
                ad,
                tckn,
                sa_str,
                r.get('SonKutu', '') or '',
                tb_str,
                r.get('AlimSayisi', '') or '',
                olasilik_str,
                r.get('OnerilenMiktar', '') or '',
                r.get('Stok', 0) or 0,
            ), tags=tuple(tags))

            # Sag panel: ayni iid ile aylik dagilim. Hucre 0 ise bos goster.
            urun_aylik = self.aylik_data.get(urun_id, {})
            aylik_values = []
            for _y, _m, anahtar, _label in self._aylar:
                miktar = urun_aylik.get(anahtar, 0)
                aylik_values.append(miktar if miktar else '')
            aylik_tag = 'aylik_zebra' if idx % 2 else 'aylik_normal'
            self.aylik_tree.insert('', tk.END, iid=iid, values=aylik_values,
                                   tags=(aylik_tag,))

        self.durum_label.config(
            text=(f"Gosterilen: {len(self.gosterilen)} | "
                  f"Secili: {len(self.secili_idler)} | "
                  f"Toplam: {len(self.tum_kayitlar)}")
        )

    def _tikla_toggle(self, event):
        bolge = self.tree.identify('region', event.x, event.y)
        if bolge != 'cell':
            return
        sutun = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)
        if not item:
            return
        try:
            urun_id_str, musteri_id_str = item.replace('row_', '').split('_')
            urun_id = int(urun_id_str)
            musteri_id = int(musteri_id_str)
        except (ValueError, AttributeError):
            return

        if sutun == '#1':  # Sec sutunu - secimi toggle et
            anahtar = (urun_id, musteri_id)
            if anahtar in self.secili_idler:
                self.secili_idler.discard(anahtar)
            else:
                self.secili_idler.add(anahtar)
            self._tabloyu_doldur()
        elif sutun == '#2':  # Detay sutunu - detay penceresi ac
            self._detay_penceresi_ac(urun_id, musteri_id)

    def _detay_penceresi_ac(self, urun_id: int, musteri_id: int):
        """Bir satirin detay (cikis gecmisi) penceresini ac."""
        try:
            from ilac_cikis_detay_gui import IlacCikisDetayGUI
        except ImportError as e:
            messagebox.showerror(
                "Modul Yok",
                f"Detay modulu yuklenemedi:\n{e}",
                parent=self.window
            )
            return

        kayit = next(
            (r for r in self.tum_kayitlar
             if r.get('UrunId') == urun_id and r.get('MusteriId') == musteri_id),
            None
        )
        if not kayit:
            return

        ilgili_hasta = {
            'MusteriId': kayit.get('MusteriId'),
            'MusteriAdiSoyadi': (kayit.get('MusteriAdiSoyadi') or '').strip(),
            'MusteriTCKN': (kayit.get('MusteriTCKN') or '').strip()
                            if kayit.get('MusteriTCKN') else '',
        }

        IlacCikisDetayGUI(
            parent=self.window,
            urun_id=urun_id,
            urun_adi=kayit.get('UrunAdi', ''),
            ilgili_hasta=ilgili_hasta,
            db=self.db,
        )

    def _tumunu_sec(self):
        for r in self.gosterilen:
            self.secili_idler.add((r.get('UrunId'), r.get('MusteriId')))
        self._tabloyu_doldur()

    def _secimi_temizle(self):
        self.secili_idler.clear()
        self._tabloyu_doldur()

    def _secilileri_ekle(self):
        if not self.secili_idler:
            messagebox.showinfo(
                "Bilgi",
                "Once satir secin (Sec sutununa tiklayin).",
                parent=self.window
            )
            return

        secilenler = []
        for r in self.tum_kayitlar:
            anahtar = (r.get('UrunId'), r.get('MusteriId'))
            if anahtar in self.secili_idler:
                miktar = r.get('OnerilenMiktar', 1) or 1
                secilenler.append({
                    'UrunId': r.get('UrunId'),
                    'UrunAdi': r.get('UrunAdi', ''),
                    'Barkod': '',
                    'Miktar': miktar,
                    'MF': '',
                    'Toplam': miktar,
                    'Stok': r.get('Stok', 0) or 0,
                    'AylikOrt': 0,
                    'Selcuk': '', 'Alliance': '', 'Sancak': '',
                    'Iskoop': '', 'Farmazon': '',
                    '_kaynak_hasta': r.get('MusteriAdiSoyadi', ''),
                })

        if not secilenler:
            messagebox.showwarning("Uyari", "Secilen satir bulunamadi.",
                                   parent=self.window)
            return

        try:
            eklenen = self.on_ekle(secilenler) or 0
        except Exception as e:
            logger.exception("Ana listeye ekleme hatasi")
            messagebox.showerror("Hata",
                                 f"Ana listeye ekleme basarisiz:\n{e}",
                                 parent=self.window)
            return

        atlanan = len(secilenler) - eklenen
        mesaj = f"{eklenen} urun ana siparis listesine eklendi."
        if atlanan > 0:
            mesaj += f"\n{atlanan} urun zaten listedeydi (atlandi)."
        messagebox.showinfo("Basarili", mesaj, parent=self.window)
        self._secimi_temizle()
