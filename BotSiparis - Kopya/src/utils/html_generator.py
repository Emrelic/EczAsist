"""
HTML siparis listesi olusturma modulu
"""
import os
import tempfile
from datetime import datetime


def get_vade_bilgileri():
    """Depo vade bilgilerini cevresel degiskenlerden oku"""
    return {
        "alliance": int(os.getenv("ALLIANCE_VADE", "1")),
        "selcuk": int(os.getenv("SELCUK_VADE", "1")),
        "yusufpasa": int(os.getenv("YUSUFPASA_VADE", "1")),
        "iskoop": int(os.getenv("ISKOOP_VADE", "1")),
        "bursa": int(os.getenv("BURSA_VADE", "1")),
        "farmazon": int(os.getenv("FARMAZON_VADE", "1")),
        "sancak": int(os.getenv("SANCAK_VADE", "1"))
    }


def get_aylik_faiz():
    """Aylik faiz oranini oku"""
    faiz_str = os.getenv("AYLIK_FAIZ", "4").replace(",", ".")
    return float(faiz_str) / 100


def turkce_karakter_temizle(metin):
    """Turkce karakterleri Ingilizce karsiliklariyla degistir"""
    if not metin:
        return metin
    metin = str(metin)
    metin = metin.replace('ı', 'i').replace('İ', 'I').replace('ş', 's').replace('Ş', 'S')
    metin = metin.replace('ğ', 'g').replace('Ğ', 'G').replace('ü', 'u').replace('Ü', 'U')
    metin = metin.replace('ö', 'o').replace('Ö', 'O').replace('ç', 'c').replace('Ç', 'C')
    return metin


def create_html_file(products, eczane_info=None):
    """
    Urunlerden tam ozellikli HTML dosyasi olustur

    Args:
        products: Urun listesi
        eczane_info: Eczane bilgileri dict

    Returns:
        str: Olusturulan HTML dosyasinin yolu
    """
    # Tarih bilgisi
    tarih = datetime.now().strftime("%d/%m/%Y %H:%M")

    # HTML icerigi olustur
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Siparis Listesi</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            background: #f5f5f5;
        }}
        .page-container {{
            position: fixed;
            left: 0;
            top: 0;
            width: 100vw;
            height: 100vh;
            background: white;
            overflow-y: auto;
            overflow-x: hidden;
            padding: 15px;
            box-sizing: border-box;
        }}
        h1 {{
            color: #2196F3;
            font-size: 22px;
            text-align: center;
            margin-bottom: 10px;
        }}
        .info {{
            background: #e3f2fd;
            padding: 10px;
            margin-bottom: 10px;
            font-size: 12px;
        }}
        .summary {{
            background: #fff3cd;
            padding: 10px;
            text-align: center;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background: #2196F3;
            color: white;
            padding: 8px 5px;
            font-size: 11px;
            text-align: left;
        }}
        td {{
            padding: 6px 5px;
            border-bottom: 1px solid #ddd;
            font-size: 11px;
        }}
        .depo-btn {{
            display: inline-block;
            background: #4CAF50;
            color: white;
            padding: 3px 8px;
            margin: 2px;
            border-radius: 3px;
            text-decoration: none;
            font-size: 11px;
        }}
        .barkod {{
            background: #e3f2fd;
            padding: 2px 6px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 11px;
            display: inline-block;
            margin-top: 3px;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            padding: 15px;
            background: #f5f5f5;
            font-size: 11px;
            color: #666;
        }}
        .finansal-info {{
            background: #e8f5e9;
            border: 1px solid #4CAF50;
            padding: 10px;
            margin-bottom: 15px;
            border-radius: 5px;
            font-size: 12px;
        }}
        .finansal-info b {{
            color: #2e7d32;
        }}
        .efektif {{
            color: #d32f2f;
            font-size: 12px;
            font-weight: bold;
        }}
        .en-karli {{
            background: #fff9c4 !important;
            font-weight: bold;
        }}
        .star {{
            color: #ff9800;
            font-weight: bold;
        }}
        .legend {{
            background: #f5f5f5;
            padding: 10px;
            margin-top: 15px;
            border-radius: 5px;
            font-size: 11px;
        }}
        .legend-item {{
            margin: 5px 0;
        }}
    </style>
    <script>
        window.addEventListener('load', function() {{
            const screenWidth = window.screen.width;
            const screenHeight = window.screen.height;
            window.resizeTo(screenWidth / 2, screenHeight);
            window.moveTo(0, 0);
        }});

        function copyBarkod(barkod) {{
            navigator.clipboard.writeText(barkod).then(() => {{
                console.log('Barkod kopyalandi:', barkod);
            }});
        }}

        function openDepoWindow(url, depoName, barkod) {{
            navigator.clipboard.writeText(barkod).then(() => {{
                console.log('Barkod kopyalandi:', barkod);
            }});

            const w = window.screen.width / 2;
            const h = window.screen.height;
            const l = window.screen.width / 2;

            const features = `width=${{w}},height=${{h}},left=${{l}},top=0,scrollbars=yes,resizable=yes`;
            window.open(url, depoName, features);

            return false;
        }}
    </script>
</head>
<body>
<div class="page-container">
    <h1>SIPARIS LISTESI</h1>
    <p style="text-align:center; font-size:12px; color:#666;">{tarih}</p>
"""

    # Eczane bilgileri
    if eczane_info:
        html_content += '<div class="info">'
        if eczane_info.get("eczane_adi"):
            html_content += f"Eczane: {eczane_info['eczane_adi']}<br>"
        if eczane_info.get("eczaci_adi"):
            html_content += f"Eczaci: {eczane_info['eczaci_adi']}<br>"
        html_content += "</div>"

    # Finansal bilgiler
    vade_bilgileri = get_vade_bilgileri()
    aylik_faiz = get_aylik_faiz()

    html_content += '<div class="finansal-info">'
    html_content += f'<b>Finansal Parametreler:</b> Aylik Faiz: <b>%{aylik_faiz*100:.1f}</b> | '
    html_content += f'Vadeler: Alliance/Selcuk/YP: <b>{vade_bilgileri["alliance"]} ay</b>, '
    html_content += f'Koop/BEK/Sancak: <b>{vade_bilgileri["iskoop"]} ay</b><br>'
    html_content += '<small style="color:#666;">Efektif fiyat = Baz fiyat + (Para bagli kalma suresi x Bilesik faiz). '
    html_content += 'Gec odeme = dusuk efektif fiyat (avantaj), Erken odeme = yuksek efektif fiyat (dezavantaj)</small>'
    html_content += '</div>'

    # Ozet
    html_content += f'<div class="summary">Toplam {len(products)} urun</div>'

    # Tablo baslangic
    html_content += """
<table>
<tr>
<th>#</th>
<th>Urun Adi</th>
<th>Depocu</th>
<th>Stok</th>
<th>Iht</th>
<th>MinStk</th>
<th>Siparis</th>
<th>Depolar</th>
</tr>
"""

    # Urun satirlari
    for idx, product in enumerate(products, 1):
        urun_adi = product.get("urun_adi", "-")
        barkod = product.get("barkod", "-")
        siparis_adet = product.get("siparis_adet", 0)

        # GUI'deki kolonlar
        depocu_fiyat = product.get("alliance_durum", {}).get("fiyat", "-")
        if isinstance(depocu_fiyat, (int, float)):
            depocu_str = f"{depocu_fiyat:.2f}".replace(".", ",")
        else:
            depocu_str = str(depocu_fiyat)

        stok = product.get("stok", "-")
        mf = product.get("mf", "-")
        minstk = product.get("minstk", "-")

        # Aylik gidis bilgisi
        monthly_sales = product.get("monthly_sales", {})
        aylik_gidis_html = ""
        if monthly_sales:
            today = datetime.now()
            ay_parts = []

            for i in range(12, -1, -1):
                target_month = today.month - i
                target_year = today.year

                while target_month <= 0:
                    target_month += 12
                    target_year -= 1

                col_key = f"{target_month:02d}.{target_year % 100:02d}"
                deger = monthly_sales.get(col_key, "0")

                ay_parts.append(f'<span style="color:#666; font-size:14px;">{target_month}:{target_year % 100:02d}</span> <b style="font-size:14px;">{deger}</b>')

            aylik_gidis_html = " ".join(ay_parts)

            top = monthly_sales.get("Top", "0")
            ort = monthly_sales.get("Ort", "0")
            aylik_gidis_html += f' <span style="color:#000; font-size:14px; font-weight:bold;">Top: {top}</span> <span style="color:#2196F3; font-size:16px; font-weight:bold;">Ort: {ort}</span>'

        # Depo linkleri
        depo_links = []
        if product.get("alliance_durum", {}).get("stok_var"):
            depo_links.append(f'<a href="#" class="depo-btn" onclick="return openDepoWindow(\'https://esiparisv2.alliance-healthcare.com.tr/Sales/QuickOrder\', \'Alliance\', \'{barkod}\');">All</a>')
        if product.get("selcuk_durum", {}).get("stok_var"):
            depo_links.append(f'<a href="#" class="depo-btn" onclick="return openDepoWindow(\'https://webdepo.selcukecza.com.tr/Siparis/hizlisiparis.aspx\', \'Selcuk\', \'{barkod}\');">Sel</a>')
        if product.get("yusufpasa_durum", {}).get("stok_var"):
            depo_links.append(f'<a href="#" class="depo-btn" onclick="return openDepoWindow(\'http://eticaret.yusufpasa.com/CustomerBasket.asp\', \'Yusufpasa\', \'{barkod}\');">Yus</a>')
        if product.get("sancak_durum", {}).get("stok_var"):
            depo_links.append(f'<a href="#" class="depo-btn" onclick="return openDepoWindow(\'https://eticaret.sancakecza.com.tr/Sales/Cart\', \'Sancak\', \'{barkod}\');">San</a>')
        if product.get("farmazon_durum", {}).get("stok_var"):
            depo_links.append(f'<a href="#" class="depo-btn" onclick="return openDepoWindow(\'https://www.farmazon.com.tr/homepage\', \'Farmazon\', \'{barkod}\');">Fz</a>')
        if product.get("iskoop_durum", {}).get("stok_var"):
            depo_links.append(f'<a href="#" class="depo-btn" onclick="return openDepoWindow(\'https://esube.iskoop.org/irj/portal/\', \'Iskoop\', \'{barkod}\');">Isk</a>')
        if product.get("bursa_durum", {}).get("stok_var"):
            depo_links.append(f'<a href="#" class="depo-btn" onclick="return openDepoWindow(\'https://esube.bek.org.tr/irj/portal/\', \'Bursa\', \'{barkod}\');">Bur</a>')

        depo_html = " ".join(depo_links) if depo_links else '<span style="color:#999;">Yok</span>'

        # Depo sartlarini topla - her depo icin ayri liste
        depo_mapping = {
            "alliance": ("Alliance", "#4CAF50", "https://esiparisv2.alliance-healthcare.com.tr/Sales/QuickOrder"),
            "selcuk": ("Selcuk", "#2196F3", "https://webdepo.selcukecza.com.tr/Siparis/hizlisiparis.aspx"),
            "yusufpasa": ("Yusuf Pasa", "#FF9800", "http://eticaret.yusufpasa.com/CustomerBasket.asp"),
            "iskoop": ("Iskoop", "#9C27B0", "https://esube.iskoop.org/irj/portal/"),
            "bursa": ("BEK", "#00BCD4", "https://esube.bek.org.tr/irj/portal/"),
            "sancak": ("Sancak", "#E91E63", "https://eticaret.sancakecza.com.tr/Sales/Cart"),
            "farmazon": ("Farmazon", "#795548", "https://www.farmazon.com.tr/homepage")
        }

        # Her depo icin sartlari ayri topla
        depo_sartlari = {}  # {depo_key: [(sart_str, fiyat_str, efektif_str, is_en_karli), ...]}
        aktif_depolar = []  # Stok olan depolar

        # En karli sonucu al
        en_karli_sonuc = product.get("en_karli_sonuc", {})
        en_karli_depo = en_karli_sonuc.get("depo")
        en_karli_sart = en_karli_sonuc.get("sart")
        tum_secenekler = en_karli_sonuc.get("tum_secenekler", [])

        # Efektif fiyatlari bir dict'e cevir
        efektif_dict = {}
        for sec in tum_secenekler:
            key = (sec.get("depo"), sec.get("sart"))
            efektif_dict[key] = sec.get("efektif_birim", 0)

        # Her depo icin onerilen siparis adedini hesapla
        depo_siparis_adet = {}  # {depo_key: adet}

        # Farmazon pahali mi kontrol et (HTML'de gostermek icin)
        farmazon_pahali = False
        farmazon_durum = product.get("farmazon_durum", {})
        if farmazon_durum.get("pahali"):
            farmazon_pahali = True

        for depo_key, (depo_name, depo_color, depo_url) in depo_mapping.items():
            depo_durum = product.get(f"{depo_key}_durum", {})

            # Depoda stok yoksa sartlari gosterme (Farmazon pahali ise de atla)
            if not depo_durum.get("stok_var"):
                # Farmazon pahali ise yine de goster (PAHALI yazmak icin)
                if depo_key == "farmazon" and farmazon_pahali:
                    pass  # Devam et, goster
                else:
                    continue

            # Varsayilan siparis adedi
            depo_siparis_adet[depo_key] = siparis_adet

            # Farmazon icin: en karli secenek bu depodaysa ve MF'li ise, min_adet kullan
            if depo_key == "farmazon" and en_karli_depo == "farmazon":
                # en_karli_sart formatini kontrol et (ornek: "10+1")
                if en_karli_sart and "+" in str(en_karli_sart):
                    try:
                        min_adet_str = en_karli_sart.split("+")[0]
                        farmazon_min_adet = int(min_adet_str)
                        if farmazon_min_adet > siparis_adet:
                            depo_siparis_adet[depo_key] = farmazon_min_adet
                    except (ValueError, IndexError):
                        pass

            aktif_depolar.append((depo_key, depo_name, depo_color, depo_url))
            depo_sartlari[depo_key] = []

            satis_kosullari = depo_durum.get("satis_kosullari", [])

            if satis_kosullari:
                for kosul in satis_kosullari:
                    birim_fiyat = kosul.get("birim_fiyat", kosul.get("fiyat", 0))
                    min_adet = kosul.get("min_adet", 1)
                    mf_val = kosul.get("mf", 0)

                    if isinstance(birim_fiyat, (int, float)) and birim_fiyat > 0:
                        # Iskoop ve Bursa icin KDV ekle (KDV haric fiyat veriyorlar)
                        if depo_key in ("iskoop", "bursa"):
                            kdv_orani = kosul.get("kdv_orani", 10)
                            birim_fiyat_kdv = birim_fiyat * (1 + kdv_orani / 100)
                        else:
                            birim_fiyat_kdv = birim_fiyat

                        fiyat_str = f"{birim_fiyat_kdv:.2f}".replace(".", ",")

                        # MF varsa goster
                        if mf_val > 0:
                            sart_str = f"{min_adet}+{mf_val}"
                        else:
                            sart_str = "1"

                        # Efektif fiyati bul
                        efektif = efektif_dict.get((depo_key, sart_str), 0)
                        efektif_str = f"{efektif:.2f}".replace(".", ",") if efektif > 0 else "-"

                        # En karli mi?
                        is_en_karli = (depo_key == en_karli_depo and sart_str == en_karli_sart)

                        depo_sartlari[depo_key].append((sart_str, fiyat_str, efektif_str, is_en_karli))

            # Farmazon icin: satis_kosullari bos olabilir, tum_secenekler'den al
            if depo_key == "farmazon" and not depo_sartlari[depo_key]:
                # Farmazon pahali mi?
                if farmazon_pahali:
                    # PAHALI - fiyat yerine uyari goster
                    fiyat = farmazon_durum.get("fiyat", 0)
                    psf = farmazon_durum.get("psf", 0)
                    if fiyat and psf:
                        fiyat_str = f"{fiyat:.2f}".replace(".", ",")
                        psf_str = f"{psf:.2f}".replace(".", ",")
                        # Ozel format: PAHALI (fiyat > PSF)
                        depo_sartlari[depo_key].append(("PAHALI", fiyat_str, f"PSF: {psf_str}", False))
                    else:
                        depo_sartlari[depo_key].append(("PAHALI", "-", "-", False))
                else:
                    # tum_secenekler icinden farmazon seceneklerini bul
                    for sec in tum_secenekler:
                        if sec.get("depo") == "farmazon":
                            sart_str = sec.get("sart", "1")
                            birim_fiyat = sec.get("birim_fiyat", 0)
                            efektif = sec.get("efektif_birim", 0)

                            if birim_fiyat > 0:
                                fiyat_str = f"{birim_fiyat:.2f}".replace(".", ",")
                                efektif_str = f"{efektif:.2f}".replace(".", ",") if efektif > 0 else "-"
                                is_en_karli = (en_karli_depo == "farmazon" and en_karli_sart == sart_str)
                                depo_sartlari[depo_key].append((sart_str, fiyat_str, efektif_str, is_en_karli))

        # Depo sartlari tablosu olustur
        if aktif_depolar:
            depo_sartlari_html = '<table style="width:100%; border-collapse:collapse; margin-top:5px;">'
            # Baslik satiri - depo isimleri, siparis adedi ve vadeleri (tiklanabilir linkler)
            depo_sartlari_html += '<tr>'
            for depo_key, depo_name, depo_color, depo_url in aktif_depolar:
                vade = vade_bilgileri.get(depo_key, 1)
                adet = depo_siparis_adet.get(depo_key, siparis_adet)
                # En karli depo ise yildiz ekle
                star_html = '<span class="star" style="font-size:16px;">★</span> ' if depo_key == en_karli_depo else ''
                # Farmazon'da adet farkli ise vurgula
                if depo_key == "farmazon" and adet != siparis_adet:
                    adet_html = f'<span style="background:#fff3cd; color:#000; padding:2px 6px; border-radius:3px; font-size:13px;">{adet} ad.</span>'
                else:
                    adet_html = f'<span style="font-size:12px;">{adet} ad.</span>'
                depo_sartlari_html += f'<th style="background:{depo_color}; color:white; padding:8px 10px; text-align:center; font-size:14px; font-weight:bold; border:1px solid #ddd; cursor:pointer;" onclick="openDepoWindow(\'{depo_url}\', \'{depo_name}\', \'{barkod}\')\">{star_html}<span style="text-decoration:underline;">{depo_name}</span> {adet_html}<br><small style="font-weight:normal; font-size:11px;">({vade} ay vade)</small></th>'
            depo_sartlari_html += '</tr>'

            # Maksimum sart sayisini bul
            max_sart = max(len(depo_sartlari.get(d[0], [])) for d in aktif_depolar) if aktif_depolar else 0

            # Sart satirlari
            for i in range(max_sart):
                depo_sartlari_html += '<tr>'
                for depo_key, depo_name, depo_color, depo_url in aktif_depolar:
                    sartlar = depo_sartlari.get(depo_key, [])
                    if i < len(sartlar):
                        sart_str, fiyat_str, efektif_str, is_en_karli = sartlar[i]

                        # PAHALI durumu icin ozel stil (kirmizi arka plan)
                        if sart_str == "PAHALI":
                            cell_style = "padding:6px 8px; text-align:center; font-size:12px; border:1px solid #ddd; background:#ffcdd2;"
                            # PSF bilgisi efektif_str'de
                            depo_sartlari_html += f'<td style="{cell_style}"><b style="color:#c62828;">⚠ PAHALI</b><br><span style="font-size:11px;">{fiyat_str} TL</span><br><span style="font-size:10px; color:#666;">{efektif_str}</span></td>'
                        elif is_en_karli:
                            # En karli ise ozel stil
                            cell_style = "padding:6px 8px; text-align:center; font-size:12px; border:1px solid #ddd; background:#fff9c4;"
                            star = '<span class="star">★</span> '
                            efektif_html = f'<br><span class="efektif">Efektif: {efektif_str} TL</span>' if efektif_str != "-" else ""
                            depo_sartlari_html += f'<td style="{cell_style}">{star}<b>{sart_str}</b><br><span style="font-size:13px;">{fiyat_str} TL</span>{efektif_html}</td>'
                        else:
                            cell_style = "padding:6px 8px; text-align:center; font-size:12px; border:1px solid #ddd; background:#f9f9f9;"
                            star = ""
                            # Efektif fiyat goster - daha belirgin
                            efektif_html = f'<br><span class="efektif">Efektif: {efektif_str} TL</span>' if efektif_str != "-" else ""
                            depo_sartlari_html += f'<td style="{cell_style}">{star}<b>{sart_str}</b><br><span style="font-size:13px;">{fiyat_str} TL</span>{efektif_html}</td>'
                    else:
                        depo_sartlari_html += '<td style="padding:6px 8px; text-align:center; font-size:12px; border:1px solid #ddd; background:#f9f9f9;">-</td>'
                depo_sartlari_html += '</tr>'

            depo_sartlari_html += '</table>'
        else:
            depo_sartlari_html = '<span style="color:#999; font-size:11px;">Depo sartlari bulunamadi</span>'

        # Kac satirlik olacagini hesapla (aylik gidis + depo sartlari)
        row_span = 3

        # Urun satiri
        html_content += f"""<tr>
<td rowspan="{row_span}"><b>{idx}</b></td>
<td><b style="font-size:13px;">{urun_adi}</b><br><span class="barkod" onclick="copyBarkod('{barkod}')">{barkod}</span></td>
<td>{depocu_str}</td>
<td>{stok}</td>
<td>{mf}</td>
<td>{minstk}</td>
<td><b style="background:#fff3cd; padding:2px 5px; font-size:13px;">{siparis_adet}</b></td>
<td>{depo_html}</td>
</tr>
<tr>
<td colspan="7" style="background:#f5f5f5; padding:8px; font-size:14px;">{aylik_gidis_html if aylik_gidis_html else '<span style="color:#999;">Aylik gidis bilgisi yok</span>'}</td>
</tr>
<tr>
<td colspan="7" style="background:#e8f5e9; padding:6px; font-size:11px;"><b>Depo Sartlari:</b> {depo_sartlari_html}</td>
</tr>
"""

    # Legend
    html_content += """</table>

<div class="legend">
<b>Aciklamalar:</b>
<div class="legend-item"><span class="star">★</span> = En karli secenek (en dusuk efektif fiyat)</div>
<div class="legend-item"><span style="color:#d32f2f;">Efektif Fiyat</span> = Gercek finansal maliyet (odeme vadesi + satis suresi + faiz dahil)</div>
<div class="legend-item"><b>Vade Avantaji:</b> Gec odeme yapan depolar (3 ay) erken odeme yapanlara (1 ay) gore avantajli</div>
<div class="legend-item"><b>Formul:</b> Efektif = Baz Fiyat × (1 + Aylik Faiz)^(Ortalama Satis Suresi - Vade)</div>
</div>

<div class="footer">
<p>Bu liste <strong>Botanik Siparis Yardimcisi</strong> tarafindan olusturulmustur.</p>
<p>Olusturulma Tarihi: {tarih}</p>
</div>
</div>
</body>
</html>
"""

    # Gecici dosya olustur
    temp_dir = tempfile.gettempdir()
    filename = f"siparis_listesi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    file_path = os.path.join(temp_dir, filename)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return file_path
