"""Medula penceresinin ANLIK durumunu dump et — Claude'un incelemesi için.

Kullanım:
  python tools/medula_inceleme.py            # sadece dump
  python tools/medula_inceleme.py click <id> # önce ID'ye tıkla, sonra dump
  python tools/medula_inceleme.py row1       # 1. satıra tıkla (DOM scan), sonra dump

Çıktı (UTF-8):
  tools/_inceleme_html.html         (sayfa HTML kaynağı)
  tools/_inceleme_ui_tree.txt       (pywinauto UIA descendants ağacı)
  tools/_inceleme_screenshot.png    (pencere ekran görüntüsü)
  tools/_inceleme_ozet.txt          (özet: url, başlık, ID'ler)
"""
from __future__ import annotations

import sys
import io
from pathlib import Path

# stdout UTF-8 — Windows charmap encode hatasını önle
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJE_KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJE_KOK))

from recete_kontrol.medula_rapor_tarayici import (
    _medula_hwnd_bul, _html_doc, _pywinauto_yukle, _html_dom_hazir_bekle,
    _pencereyi_one_getir,
)

OUTPUT_DIR = Path(__file__).resolve().parent
HTML_OUT = OUTPUT_DIR / '_inceleme_html.html'
TREE_OUT = OUTPUT_DIR / '_inceleme_ui_tree.txt'
PNG_OUT = OUTPUT_DIR / '_inceleme_screenshot.png'
OZET_OUT = OUTPUT_DIR / '_inceleme_ozet.txt'


def dump(hwnd):
    ozet = []

    def emit(msg):
        print(msg)
        ozet.append(msg)

    # 1. Pencere başlığı
    try:
        import win32gui
        title = win32gui.GetWindowText(hwnd)
        emit(f'Pencere başlığı: {title}')
    except Exception as e:
        emit(f'win32gui hatası: {e}')

    doc = _html_doc(hwnd)
    if doc is None:
        emit('UYARI: HTML DOM proxy alınamadı')
    else:
        try:
            emit(f'DOM url: {doc.url}')
        except Exception:
            pass
        try:
            html = doc.documentElement.outerHTML
            HTML_OUT.write_text(html, encoding='utf-8', errors='replace')
            emit(f'HTML dump: {HTML_OUT.name} ({len(html)} char)')
        except Exception as e:
            emit(f'HTML dump hatası: {e}')

        # Önemli ID kontrolü
        ozel_idler = [
            'f:t18', 'f:buttonRaporListesi', 'f:buttonBitmisRapor',
            'form1:buttonSonlandirilmamisReceteler',
            'form1:tableExReceteList',
            'form1:menuHtmlCommandExButton31',  # Reçete Listesi menü
        ]
        emit('\nÖnemli ID kontrolü:')
        for eid in ozel_idler:
            try:
                el = doc.getElementById(eid)
                emit(f'  {eid}: {"VAR" if el is not None else "yok"}')
            except Exception as e:
                emit(f'  {eid}: hata ({e})')

        # rowClass1/2 sayıları (reçete tablo satırları)
        for cls in ('rowClass1', 'rowClass2'):
            try:
                els = doc.getElementsByClassName(cls)
                emit(f'  class="{cls}": {els.length} eleman')
            except Exception:
                pass

        # td[veri="4"] — B grubu
        try:
            tds = doc.getElementsByTagName('TD')
            ver_4 = []
            for i in range(tds.length):
                t = tds.item(i)
                try:
                    if t.getAttribute('veri') == '4':
                        ver_4.append((t.innerText or '').strip()[:30])
                except Exception:
                    continue
            emit(f'  td[veri="4"] sayısı: {len(ver_4)} → ilkler: {ver_4[:3]}')
        except Exception:
            pass

        # Input/button id'leri (ilk 30)
        emit("\nForm elementleri (input/button/a/img — ilk 50):")
        sayac = 0
        for tag in ('input', 'button', 'a', 'img'):
            try:
                els = doc.getElementsByTagName(tag)
                for i in range(els.length):
                    e = els.item(i)
                    try:
                        eid = e.id
                        if not eid:
                            continue
                        etype = e.getAttribute('type') or ''
                        eval_ = (e.getAttribute('value') or '')[:30]
                        etxt = (e.innerText or '').strip()[:40]
                        ealt = (e.getAttribute('alt') or '')[:30]
                        emit(f'  <{tag} id="{eid}" type="{etype}" '
                             f'alt="{ealt}" text="{etxt}">')
                        sayac += 1
                        if sayac >= 50:
                            break
                    except Exception:
                        continue
                if sayac >= 50:
                    break
            except Exception:
                continue

    # UI tree (pywinauto UIA)
    try:
        Application, Desktop, send_keys = _pywinauto_yukle()
        app = Application(backend='uia').connect(handle=hwnd, timeout=5)
        win = app.window(handle=hwnd)
        lines = []

        def uia_dump(elem, depth=0):
            if depth > 6:
                return
            try:
                txt = (elem.element_info.name or '')[:60]
                ctrl = elem.element_info.control_type
                aid = elem.element_info.automation_id
                cls = elem.element_info.class_name
                rect = elem.element_info.rectangle
                lines.append(
                    f'{"  " * depth}- [{ctrl}] name={txt!r} aid={aid!r} '
                    f'cls={cls!r} rect=({rect.left},{rect.top},{rect.right},{rect.bottom})')
                for c in elem.children():
                    uia_dump(c, depth + 1)
            except Exception as e:
                lines.append(f'{"  " * depth}- <error: {e}>')

        uia_dump(win)
        TREE_OUT.write_text('\n'.join(lines), encoding='utf-8')
        emit(f'\nUI tree dump: {TREE_OUT.name} ({len(lines)} satır)')
    except Exception as e:
        emit(f'UI tree dump hatası: {e}')

    # Screenshot
    try:
        from PIL import ImageGrab
        import win32gui
        rect = win32gui.GetWindowRect(hwnd)
        img = ImageGrab.grab(bbox=rect)
        img.save(str(PNG_OUT))
        emit(f'Screenshot: {PNG_OUT.name} {rect}')
    except Exception as e:
        emit(f'Screenshot hatası: {e}')

    OZET_OUT.write_text('\n'.join(ozet), encoding='utf-8')


def main():
    print('=== MEDULA INCELEME ===')
    hwnd = _medula_hwnd_bul()
    if not hwnd:
        print('HATA: Medula penceresi bulunamadı')
        return 1
    print(f'Medula hwnd: {hwnd}')

    _pencereyi_one_getir(hwnd)
    import time
    time.sleep(0.4)

    args = sys.argv[1:]
    if args and args[0] == 'click' and len(args) >= 2:
        target_id = args[1]
        print(f'>>> Tıklanıyor: {target_id}')
        doc = _html_dom_hazir_bekle(hwnd, sure_sn=10.0)
        if doc is None:
            doc = _html_doc(hwnd)
        if doc is None:
            print('HATA: DOM yok')
            return 1
        try:
            el = doc.getElementById(target_id)
            if el is None:
                print(f'HATA: {target_id} bulunamadı')
                return 1
            try:
                el.click()
            except Exception as e:
                print(f'click() hatası: {e} — fireEvent dene')
                el.fireEvent('onclick')
            time.sleep(3.0)
            _html_dom_hazir_bekle(hwnd, sure_sn=10.0)
        except Exception as e:
            print(f'Tıklama hatası: {e}')
            return 1
    elif args and args[0] == 'row1':
        print('>>> 1. satıra (rowClass1/2) tıklanıyor')
        doc = _html_dom_hazir_bekle(hwnd, sure_sn=10.0)
        if doc is None:
            doc = _html_doc(hwnd)
        if doc is None:
            print('HATA: DOM yok')
            return 1
        rows = None
        for cls in ('rowClass1', 'rowClass2'):
            rs = doc.getElementsByClassName(cls)
            if rs and rs.length > 0:
                rows = rs
                break
        if not rows:
            print('HATA: rowClass1/2 yok')
            return 1
        ilk = rows.item(0)
        print(f'1. satır innerHTML: {(ilk.innerHTML or "")[:200]}')
        try:
            ilk.click()
            print('click() OK')
        except Exception as e:
            print(f'click() hatası: {e} — fireEvent dene')
            try:
                ilk.fireEvent('onclick')
                print('fireEvent OK')
            except Exception as e2:
                print(f'fireEvent de hatası: {e2}')
        time.sleep(3.0)
        _html_dom_hazir_bekle(hwnd, sure_sn=10.0)
    elif args and args[0] == 'row1_dispatch':
        idx = int(args[1]) if len(args) >= 2 else 0
        tr_id = f'TR_parentof_form1:tableExReceteList:{idx}:rowActionReceteSec'
        print(f'>>> dispatchEvent ile {idx}. satır TR: {tr_id}')
        doc = _html_dom_hazir_bekle(hwnd, sure_sn=10.0)
        if doc is None:
            doc = _html_doc(hwnd)
        if doc is None:
            print('HATA: DOM yok')
            return 1
        js = (
            "(function(){"
            "var tr=document.getElementById(\"" + tr_id + "\");"
            "if(!tr){return;}"
            "var ev;"
            "if(document.createEvent){"
            "ev=document.createEvent('MouseEvents');"
            "ev.initMouseEvent('click',true,true,window,1,0,0,0,0,false,false,false,false,0,null);"
            "tr.dispatchEvent(ev);"
            "}else if(document.createEventObject){"
            "ev=document.createEventObject();"
            "tr.fireEvent('onclick',ev);"
            "}"
            "})();"
        )
        print(f'JS: {js[:120]}...')
        try:
            doc.parentWindow.execScript(js, 'JavaScript')
            print('execScript OK')
        except Exception as e:
            print(f'execScript hatası: {e}')
        time.sleep(3.0)
        _html_dom_hazir_bekle(hwnd, sure_sn=15.0)
    elif args and args[0] == 'row1_submit':
        idx = int(args[1]) if len(args) >= 2 else 0
        print(f'>>> myfaces.oam.submitForm ile {idx}. satır seç (rowAction)')
        doc = _html_dom_hazir_bekle(hwnd, sure_sn=10.0)
        if doc is None:
            doc = _html_doc(hwnd)
        if doc is None:
            print('HATA: DOM yok')
            return 1
        action_id = f'form1:tableExReceteList:{idx}:rowActionReceteSec'
        js = f"myfaces.oam.submitForm('form1','{action_id}','',[]);"
        print(f'JS: {js}')
        try:
            doc.parentWindow.execScript(js, 'JavaScript')
            print('execScript OK')
        except Exception as e:
            print(f'execScript hatası: {e}')
        time.sleep(3.0)
        _html_dom_hazir_bekle(hwnd, sure_sn=15.0)
    elif args and args[0] == 'b_grubu':
        print('>>> B grubu (td[veri="4"]) tıklanıyor')
        doc = _html_dom_hazir_bekle(hwnd, sure_sn=10.0)
        if doc is None:
            doc = _html_doc(hwnd)
        if doc is None:
            print('HATA: DOM yok')
            return 1
        try:
            b_td = doc.querySelector('td[veri="4"]')
        except Exception:
            b_td = None
            tds = doc.getElementsByTagName('TD')
            for i in range(tds.length):
                t = tds.item(i)
                try:
                    if t.getAttribute('veri') == '4':
                        b_td = t
                        break
                except Exception:
                    continue
        if b_td is None:
            print('HATA: td[veri="4"] bulunamadı')
            return 1
        try:
            b_td.click()
            print('click OK')
        except Exception as e:
            print(f'click hatası: {e}')
            try:
                b_td.fireEvent('onclick')
            except Exception:
                pass
        time.sleep(1.5)

    dump(hwnd)
    return 0


if __name__ == '__main__':
    sys.exit(main())
