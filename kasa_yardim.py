"""
Botanik Bot - Kasa Takip Yardım Modülü
Kullanım kılavuzu ve yardım sistemi
"""

import tkinter as tk
from tkinter import ttk
import webbrowser


class KasaYardimPenceresi:
    """Kullanım kılavuzu ve yardım penceresi"""

    def __init__(self, parent):
        self.parent = parent
        self.pencere = None

    def goster(self):
        """Yardım penceresini göster"""
        self.pencere = tk.Toplevel(self.parent)
        self.pencere.title("Kullanım Kılavuzu")
        self.pencere.geometry("800x650")
        self.pencere.configure(bg='#f5f5f5')

        # Pencereyi ortala
        self.pencere.update_idletasks()
        x = (self.pencere.winfo_screenwidth() - 800) // 2
        y = (self.pencere.winfo_screenheight() - 650) // 2
        self.pencere.geometry(f"800x650+{x}+{y}")

        # Başlık
        baslik_frame = tk.Frame(self.pencere, bg='#2c3e50', height=60)
        baslik_frame.pack(fill='x')
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text="Kasa Takip Sistemi - Kullanım Kılavuzu",
            font=('Arial', 16, 'bold'),
            bg='#2c3e50',
            fg='white'
        ).pack(expand=True)

        # Ana içerik
        main_frame = tk.Frame(self.pencere, bg='#f5f5f5')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Sol menü
        menu_frame = tk.Frame(main_frame, bg='white', width=200)
        menu_frame.pack(side='left', fill='y', padx=(0, 10))
        menu_frame.pack_propagate(False)

        tk.Label(
            menu_frame,
            text="Konular",
            font=('Arial', 12, 'bold'),
            bg='white',
            pady=10
        ).pack(fill='x')

        # Menü butonları
        konular = [
            ("Genel Bakış", self.genel_bakis),
            ("Kasa Açılış", self.kasa_acilis),
            ("Gün Sonu Sayım", self.gun_sonu_sayim),
            ("POS ve IBAN", self.pos_iban),
            ("Botanik Entegrasyonu", self.botanik_entegrasyon),
            ("Düzeltmeler", self.duzeltmeler),
            ("Raporlar", self.raporlar),
            ("WhatsApp Gönderimi", self.whatsapp),
            ("E-posta Gönderimi", self.email),
            ("Yazıcı Ayarları", self.yazici),
            ("Geçmiş Kayıtlar", self.gecmis),
            ("Kısayollar", self.kisayollar),
        ]

        self.menu_butonlar = []
        for konu, fonksiyon in konular:
            btn = tk.Button(
                menu_frame,
                text=konu,
                font=('Arial', 10),
                bg='white',
                fg='#333',
                bd=0,
                anchor='w',
                padx=15,
                pady=8,
                cursor='hand2',
                command=fonksiyon,
                activebackground='#e8f4fc'
            )
            btn.pack(fill='x')
            self.menu_butonlar.append(btn)

        # Sağ içerik alanı
        self.icerik_frame = tk.Frame(main_frame, bg='white')
        self.icerik_frame.pack(side='right', fill='both', expand=True)

        # Scrollable içerik
        self.canvas = tk.Canvas(self.icerik_frame, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.icerik_frame, orient='vertical', command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg='white')

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor='nw')
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Mouse wheel scroll
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # İlk sayfa
        self.genel_bakis()

    def icerik_temizle(self):
        """İçerik alanını temizle"""
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

    def baslik_ekle(self, metin, alt_baslik=False):
        """Başlık ekle"""
        font = ('Arial', 12, 'bold') if alt_baslik else ('Arial', 16, 'bold')
        renk = '#34495e' if alt_baslik else '#2c3e50'
        pady = (15, 5) if alt_baslik else (20, 10)

        tk.Label(
            self.scroll_frame,
            text=metin,
            font=font,
            bg='white',
            fg=renk,
            anchor='w'
        ).pack(fill='x', padx=20, pady=pady)

    def paragraf_ekle(self, metin):
        """Paragraf ekle"""
        tk.Label(
            self.scroll_frame,
            text=metin,
            font=('Arial', 10),
            bg='white',
            fg='#333',
            anchor='w',
            justify='left',
            wraplength=550
        ).pack(fill='x', padx=25, pady=5)

    def madde_ekle(self, metin):
        """Madde işaretli liste ekle"""
        tk.Label(
            self.scroll_frame,
            text=f"  •  {metin}",
            font=('Arial', 10),
            bg='white',
            fg='#444',
            anchor='w',
            justify='left',
            wraplength=530
        ).pack(fill='x', padx=25, pady=2)

    def bilgi_kutusu(self, metin, tip="info"):
        """Bilgi kutusu ekle (info, warning, success)"""
        renkler = {
            "info": ("#e3f2fd", "#1565c0", "ℹ️"),
            "warning": ("#fff3e0", "#e65100", "⚠️"),
            "success": ("#e8f5e9", "#2e7d32", "✓"),
            "tip": ("#f3e5f5", "#7b1fa2", "💡")
        }
        bg, fg, ikon = renkler.get(tip, renkler["info"])

        frame = tk.Frame(self.scroll_frame, bg=bg, padx=15, pady=10)
        frame.pack(fill='x', padx=20, pady=10)

        tk.Label(
            frame,
            text=f"{ikon} {metin}",
            font=('Arial', 10),
            bg=bg,
            fg=fg,
            anchor='w',
            justify='left',
            wraplength=520
        ).pack(fill='x')

    def kod_kutusu(self, metin):
        """Kod/komut kutusu ekle"""
        frame = tk.Frame(self.scroll_frame, bg='#f5f5f5', padx=15, pady=10)
        frame.pack(fill='x', padx=20, pady=5)

        tk.Label(
            frame,
            text=metin,
            font=('Consolas', 10),
            bg='#f5f5f5',
            fg='#333',
            anchor='w',
            justify='left'
        ).pack(fill='x')

    # ==================== KONU SAYFALARI ====================

    def genel_bakis(self):
        """Genel bakış sayfası"""
        self.icerik_temizle()

        self.baslik_ekle("Genel Bakış")

        self.paragraf_ekle(
            "Kasa Takip Sistemi, günlük kasa kapatma işlemlerinizi kolaylaştırmak için "
            "tasarlanmış kapsamlı bir araçtır. Botanik EOS sistemiyle entegre çalışarak "
            "otomatik veri çekme, karşılaştırma ve raporlama yapar."
        )

        self.baslik_ekle("Temel Özellikler", alt_baslik=True)
        self.madde_ekle("Başlangıç kasası ve gün sonu sayımı")
        self.madde_ekle("POS ve IBAN toplamları takibi")
        self.madde_ekle("Botanik EOS'tan otomatik veri çekme")
        self.madde_ekle("Sayım - Botanik karşılaştırması ve fark analizi")
        self.madde_ekle("Masraf, silinen reçete ve alınan para düzeltmeleri")
        self.madde_ekle("WhatsApp ve E-posta ile rapor gönderimi")
        self.madde_ekle("Termal yazıcıya yazdırma")
        self.madde_ekle("Geçmiş kayıtları görüntüleme ve analiz")

        self.baslik_ekle("Ekran Düzeni", alt_baslik=True)
        self.paragraf_ekle("Program 4 ana bölümden oluşur:")
        self.madde_ekle("SOL ÜST: Başlangıç kasası ve küpür detayları")
        self.madde_ekle("SOL ALT: Gün sonu nakit sayımı")
        self.madde_ekle("ORTA: POS ve IBAN toplamları")
        self.madde_ekle("SAĞ: Düzeltmeler, Botanik verileri ve özet")

        self.bilgi_kutusu("Programı kullanmadan önce Botanik EOS'ta 'Kasa Kapatma' penceresini açık tutun.", "tip")

    def kasa_acilis(self):
        """Kasa açılış bölümü"""
        self.icerik_temizle()

        self.baslik_ekle("Kasa Açılış İşlemleri")

        self.paragraf_ekle(
            "Her günün başında kasadaki para miktarını kaydetmeniz gerekir. "
            "Bu genellikle bir önceki günün 'Ertesi Gün Kasası' değeridir."
        )

        self.baslik_ekle("Başlangıç Kasası Girişi", alt_baslik=True)
        self.madde_ekle("Sol üst köşedeki 'Başlangıç Kasası' bölümüne gidin")
        self.madde_ekle("Her küpür için adet sayısını girin")
        self.madde_ekle("Toplam otomatik olarak hesaplanır")

        self.bilgi_kutusu(
            "Eğer fiziksel sayım Botanik'teki başlangıç kasasından farklıysa, "
            "'Manuel Başlangıç' butonunu kullanarak farkı açıklayabilirsiniz.",
            "warning"
        )

        self.baslik_ekle("Manuel Başlangıç Kasası", alt_baslik=True)
        self.paragraf_ekle(
            "Bazı durumlarda (kasadan para alınması, ekleme yapılması vb.) "
            "başlangıç kasası Botanik'teki değerden farklı olabilir."
        )
        self.madde_ekle("'Manuel Başlangıç' butonuna tıklayın")
        self.madde_ekle("Gerçek başlangıç tutarını girin")
        self.madde_ekle("Farkın nedenini açıklama olarak yazın")
        self.madde_ekle("Bu açıklama raporlarda gösterilir")

    def gun_sonu_sayim(self):
        """Gün sonu sayım bölümü"""
        self.icerik_temizle()

        self.baslik_ekle("Gün Sonu Nakit Sayımı")

        self.paragraf_ekle(
            "Gün sonunda kasadaki tüm nakit parayı küpür küpür saymanız gerekir. "
            "Bu sayım Botanik'teki nakit toplamıyla karşılaştırılır."
        )

        self.baslik_ekle("Sayım Nasıl Yapılır?", alt_baslik=True)
        self.madde_ekle("Sol alt köşedeki 'Gün Sonu Sayım' bölümüne gidin")
        self.madde_ekle("Her küpür için adet sayısını girin (200, 100, 50, 20, 10, 5, 1 TL ve kuruşlar)")
        self.madde_ekle("Toplam nakit otomatik hesaplanır")
        self.madde_ekle("Botanik değeriyle fark varsa uyarı gösterilir")

        self.bilgi_kutusu(
            "Sayım sırasında müşteri gelirse 'Alışveriş' bölümünden işlemi kaydedin. "
            "Bu tutar sayımdan düşülür.",
            "tip"
        )

        self.baslik_ekle("Sayım Sırası Alışveriş", alt_baslik=True)
        self.paragraf_ekle(
            "Sayım yaparken müşteri gelip alışveriş yaparsa, bu tutarı 'Alışveriş' "
            "bölümüne girin. Program bu tutarı sayımdan düşerek doğru karşılaştırma yapar."
        )

    def pos_iban(self):
        """POS ve IBAN bölümü"""
        self.icerik_temizle()

        self.baslik_ekle("POS ve IBAN Toplamları")

        self.baslik_ekle("POS Girişi", alt_baslik=True)
        self.paragraf_ekle(
            "Günlük POS cihazlarından yapılan tahsilatları girin. "
            "Program 8 adet POS alanı destekler."
        )
        self.madde_ekle("Her POS cihazının günlük toplamını ilgili alana girin")
        self.madde_ekle("Toplam otomatik hesaplanır")
        self.madde_ekle("Botanik POS toplamıyla karşılaştırılır")

        self.baslik_ekle("IBAN Girişi", alt_baslik=True)
        self.paragraf_ekle(
            "Banka havalesi/EFT ile yapılan tahsilatları girin. "
            "4 adet IBAN alanı mevcuttur."
        )

        self.bilgi_kutusu(
            "Botanik'ten 'Botanik'ten Çek' butonuyla POS ve IBAN değerlerini "
            "otomatik olarak çekebilirsiniz.",
            "success"
        )

    def botanik_entegrasyon(self):
        """Botanik entegrasyonu"""
        self.icerik_temizle()

        self.baslik_ekle("Botanik EOS Entegrasyonu")

        self.paragraf_ekle(
            "Program, Botanik EOS 'Kasa Kapatma' penceresinden verileri otomatik olarak "
            "okuyabilir. Bu sayede manuel giriş hatalarını önler ve karşılaştırma yapar."
        )

        self.baslik_ekle("Otomatik Veri Çekme", alt_baslik=True)
        self.madde_ekle("Botanik EOS'u açın ve 'Kasa Kapatma' penceresine gidin")
        self.madde_ekle("Kasa Takip programını açtığınızda veriler otomatik çekilir")
        self.madde_ekle("Manuel olarak 'Botanik'ten Çek' butonuyla da çekebilirsiniz")

        self.baslik_ekle("Çekilen Veriler", alt_baslik=True)
        self.madde_ekle("Başlangıç Kasası")
        self.madde_ekle("Nakit Toplam")
        self.madde_ekle("POS Toplam")
        self.madde_ekle("IBAN Toplam")

        self.baslik_ekle("Fark Analizi", alt_baslik=True)
        self.paragraf_ekle(
            "Program, sizin sayımınız ile Botanik değerlerini karşılaştırır. "
            "Fark varsa kırmızı renkte gösterilir."
        )

        self.bilgi_kutusu(
            "Başlangıç kasası tutarsızsa program uyarı verir. "
            "Bu durumda 'Manuel Başlangıç' özelliğini kullanın.",
            "warning"
        )

    def duzeltmeler(self):
        """Düzeltmeler bölümü"""
        self.icerik_temizle()

        self.baslik_ekle("Düzeltmeler")

        self.paragraf_ekle(
            "Gün içinde bazı işlemler nakit toplamını etkiler ama Botanik'e yansımaz. "
            "Bu düzeltmeleri yaparak doğru karşılaştırma sağlarsınız."
        )

        self.baslik_ekle("Masraflar (-)", alt_baslik=True)
        self.paragraf_ekle(
            "Kasadan ödenen ama Botanik'e girilmeyen masraflar. "
            "Örnek: Temizlik malzemesi, kırtasiye, küçük onarımlar..."
        )
        self.madde_ekle("Masraf tutarını girin")
        self.madde_ekle("Bu tutar nakit sayımınıza eklenir (düzeltme için)")

        self.baslik_ekle("Silinen Reçeteler (-)", alt_baslik=True)
        self.paragraf_ekle(
            "Botanik'te silinen ama parası alınmış reçeteler. "
            "Silinen reçetenin tutarı Botanik toplamından düşer."
        )

        self.baslik_ekle("Alınan Paralar (+)", alt_baslik=True)
        self.paragraf_ekle(
            "Gün içinde kasadan alınan paralar. "
            "Örnek: Banka yatırımı, mal ödemesi..."
        )

        self.bilgi_kutusu(
            "Düzeltmeler formülü: Düzeltilmiş Nakit = Sayım + Masraf + Silinen + Alınan",
            "info"
        )

    def raporlar(self):
        """Raporlar bölümü"""
        self.icerik_temizle()

        self.baslik_ekle("Raporlar")

        self.paragraf_ekle(
            "Program çeşitli raporlama seçenekleri sunar. "
            "Üst menüdeki 'Raporlar' butonundan erişebilirsiniz."
        )

        self.baslik_ekle("Rapor Türleri", alt_baslik=True)
        self.madde_ekle("Günlük Kasa Raporu")
        self.madde_ekle("Haftalık Özet")
        self.madde_ekle("Aylık Özet")
        self.madde_ekle("Fark Analizi Raporu")

        self.baslik_ekle("Rapor Ayarları", alt_baslik=True)
        self.paragraf_ekle(
            "'Rapor Ayarları' butonundan hangi bölümlerin rapora dahil edileceğini "
            "seçebilirsiniz. WhatsApp ve yazıcı için ayrı ayarlar yapılabilir."
        )

    def whatsapp(self):
        """WhatsApp gönderimi"""
        self.icerik_temizle()

        self.baslik_ekle("WhatsApp ile Rapor Gönderimi")

        self.paragraf_ekle(
            "Kasa raporunu WhatsApp üzerinden hızlıca gönderebilirsiniz. "
            "Üst menüdeki yeşil 'WhatsApp' butonuna tıklayın."
        )

        self.baslik_ekle("Kullanım", alt_baslik=True)
        self.madde_ekle("Üst menüden 'WhatsApp' butonuna tıklayın")
        self.madde_ekle("Rapor önizlemesini kontrol edin")
        self.madde_ekle("İsterseniz Botanik ekran görüntüsü ekleyin")
        self.madde_ekle("'WhatsApp ile Gönder' butonuna tıklayın")
        self.madde_ekle("Tarayıcıda WhatsApp Web açılır")
        self.madde_ekle("Mesajı gönderin")

        self.baslik_ekle("Botanik Ekran Görüntüsü", alt_baslik=True)
        self.paragraf_ekle(
            "İsterseniz Botanik 'Kasa Kapatma' penceresinin ekran görüntüsünü de "
            "ekleyebilirsiniz. Bu görüntü panoya kopyalanır, WhatsApp'ta Ctrl+V ile yapıştırabilirsiniz."
        )

        self.bilgi_kutusu(
            "WhatsApp numarası ayarlardan değiştirilebilir.",
            "tip"
        )

    def email(self):
        """E-posta gönderimi"""
        self.icerik_temizle()

        self.baslik_ekle("E-posta ile Rapor Gönderimi")

        self.paragraf_ekle(
            "Kasa raporunu e-posta ile gönderebilirsiniz. "
            "HTML formatlı profesyonel bir rapor oluşturulur."
        )

        self.baslik_ekle("İlk Kurulum", alt_baslik=True)
        self.madde_ekle("'E-posta' butonuna tıklayın")
        self.madde_ekle("'Ayarlar' butonuna basın")
        self.madde_ekle("E-posta sağlayıcınızı seçin (Gmail, Outlook vb.)")
        self.madde_ekle("E-posta adresinizi girin")
        self.madde_ekle("Şifrenizi girin (Gmail için Uygulama Şifresi)")
        self.madde_ekle("Alıcı e-posta adreslerini ekleyin")
        self.madde_ekle("'Kaydet' butonuna tıklayın")

        self.baslik_ekle("Gmail Uygulama Şifresi", alt_baslik=True)
        self.paragraf_ekle(
            "Gmail kullanıyorsanız normal şifrenizi kullanamazsınız. "
            "Google güvenlik politikası gereği 'Uygulama Şifresi' oluşturmanız gerekir."
        )
        self.madde_ekle("Google Hesabı > Güvenlik > 2 Adımlı Doğrulama'yı açın")
        self.madde_ekle("Güvenlik > Uygulama Şifreleri bölümüne gidin")
        self.madde_ekle("Yeni bir uygulama şifresi oluşturun")
        self.madde_ekle("16 karakterlik şifreyi kopyalayıp programa yapıştırın")

        self.bilgi_kutusu(
            "E-posta ayarları penceresinde 'Nasıl Yapılır?' butonundan "
            "detaylı Gmail kurulum rehberine ulaşabilirsiniz.",
            "tip"
        )

        self.baslik_ekle("Rapor Gönderme", alt_baslik=True)
        self.madde_ekle("'E-posta' butonuna tıklayın")
        self.madde_ekle("Rapor özetini kontrol edin")
        self.madde_ekle("İsterseniz Botanik ekran görüntüsü ekleyin")
        self.madde_ekle("'E-posta Gönder' butonuna tıklayın")

    def yazici(self):
        """Yazıcı ayarları"""
        self.icerik_temizle()

        self.baslik_ekle("Yazıcı Ayarları")

        self.paragraf_ekle(
            "Kasa raporunu termal yazıcıya yazdırabilirsiniz. "
            "80mm termal yazıcılar desteklenir."
        )

        self.baslik_ekle("Yazdırma", alt_baslik=True)
        self.madde_ekle("'Kaydet' butonuna tıklayın")
        self.madde_ekle("Yazıcı seçim penceresi açılır")
        self.madde_ekle("Yazıcınızı seçin")
        self.madde_ekle("'Yazdır' butonuna tıklayın")

        self.baslik_ekle("Desteklenen Yazıcılar", alt_baslik=True)
        self.madde_ekle("80mm termal yazıcılar")
        self.madde_ekle("ESC/POS protokolü destekleyen yazıcılar")
        self.madde_ekle("Windows'a yüklenmiş tüm yazıcılar")

    def gecmis(self):
        """Geçmiş kayıtlar"""
        self.icerik_temizle()

        self.baslik_ekle("Geçmiş Kayıtlar")

        self.paragraf_ekle(
            "Kaydedilen tüm kasa kapatma raporlarına 'Geçmiş Kayıtlar' butonundan ulaşabilirsiniz."
        )

        self.baslik_ekle("Kayıtları Görüntüleme", alt_baslik=True)
        self.madde_ekle("'Geçmiş Kayıtlar' butonuna tıklayın")
        self.madde_ekle("Tarih listesinden istediğiniz günü seçin")
        self.madde_ekle("Detay görmek için çift tıklayın")

        self.baslik_ekle("Kayıt İçeriği", alt_baslik=True)
        self.madde_ekle("Tarih ve saat bilgisi")
        self.madde_ekle("Başlangıç kasası ve küpür detayları")
        self.madde_ekle("Nakit, POS, IBAN toplamları")
        self.madde_ekle("Botanik verileri ve farklar")
        self.madde_ekle("Düzeltmeler")
        self.madde_ekle("Ayrılan para ve ertesi gün kasası")

    def kisayollar(self):
        """Kısayollar"""
        self.icerik_temizle()

        self.baslik_ekle("İpuçları ve Kısayollar")

        self.baslik_ekle("Hızlı İşlemler", alt_baslik=True)
        self.madde_ekle("Tab tuşu: Alanlar arasında gezinme")
        self.madde_ekle("Enter tuşu: Bir sonraki alana geç")
        self.madde_ekle("Escape tuşu: İşlemi iptal et")

        self.baslik_ekle("Pratik İpuçları", alt_baslik=True)
        self.madde_ekle("Botanik'i önce açın, program otomatik veri çeker")
        self.madde_ekle("Sayıma başlamadan önce başlangıç kasasını kontrol edin")
        self.madde_ekle("Masrafları gün içinde not alın, akşam girin")
        self.madde_ekle("Raporu göndermeden önce önizlemeyi kontrol edin")

        self.bilgi_kutusu(
            "Her gün düzenli olarak 'Kaydet' butonuna basarak raporunuzu saklayın. "
            "Geçmiş kayıtlardan eski raporlara ulaşabilirsiniz.",
            "success"
        )


# Test için
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    KasaYardimPenceresi(root).goster()
    root.mainloop()
