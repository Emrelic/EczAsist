# MF (Mal Fazlasi) Analiz Modulu - Tasarim Dokumani

**Tarih:** 2025-12-24
**Durum:** Tasarim Asamasinda

---

## Modul Tanimi

Bu modul, ilac takip, ekstre kontrol ve kasa sayimi gibi diger modullerden bagimsiz olarak calisacak ayri bir analiz programidir.

---

## Temel Kavramlar ve Isleyis

### 1. Stok ve Satis Bilgileri
- Eczanede bir ilacin stogu var
- Bu ilacin bir aylik gidisi (satis miktari) var

### 2. Depo Odeme Vadesi
- Ecza deposundan ay icinde (1-31 arasi) alinan ilaclarin parasi **ortalama 90 gun sonra** odeniyor
- Bu, o aydan **3 ay sonra ayin 15. gunune** denk geliyor
- **Ornek:** 1-31 Ocak arasinda alinan mallarin parasi **15 Nisan**'da depoya odeniyor

### 3. SGK Tahsilat Vadesi
- Ay icinde SGK'ya satilan ilaclarin parasi ayni sekilde **ortalama 90 gun vade** ile tahsil ediliyor
- **3 ay sonra ay ortasi (15. gun)** SGK'dan geliyor
- **Ornek:** 1-31 Ocak arasinda recetesi girilip satilan ilaclarin parasi **15 Nisan**'da SGK'dan geliyor

### 4. Nakit Satis
- Nakit satilan ilaclarin parasi **aninda** tahsil ediliyor

### 5. Kredi Karti Satisi
- Kredi karti ile satilan ilaclarin parasi **45 gun sonra** tahsil ediliyor

### 6. Eczane Ciro Dagilimi
- Her eczanenin belli yuzdeler ile SGK, nakit ve kredi karti cirosu var
- Bu yuzdeler eczaneye gore degiskenlik gosteriyor

### 7. SGK Katilim Paylari

#### Calisan Sigortalilar
- Ilac tutarinin **%20'si** aninda nakit veya kredi karti olarak tahsil ediliyor

#### Emekli Sigortalilar
- Ilac tutarinin **%10'u** takip eden **ikinci ayin sonunda** eczane hesabina yatiriliyor
- **Ornek:** 1-31 Ocak arasinda ilac alan emeklinin %10 katilim payi **31 Mart**'ta eczane hesabina yatiriliyor

### 8. Mal Fazlasi (MF) Kampanyalari
- Ilaclarda kampanyalar yayinlanabiliyor
- **Ornekler:**
  - **5+1:** 5 tane parasi odenip 6 tane aliniyor (1 bedava)
  - **10+3:** 10 tane parasi odenip 13 tane aliniyor (3 bedava)
  - **100+50:** 100 tane parasi odenip 150 tane aliniyor (50 bedava)

### 9. Stok Maliyeti
- MF almak icin belli bir miktar toplu almak gerekebiliyor
- Bu da **stok maliyeti** demek
- **Aylik faiz kadar stok maliyeti** var diyebiliriz

### 10. Zam Faktoru
- Belli bir tarihte belli bir oranda zam gelebilir
- Zama gore onceden stok yapmanin avantaji/dezavantaji olacaktir

---

## Analiz Gereksinimleri

### Karsilastirilacak Durumlar

1. **MF'siz Alim Durumu**
   - Normal fiyattan, ihtiyac kadar alim
   - Dusuk stok maliyeti
   - Kampanya avantajindan yararlanilmiyor

2. **MF'li Alim Durumu**
   - Toplu alim ile bedava urun kazanimi
   - Yuksek stok maliyeti (faiz)
   - Kampanya avantajindan yararlaniliyor

3. **Zam Oncesi Stok Yapma Durumu**
   - Zam oncesi fiyattan toplu alim
   - Stok maliyeti vs zam avantaji karsilastirmasi

### Gosterim Sekli
- **Iki durum yan yana gosterilmeli**
- Bir ilac icin MF'li/MF'siz veya toplu/normal alim durumlari karsilastirilmali
- Net kar/zarar hesabi yapilmali

---

## Hesaplanacak Degerler (Taslak)

1. Toplam alim maliyeti
2. Stok tutma maliyeti (faiz)
3. Satis gelirleri (SGK + Nakit + Kredi Karti)
4. Tahsilat zamanlari ve nakit akisi
5. Net kar/zarar
6. Karsilastirmali analiz tablosu

---

## Sonraki Adimlar

- [ ] Arayuz tasarimi
- [ ] Hesaplama formullerinin detaylandirilmasi
- [ ] Veritabani yapisi (gerekirse)
- [ ] Grafik/tablo gosterimi
- [ ] Simülasyon motoru

---

**Not:** Bu dokuman 24 Aralik 2024 gece konusmasindan kaydedilmistir. Yarin kaldigi yerden devam edilecektir.
