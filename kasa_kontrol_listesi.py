"""
Botanik Bot - Kasa Kontrol Listesi
Kasa eksik/fazla çıktığında kontrol edilecek maddeler
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

logger = logging.getLogger(__name__)


class KasaKontrolListesi:
    """Kasa Eksik/Fazla Kontrol Listesi Penceresi"""

    # Kasa fazla çıktığında kontrol edilecek maddeler
    FAZLA_KONTROL = [
        ("a", "Bir onceki gun baslangic kasasi dogru mu kontrol edildi"),
        ("b", "Aksam kasasi dogru sayildi mi"),
        ("c", "Satis ekranlarinda bekleyen veya gun ici satisi unutulan urun var mi kontrol edildi"),
        ("d", "Islemesi unutulan veresiye tahsilati durumu var mi"),
        ("e", "Bozuk para eklenmis ama kasadan butun para alinmasi unutulmus olabilir mi"),
        ("f", "Kapora alinmis kasaya konmustur - ayri bir yere not ile koyulmasi gerekir"),
        ("g", "Majistral yapilip sistemden dusulmemesi soz konusu mu"),
        ("h", "Strip, bez, igne ucu, KKI farki parasi hastadan alinmis fakat sisteme islenmemis olabilir mi"),
        ("i", "Baska eczane ile takas yapilip parasi kasaya konmus olabilir mi"),
        ("j", "Fis iptali yapilmis olabilir mi"),
        ("k", "Aktarilmayan recete var mi"),
        ("l", "Para ustu eksik verilmis olabilir mi"),
        ("m", "Iade yapilmis parasi kasadan hastaya verilmemis veya ayrilmamis olabilir mi"),
        ("n", "Olu karekod veya mal fazlasi urun satisi yapilip parasi kasaya konmus olabilir mi"),
        ("o", "Bir onceki gun satisi yapilmis fakat parasi bugun alinmis sisteme de duzgun islenmemis olabilir mi"),
    ]

    # Kasa eksik çıktığında kontrol edilecek maddeler
    EKSIK_KONTROL = [
        ("a", "Bir onceki gun baslangic kasasi eksik olabilir mi - kontrol edilmeli"),
        ("b", "Aksam kasasi yanlis sayilmistir"),
        ("c", "Dun aksamdan yapilan satis pos raporu vesaire islenmemistir"),
        ("d", "Yapilan satisin parasi alinmamistir - eksik cikan tutar olcusunde raflar gezilerek satilan urunler hatirlanmaya calisilmali"),
        ("e", "Veresiye satis veresiye islenmemistir - veresiye islemi yapilmadan tahsilat veya receteden hesaba atma islemi bitirilmeden ikinci ise asla gecilmemelidir"),
        ("f", "Ikinci POS cihazi kullanilmis fakat raporu alinmasi unutulmus islenmemistir"),
        ("g", "Bir onceki gun satisin parasi alinmis fakat satis bugun yapilmistir - satisi tamamlanmamis satislarin parasi ayri bir kilitli poset icinde muhafaza edilmelidir"),
        ("h", "Mukerrer satis kaydi islenmistir - ayni urun iki kez satilip bir kez parasi kasaya konmustur"),
        ("i", "Indirim/iskonto sisteme islenmemistir - iskonto tutari 1 TL bile olsa islenmeli ve onemsenmeli"),
        ("j", "Masraflar islenmemistir - masraf islenmeden kasadan para almak kesinlikle yasaktir"),
        ("k", "Silinmesi gereken fakat sistemde unutulmus recete varligi - hastanin odeme yuzunden almaktan vazgectigi reçeteler kontrol edilmeli"),
        ("l", "Gun ici eczacinin aldigi para islenmemis veya yanlis islenmistir"),
        ("m", "Gun ici cesitli sebeplerle kasadan para alinmasi - mecburi durumlarda kagida yazilip iki personel tarafindan sayilmali"),
        ("n", "Kasadan tibtek/sedat veya baska tedarikci firmaya odeme yapilmis fakat masraf islenmemistir"),
        ("o", "Kasadan alinan butun para bozdurulmus ama bozukla kasadan baska yere konmustur"),
        ("p", "Emanet verilmesi gereken urun parekende satilarak sisteme islenmistir"),
        ("q", "IBAN'a atilan para vardir ama unutulmus IBAN olarak islenmemistir"),
        ("r", "Komplike satislarin kafa karistirmasi - birden fazla recete, parekende, odenmeyen ilac olan recetede tahsilatin duzgun yapilmamasi"),
        ("s", "Hastanin borcu olmadigini ve parayi daha once odedigini iddia etmesi ve hakli olmasi - WhatsApp'tan eczaciya haber verilmeli"),
        ("t", "Depo veya personel odemeler cari hareketten nakit olarak islenmistir"),
        ("u", "Baska eczaneden alinan takasin parasi kasadan verilmis ama kayitlara islenmemistir"),
        ("v", "Emanetin parekendoye cevrilip satilmasi olmus fakat para kasaya konmamistir"),
        ("w", "Iskonto yuvarlama ve odeme secenekleri birbirine karistirilmistir"),
        ("x", "Son islem tarihi bugun olan gecmis recetelerin sistemi bozmus olabilme ihtimali - sistemsel hata"),
    ]

    def __init__(self, parent, fark):
        """
        parent: Ana pencere
        fark: Kasa farkı (+ fazla, - eksik)
        """
        self.parent = parent
        self.fark = fark
        self.kontrol_vars = {}
        self.pencere = None

    def goster(self):
        """Kontrol listesi penceresini göster"""
        self.pencere = tk.Toplevel(self.parent)
        self.pencere.title("Kasa Fark Kontrol Listesi")
        self.pencere.geometry("800x650")
        self.pencere.transient(self.parent)
        self.pencere.grab_set()
        self.pencere.configure(bg='#FAFAFA')

        # Pencereyi ortala
        self.pencere.update_idletasks()
        x = (self.pencere.winfo_screenwidth() - 800) // 2
        y = (self.pencere.winfo_screenheight() - 650) // 2
        self.pencere.geometry(f"800x650+{x}+{y}")

        # Başlık
        if self.fark > 0:
            baslik_text = f"KASA FAZLA CIKTI: +{self.fark:,.2f} TL"
            baslik_renk = '#FF9800'
            liste = self.FAZLA_KONTROL
        else:
            baslik_text = f"KASA EKSIK CIKTI: {self.fark:,.2f} TL"
            baslik_renk = '#F44336'
            liste = self.EKSIK_KONTROL

        baslik_frame = tk.Frame(self.pencere, bg=baslik_renk, height=60)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text=baslik_text,
            font=("Arial", 14, "bold"),
            bg=baslik_renk,
            fg='white'
        ).pack(expand=True)

        # Açıklama
        aciklama_frame = tk.Frame(self.pencere, bg='#FFECB3' if self.fark > 0 else '#FFCDD2', padx=15, pady=10)
        aciklama_frame.pack(fill="x")

        tk.Label(
            aciklama_frame,
            text="Asagidaki maddeleri tek tek kontrol edin ve isaretleyin.\n"
                 "Tum maddeler kontrol edilmeden pencere kapatilamaz.",
            font=("Arial", 10),
            bg='#FFECB3' if self.fark > 0 else '#FFCDD2',
            fg='#E65100' if self.fark > 0 else '#C62828',
            justify='left'
        ).pack(anchor='w')

        # Scroll edilebilir alan
        main_frame = tk.Frame(self.pencere, bg='#FAFAFA')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        canvas = tk.Canvas(main_frame, bg='#FAFAFA', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg='#FAFAFA')

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Kontrol maddeleri
        for kod, metin in liste:
            row = tk.Frame(scrollable, bg='#FAFAFA')
            row.pack(fill="x", pady=3, padx=5)

            var = tk.BooleanVar(value=False)
            self.kontrol_vars[kod] = var

            cb = tk.Checkbutton(
                row,
                text=f"{kod}) {metin}",
                variable=var,
                font=("Arial", 10),
                bg='#FAFAFA',
                activebackground='#FAFAFA',
                anchor='w',
                wraplength=700,
                justify='left',
                command=self.kontrol_durumu_guncelle
            )
            cb.pack(fill="x", anchor='w')

        # Alt butonlar
        buton_frame = tk.Frame(self.pencere, bg='#FAFAFA', pady=15)
        buton_frame.pack(fill="x")

        # Tümünü işaretle butonu
        tk.Button(
            buton_frame,
            text="Tumunu Isaretle",
            font=("Arial", 10),
            bg='#2196F3',
            fg='white',
            width=15,
            cursor='hand2',
            command=self.tumunu_isaretle
        ).pack(side="left", padx=20)

        # Durum etiketi
        self.durum_label = tk.Label(
            buton_frame,
            text="0 / {} madde kontrol edildi".format(len(liste)),
            font=("Arial", 10),
            bg='#FAFAFA',
            fg='#666'
        )
        self.durum_label.pack(side="left", expand=True)

        # Tamam butonu
        self.tamam_btn = tk.Button(
            buton_frame,
            text="Tamam",
            font=("Arial", 11, "bold"),
            bg='#9E9E9E',
            fg='white',
            width=15,
            cursor='hand2',
            state='disabled',
            command=self.kapat
        )
        self.tamam_btn.pack(side="right", padx=20)

        # Pencere kapatma engeli
        self.pencere.protocol("WM_DELETE_WINDOW", self.kapatma_kontrolu)

    def kontrol_durumu_guncelle(self):
        """Kontrol durumunu güncelle"""
        toplam = len(self.kontrol_vars)
        isaretli = sum(1 for v in self.kontrol_vars.values() if v.get())

        self.durum_label.config(text=f"{isaretli} / {toplam} madde kontrol edildi")

        if isaretli == toplam:
            self.tamam_btn.config(state='normal', bg='#4CAF50')
        else:
            self.tamam_btn.config(state='disabled', bg='#9E9E9E')

    def tumunu_isaretle(self):
        """Tüm maddeleri işaretle"""
        for var in self.kontrol_vars.values():
            var.set(True)
        self.kontrol_durumu_guncelle()

    def kapatma_kontrolu(self):
        """Pencere kapatma kontrolü"""
        toplam = len(self.kontrol_vars)
        isaretli = sum(1 for v in self.kontrol_vars.values() if v.get())

        if isaretli < toplam:
            messagebox.showwarning(
                "Kontrol Tamamlanmadi",
                f"Henuz {toplam - isaretli} madde kontrol edilmedi!\n\n"
                "Tum maddeleri kontrol etmeden pencereyi kapatamazsiniz."
            )
        else:
            self.kapat()

    def kapat(self):
        """Pencereyi kapat"""
        if self.pencere and self.pencere.winfo_exists():
            self.pencere.destroy()
