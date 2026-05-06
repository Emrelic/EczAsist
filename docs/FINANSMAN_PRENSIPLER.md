# Eczane Finansman Sistemi (Temel Prensipler)

Bu doküman sipariş verme ve stok optimizasyonu modüllerinin finansal temelini açıklar.
Sipariş/stok/MF/zam modülleri üzerinde çalışırken yükle.

## Ödeme ve Tahsilat Döngüsü

### Depo Ödemeleri (Senet)
- 1-31'i alımları → sonraki ay 1'inde senet kesilir
- Senet, kesim tarihinden **75 gün sonra** ödenir
- Örnek: 1-31 Ocak alımları → 1 Şubat senet → ~17 Nisan ödeme

### SGK Tahsilatı (Fatura)
- 1-31'i SGK satışları → sonraki ay 1'inde fatura kesilir
- Fatura tarihinden **75 gün sonra** SGK öder
- Örnek: 1-31 Ocak satışları → 1 Şubat fatura → ~17 Nisan tahsilat

### İdeal Durum
**Ay içinde alınan mal ay içinde satılırsa** depo ödemesi ile SGK tahsilatı aynı güne denk gelir → finansman maliyeti yok.

## Stok Yapmanın Geçerli Sebepleri

1. **Zam beklentisi** — daha ucuza mal ama erken ödeme finansman maliyeti yaratır; pik noktası geçilince zarara döner.
2. **Mal Fazlası (MF) kampanyaları** — 5+1, 10+3, 20+7, 100+30 vb. Daha ucuz birim maliyet ama fazla stok finansman maliyeti.
3. **İlaç yokluğu riski** — piyasadan çekilecek ilaç için "şu tarihe kadar ihtiyaç" hesaplanır.

## Stok Maliyeti Örnek Senaryo

Ayın 10'u, stok 10, aylık gidiş 30, 100+30 MF (130 adet alım):

| Dönem | Miktar | SGK Tahsilat Gecikme | Finansman Maliyeti |
|-------|--------|---------------------|-------------------|
| Bu ay (20 adet) | 20 | 75 gün | Yok |
| 1. ay sonrası | 30 | 105 gün | 1 ay |
| 2. ay sonrası | 30 | 135 gün | 2 ay |
| 3. ay sonrası | 30 | 165 gün | 3 ay |
| 4. ay (20 gün) | 20 | 195 gün | 4 ay |

## NPV (Net Bugünkü Değer) Prensibi
MF/zamdan önce toplu alım ile ay-be-ay alımı karşılaştırırken her ödemeyi faiz oranıyla bugüne indirgeriz. İndirgenmiş nakit akışları farkı pozitifse stok yapmak avantajlı.

## Karar Noktaları (Sipariş Miktarı)

Zam/MF avantajı belli bir noktadan sonra azalır:

1. **Verimlilik (Maks ROI):** Her 100 TL yatırım için en yüksek getiri
2. **Pareto (%80):** Toplam potansiyel kazancın %80'ine ulaşılan miktar
3. **Optimum/Pik:** Maksimum mutlak kazanç noktası
4. **Sınır:** Karlılığın sıfıra düştüğü, sonrası zarar olan miktar

## Sipariş Verme Modülü Mantığı

- **Varsayılan:** Ay sonuna kadar ihtiyaç − mevcut stok = sipariş miktarı
- **Minimum tutar:** Hesaplanan miktar minimumun altındaysa minimuma tamamlanır
- **Hedef tarih:** Belirtilen tarihe kadar ihtiyaç hesaplanır
- **Zam optimizasyonu:** Pareto/optimum/verimlilik referansıyla optimal miktar
- **MF analizi:** Her MF şartı için 100 TL başına avantaj hesaplanır, en karlı MF seçilir

## Formüller

```
Günlük faiz   = (1 + yıllık_faiz/12)^(1/30) - 1
NPV           = Ödeme / (1 + günlük_faiz)^gün_sayısı
MF birim mlyt = (Alınan × Fiyat) / (Alınan + Bedava)
                Örn: 100+30, 100 TL → 10000/130 = 76.92 TL/adet
Stok finansman = Stok_değeri × (gün/365) × faiz_oranı
```
