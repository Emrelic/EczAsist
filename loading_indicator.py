"""
Loading Indicator - Tüm Modüller İçin Ortak Yükleme Göstergesi
Sorgu/işlem sürerken kullanıcıya görsel geri bildirim sağlar
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
import math


class LoadingIndicator:
    """
    Kullanım:

    # Yöntem 1: Context Manager (önerilen)
    with LoadingIndicator(parent, "Veriler yükleniyor..."):
        uzun_islem()

    # Yöntem 2: Manuel kontrol
    loading = LoadingIndicator(parent, "İşlem yapılıyor...")
    loading.show()
    try:
        uzun_islem()
    finally:
        loading.hide()

    # Yöntem 3: Thread ile (GUI donmasın)
    def islem_yap():
        # uzun işlem
        pass

    LoadingIndicator.run_with_loading(parent, "Yükleniyor...", islem_yap, callback=tamamlandi)
    """

    def __init__(self, parent, mesaj="Lütfen bekleyin...", stil="spinner"):
        """
        Args:
            parent: Ana pencere (tk.Tk, tk.Toplevel veya tk.Frame)
            mesaj: Gösterilecek mesaj
            stil: "spinner", "progress", "dots" veya "pulse"
        """
        self.parent = parent
        self.mesaj = mesaj
        self.stil = stil
        self.popup = None
        self.animasyon_aktif = False
        self._animasyon_id = None
        self._dot_count = 0
        self._angle = 0
        self._pulse_scale = 1.0
        self._pulse_growing = True

    def show(self):
        """Loading göstergesini göster"""
        if self.popup is not None:
            return

        # Overlay penceresi oluştur
        self.popup = tk.Toplevel(self.parent)
        self.popup.overrideredirect(True)  # Başlık çubuğu yok
        self.popup.attributes('-topmost', True)
        self.popup.configure(bg='#2C3E50')

        # Yarı saydam efekti için
        self.popup.attributes('-alpha', 0.95)

        # Ana frame
        main_frame = tk.Frame(self.popup, bg='#2C3E50', padx=30, pady=25)
        main_frame.pack(fill='both', expand=True)

        # Stil'e göre içerik oluştur
        if self.stil == "spinner":
            self._create_spinner(main_frame)
        elif self.stil == "progress":
            self._create_progress(main_frame)
        elif self.stil == "dots":
            self._create_dots(main_frame)
        elif self.stil == "pulse":
            self._create_pulse(main_frame)
        else:
            self._create_spinner(main_frame)

        # Mesaj
        self.mesaj_label = tk.Label(
            main_frame,
            text=self.mesaj,
            font=('Segoe UI', 11),
            bg='#2C3E50',
            fg='white'
        )
        self.mesaj_label.pack(pady=(15, 0))

        # Pencereyi ortala
        self.popup.update_idletasks()
        self._center_popup()

        # Animasyonu başlat
        self.animasyon_aktif = True
        self._animate()

        # Parent'ı devre dışı bırak
        self._disable_parent()

    def _create_spinner(self, parent):
        """Dönen spinner oluştur"""
        self.canvas = tk.Canvas(
            parent,
            width=60,
            height=60,
            bg='#2C3E50',
            highlightthickness=0
        )
        self.canvas.pack()

        # Spinner çizgileri
        self.spinner_lines = []
        center_x, center_y = 30, 30
        radius = 20

        for i in range(12):
            angle = i * 30
            rad = math.radians(angle)
            x1 = center_x + (radius - 8) * math.cos(rad)
            y1 = center_y + (radius - 8) * math.sin(rad)
            x2 = center_x + radius * math.cos(rad)
            y2 = center_y + radius * math.sin(rad)

            line = self.canvas.create_line(
                x1, y1, x2, y2,
                fill='#7F8C8D',
                width=3,
                capstyle='round'
            )
            self.spinner_lines.append(line)

    def _create_progress(self, parent):
        """İndeterminate progress bar oluştur"""
        style = ttk.Style()
        style.configure(
            "Loading.Horizontal.TProgressbar",
            troughcolor='#34495E',
            background='#3498DB',
            thickness=8
        )

        self.progress = ttk.Progressbar(
            parent,
            style="Loading.Horizontal.TProgressbar",
            mode='indeterminate',
            length=200
        )
        self.progress.pack(pady=10)
        self.progress.start(15)

    def _create_dots(self, parent):
        """Nokta animasyonu oluştur"""
        self.dots_frame = tk.Frame(parent, bg='#2C3E50')
        self.dots_frame.pack()

        self.dots = []
        for i in range(3):
            dot = tk.Label(
                self.dots_frame,
                text="●",
                font=('Arial', 16),
                bg='#2C3E50',
                fg='#3498DB'
            )
            dot.pack(side='left', padx=5)
            self.dots.append(dot)

    def _create_pulse(self, parent):
        """Nabız efektli daire oluştur"""
        self.canvas = tk.Canvas(
            parent,
            width=60,
            height=60,
            bg='#2C3E50',
            highlightthickness=0
        )
        self.canvas.pack()

        self.pulse_circle = self.canvas.create_oval(
            15, 15, 45, 45,
            fill='#3498DB',
            outline=''
        )

    def _animate(self):
        """Animasyon döngüsü"""
        if not self.animasyon_aktif or self.popup is None:
            return

        try:
            if self.stil == "spinner":
                self._animate_spinner()
            elif self.stil == "dots":
                self._animate_dots()
            elif self.stil == "pulse":
                self._animate_pulse()
            # progress bar kendi animasyonunu yapıyor

            self._animasyon_id = self.popup.after(80, self._animate)
        except tk.TclError:
            # Pencere kapandıysa
            pass

    def _animate_spinner(self):
        """Spinner animasyonu"""
        self._angle = (self._angle + 1) % 12

        colors = ['#ECF0F1', '#BDC3C7', '#95A5A6', '#7F8C8D',
                  '#6C7A7D', '#5D6D6E', '#4E5D5E', '#3F4D4E',
                  '#3F4D4E', '#3F4D4E', '#3F4D4E', '#3F4D4E']

        for i, line in enumerate(self.spinner_lines):
            color_idx = (i - self._angle) % 12
            self.canvas.itemconfig(line, fill=colors[color_idx])

    def _animate_dots(self):
        """Nokta animasyonu"""
        self._dot_count = (self._dot_count + 1) % 4

        colors = ['#7F8C8D', '#7F8C8D', '#7F8C8D']
        for i in range(self._dot_count):
            colors[i] = '#3498DB'

        for i, dot in enumerate(self.dots):
            dot.config(fg=colors[i] if i < len(colors) else '#7F8C8D')

    def _animate_pulse(self):
        """Nabız animasyonu"""
        if self._pulse_growing:
            self._pulse_scale += 0.05
            if self._pulse_scale >= 1.3:
                self._pulse_growing = False
        else:
            self._pulse_scale -= 0.05
            if self._pulse_scale <= 0.8:
                self._pulse_growing = True

        center = 30
        size = 15 * self._pulse_scale
        self.canvas.coords(
            self.pulse_circle,
            center - size, center - size,
            center + size, center + size
        )

    def _center_popup(self):
        """Popup'ı parent'ın ortasına konumlandır"""
        try:
            # Parent'ın konumunu ve boyutunu al
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_w = self.parent.winfo_width()
            parent_h = self.parent.winfo_height()

            # Popup boyutları
            popup_w = self.popup.winfo_width()
            popup_h = self.popup.winfo_height()

            # Merkez konumu hesapla
            x = parent_x + (parent_w - popup_w) // 2
            y = parent_y + (parent_h - popup_h) // 2

            self.popup.geometry(f"+{x}+{y}")
        except:
            pass

    def _disable_parent(self):
        """Parent pencereyi devre dışı bırak"""
        try:
            # Tüm butonları ve entry'leri devre dışı bırak
            self._disabled_widgets = []
            self._grab_set()
        except:
            pass

    def _grab_set(self):
        """Focus'u yakala"""
        try:
            self.popup.grab_set()
            self.popup.focus_set()
        except:
            pass

    def _enable_parent(self):
        """Parent pencereyi tekrar aktif et"""
        try:
            self.popup.grab_release()
        except:
            pass

    def update_message(self, yeni_mesaj):
        """Mesajı güncelle"""
        if self.popup and hasattr(self, 'mesaj_label'):
            try:
                self.mesaj_label.config(text=yeni_mesaj)
                self.popup.update_idletasks()
            except:
                pass

    def hide(self):
        """Loading göstergesini gizle"""
        self.animasyon_aktif = False

        if self._animasyon_id:
            try:
                self.popup.after_cancel(self._animasyon_id)
            except:
                pass
            self._animasyon_id = None

        if self.popup:
            try:
                if self.stil == "progress" and hasattr(self, 'progress'):
                    self.progress.stop()
                self._enable_parent()
                self.popup.destroy()
            except:
                pass
            self.popup = None

    def __enter__(self):
        """Context manager giriş"""
        self.show()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager çıkış"""
        self.hide()
        return False

    @staticmethod
    def run_with_loading(parent, mesaj, func, callback=None, stil="spinner", *args, **kwargs):
        """
        Bir fonksiyonu loading göstergesi ile çalıştır (thread ile).
        GUI donmaz.

        Args:
            parent: Ana pencere
            mesaj: Loading mesajı
            func: Çalıştırılacak fonksiyon
            callback: İşlem bitince çağrılacak fonksiyon (sonuç ile)
            stil: Loading stili
            *args, **kwargs: func'a geçirilecek argümanlar

        Örnek:
            def veri_cek():
                time.sleep(3)
                return {"data": [1,2,3]}

            def tamamlandi(sonuc):
                print("Sonuç:", sonuc)

            LoadingIndicator.run_with_loading(
                root, "Veriler çekiliyor...",
                veri_cek, callback=tamamlandi
            )
        """
        loading = LoadingIndicator(parent, mesaj, stil)
        loading.show()

        result = [None]
        error = [None]

        def worker():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                error[0] = e
            finally:
                # GUI thread'inde loading'i kapat ve callback'i çağır
                parent.after(0, lambda: _finish())

        def _finish():
            loading.hide()
            if error[0]:
                raise error[0]
            if callback:
                callback(result[0])

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        return loading


class LoadingButton(tk.Button):
    """
    Tıklandığında otomatik loading gösteren buton.

    Kullanım:
        def uzun_islem():
            time.sleep(2)
            return "Tamam"

        btn = LoadingButton(
            parent,
            text="Verileri Çek",
            command=uzun_islem,
            loading_text="Çekiliyor..."
        )
        btn.pack()
    """

    def __init__(self, parent, text="", command=None, loading_text="İşleniyor...",
                 callback=None, stil="spinner", **kwargs):
        self._original_text = text
        self._loading_text = loading_text
        self._user_command = command
        self._callback = callback
        self._loading_stil = stil
        self._is_loading = False

        super().__init__(parent, text=text, command=self._on_click, **kwargs)
        self._parent_window = parent.winfo_toplevel()

    def _on_click(self):
        """Butona tıklandığında"""
        if self._is_loading or not self._user_command:
            return

        self._is_loading = True
        self.config(state='disabled', text=self._loading_text)

        def finish(result=None):
            self._is_loading = False
            self.config(state='normal', text=self._original_text)
            if self._callback:
                self._callback(result)

        LoadingIndicator.run_with_loading(
            self._parent_window,
            self._loading_text,
            self._user_command,
            callback=finish,
            stil=self._loading_stil
        )


# Kısayol fonksiyonları
def show_loading(parent, mesaj="Lütfen bekleyin...", stil="spinner"):
    """Basit loading göster"""
    loading = LoadingIndicator(parent, mesaj, stil)
    loading.show()
    return loading


def loading_decorator(mesaj="İşlem yapılıyor...", stil="spinner"):
    """
    Fonksiyonu loading göstergesi ile saran decorator.

    @loading_decorator("Veriler yükleniyor...")
    def veri_yukle(self):
        # uzun işlem
        pass
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            # self.root veya self.parent'ı bul
            parent = getattr(self, 'root', None) or getattr(self, 'parent', None)
            if parent is None:
                return func(self, *args, **kwargs)

            with LoadingIndicator(parent, mesaj, stil):
                return func(self, *args, **kwargs)
        return wrapper
    return decorator


# Test
if __name__ == "__main__":
    import time

    root = tk.Tk()
    root.title("Loading Indicator Test")
    root.geometry("400x300")

    def test_spinner():
        def uzun_islem():
            time.sleep(3)
            return "Spinner tamamlandı!"

        def sonuc(r):
            print(r)

        LoadingIndicator.run_with_loading(root, "Spinner test...", uzun_islem, sonuc, "spinner")

    def test_progress():
        def uzun_islem():
            time.sleep(3)
            return "Progress tamamlandı!"

        LoadingIndicator.run_with_loading(root, "Progress test...", uzun_islem, print, "progress")

    def test_dots():
        with LoadingIndicator(root, "Dots test...", "dots"):
            time.sleep(3)

    def test_pulse():
        loading = LoadingIndicator(root, "Pulse test...", "pulse")
        loading.show()
        root.after(3000, loading.hide)

    tk.Button(root, text="Spinner Test", command=test_spinner, width=20).pack(pady=10)
    tk.Button(root, text="Progress Test", command=test_progress, width=20).pack(pady=10)
    tk.Button(root, text="Dots Test", command=lambda: threading.Thread(target=test_dots).start(), width=20).pack(pady=10)
    tk.Button(root, text="Pulse Test", command=test_pulse, width=20).pack(pady=10)

    # LoadingButton örneği
    def ornek_islem():
        time.sleep(2)
        return "Bitti!"

    LoadingButton(
        root,
        text="Loading Button Test",
        command=ornek_islem,
        loading_text="Yükleniyor...",
        callback=lambda r: print(f"Sonuç: {r}"),
        width=20
    ).pack(pady=10)

    root.mainloop()
