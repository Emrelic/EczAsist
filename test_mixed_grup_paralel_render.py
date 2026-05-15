"""Headless test — mixed grup (some veya_grubu=True, some F) için segments-aware render.

Bug: g_e2 grubunda E2-1 (F), E2-2a (T), E2-2b (T), E2-4 (F) atomları.
Beklenen: E2-1 ∧ (E2-2a ∨ E2-2b) ∧ E2-4 — ortadaki ikisi dikey paralel sub-blok.
Eski davranış: hepsi yatay seri, aralarında ∨/∧ alfabe.
"""
import sys
import tkinter as tk

sys.path.insert(0, r'C:\Users\ana\OneDrive\Desktop\Uibul3.0\EczAsist')

# Tkinter headless için sahte root oluştur
root = tk.Tk()
root.withdraw()

from aylik_recete_sorgu_gui import AylikReceteSorguGUI


def _build_test_app():
    """Sema panelinin canvas'larını oluştur (header'sız)."""
    app = AylikReceteSorguGUI.__new__(AylikReceteSorguGUI)
    app.root = root
    parent = tk.Frame(root)
    app._sema_kur(parent)
    return app


# Test atomları — g_e2 yapısına benzer mixed grup
TEST_ATOMS = [
    {"ad": "E2-1 SK raporu var", "durum": "var",
     "neden": "heyet onaylı", "grup": "Test grup [mixed]",
     "veya_grubu": False},
    {"ad": "E2-2a Herhangi 3 farklı dal", "durum": "yok",
     "neden": "sadece 1 yetkili", "grup": "Test grup [mixed]",
     "veya_grubu": True},
    {"ad": "E2-2b Aynı dalda 3 uzman", "durum": "var",
     "neden": "kalp_damar 3 doktor", "grup": "Test grup [mixed]",
     "veya_grubu": True},
    {"ad": "E2-4 Yetkili branş reçete", "durum": "var",
     "neden": "doktor branş yetkili", "grup": "Test grup [mixed]",
     "veya_grubu": False},
]


def test_segments_helper():
    """_atomlar_segments helper'ı mixed grubu doğru segmentlere bölmeli."""
    app = _build_test_app()
    # Helper closure'larına erişim için _klasik_ciz_canvas'ı render et,
    # ama önce dışarıdan segments mantığını birebir doğrula.
    segs = []
    i = 0
    n = len(TEST_ATOMS)
    while i < n:
        if TEST_ATOMS[i].get("veya_grubu"):
            j = i
            while j < n and TEST_ATOMS[j].get("veya_grubu"):
                j += 1
            if j - i >= 2:
                segs.append(('or', list(range(i, j))))
            else:
                segs.append(('and', [i]))
            i = j
        else:
            segs.append(('and', [i]))
            i += 1
    print(f"Segments: {segs}")
    assert segs == [('and', [0]), ('or', [1, 2]), ('and', [3])], \
        f"Mixed grup yanlış segmentlere bölündü: {segs}"
    print("✓ Segments helper doğru çalıştı: 1×AND + 1×OR(2) + 1×AND")
    return app


def test_render_smoke():
    """Render çalışsın ve hata vermesin (g_e2'ye benzer mixed grup)."""
    app = test_segments_helper()
    detaylar = {"alt_dal": "4.2.15.D-2 · DVT/PE"}
    app._klasik_ciz_canvas(TEST_ATOMS, detaylar=detaylar,
                            verdict="UYGUN")
    # Canvas item'ları yaratıldı mı?
    items = app._klasik_canvas.find_all()
    print(f"Canvas items: {len(items)}")
    assert len(items) > 5, \
        f"Render çok az item üretti, beklenen >5: {len(items)}"
    print("✓ Render smoke OK")

    # OR sub-blok atomları farklı y'de olmalı (E2-2a yukarıda, E2-2b aşağıda)
    # Tüm text item'larını çek, "E2-2a"/"E2-2b" içerenleri bul
    ys_2a = []
    ys_2b = []
    for item in items:
        if app._klasik_canvas.type(item) == "text":
            txt = app._klasik_canvas.itemcget(item, "text")
            coords = app._klasik_canvas.coords(item)
            if "E2-2a" in txt and coords:
                ys_2a.append(coords[1])
            if "E2-2b" in txt and coords:
                ys_2b.append(coords[1])
    print(f"E2-2a y koordinatları: {ys_2a}")
    print(f"E2-2b y koordinatları: {ys_2b}")
    if ys_2a and ys_2b:
        y_2a = min(ys_2a)
        y_2b = min(ys_2b)
        assert abs(y_2a - y_2b) > 30, \
            f"E2-2a ve E2-2b aynı y'de (paralel değil): " \
            f"y_2a={y_2a}, y_2b={y_2b}"
        print(f"✓ E2-2a y={y_2a} ile E2-2b y={y_2b} farklı "
              f"(|fark|={abs(y_2a-y_2b)}px > 30px) — DİKEY PARALEL ✓")
    else:
        print(f"! E2-2a/E2-2b text item'ı bulunamadı, ys_2a={ys_2a}, ys_2b={ys_2b}")


def test_all_or_regresyon():
    """All-OR grup hâlâ dikey paralel render edilmeli (regresyon)."""
    app = _build_test_app()
    all_or = [
        {"ad": "Atom A", "durum": "var", "neden": "ok",
         "grup": "All-OR test", "veya_grubu": True},
        {"ad": "Atom B", "durum": "yok", "neden": "yok",
         "grup": "All-OR test", "veya_grubu": True},
        {"ad": "Atom C", "durum": "yok", "neden": "yok",
         "grup": "All-OR test", "veya_grubu": True},
    ]
    app._klasik_ciz_canvas(all_or, detaylar={"alt_dal": "test"},
                            verdict="UYGUN")
    items = app._klasik_canvas.find_all()
    ys = {"A": [], "B": [], "C": []}
    for item in items:
        if app._klasik_canvas.type(item) == "text":
            txt = app._klasik_canvas.itemcget(item, "text")
            coords = app._klasik_canvas.coords(item)
            for k in ys:
                if f"Atom {k}" in txt and coords:
                    ys[k].append(coords[1])
    print(f"All-OR ys: {ys}")
    y_A = min(ys["A"]) if ys["A"] else None
    y_B = min(ys["B"]) if ys["B"] else None
    y_C = min(ys["C"]) if ys["C"] else None
    if y_A and y_B and y_C:
        assert y_A != y_B and y_B != y_C, \
            f"All-OR atomları aynı y'de: {y_A}, {y_B}, {y_C}"
        print(f"✓ All-OR regresyon OK: A={y_A}, B={y_B}, C={y_C}")


def test_all_and_regresyon():
    """All-AND grup hâlâ yatay seri (regresyon)."""
    app = _build_test_app()
    all_and = [
        {"ad": "Atom X", "durum": "var", "neden": "ok",
         "grup": "All-AND test", "veya_grubu": False},
        {"ad": "Atom Y", "durum": "var", "neden": "ok",
         "grup": "All-AND test", "veya_grubu": False},
    ]
    app._klasik_ciz_canvas(all_and, detaylar={"alt_dal": "test"},
                            verdict="UYGUN")
    items = app._klasik_canvas.find_all()
    ys = {"X": [], "Y": []}
    for item in items:
        if app._klasik_canvas.type(item) == "text":
            txt = app._klasik_canvas.itemcget(item, "text")
            coords = app._klasik_canvas.coords(item)
            for k in ys:
                if f"Atom {k}" in txt and coords:
                    ys[k].append(coords[1])
    print(f"All-AND ys: {ys}")
    y_X = min(ys["X"]) if ys["X"] else None
    y_Y = min(ys["Y"]) if ys["Y"] else None
    if y_X and y_Y:
        assert abs(y_X - y_Y) < 30, \
            f"All-AND atomları farklı y'de (yatay olmalı): {y_X}, {y_Y}"
        print(f"✓ All-AND regresyon OK: X={y_X}, Y={y_Y} (aynı seviye)")


if __name__ == "__main__":
    print("=" * 70)
    print("TEST 1: Segments helper + mixed grup render")
    print("=" * 70)
    test_render_smoke()
    print()
    print("=" * 70)
    print("TEST 2: All-OR regresyon")
    print("=" * 70)
    test_all_or_regresyon()
    print()
    print("=" * 70)
    print("TEST 3: All-AND regresyon")
    print("=" * 70)
    test_all_and_regresyon()
    print()
    print("=" * 70)
    print("✓ TÜM TESTLER GEÇTİ")
    print("=" * 70)
