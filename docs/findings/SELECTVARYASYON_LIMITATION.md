# SelectVaryasyon API Limitation

> Date: 2026-04-16 · Status: Ticimax'a ticket açıldı, cevap bekleniyor

## Bulgu

`SelectVaryasyon(Barkod="3569898154440")` boş döner — ama aynı barkod
`SelectUrun(UrunKartiID=37141)` ile erişilebilir.

## Kanıt

```
SelectUrun(UrunKartiID=37141):
  VarID=161411  Barkod=3569898154440  StokKodu=ABRUZ-12  ✅

SelectVaryasyon(Barkod="3569898154440"):
  Zeep ile → boş
  Raw SOAP ile → boş
  Minimal XML (sadece Barkod + KayitSayisi) → boş

SelectVaryasyon(Barkod="3569898112310"):
  → FOUND (bazı barkodlar çalışıyor, bazıları çalışmıyor)
```

## Test edilen XML (raw, zeep bypass)

```xml
<tem:SelectVaryasyon>
   <tem:UyeKodu>***</tem:UyeKodu>
   <tem:f>
      <ns:Barkod>3569898154440</ns:Barkod>
   </tem:f>
   <tem:s>
      <ns:KayitSayisi>10</ns:KayitSayisi>
   </tem:s>
   <tem:varyasyonAyar />
</tem:SelectVaryasyon>
```

HTTP 200, `<SelectVaryasyonResult ... />` (self-closing = boş).

## Olası Nedenler

1. SelectVaryasyon sadece belirli koşuldaki varyasyonları indeksliyor
   (aktif? belirli bir mağaza? belirli bir tarih aralığı?)
2. Ticimax'ta bir bug / stale index
3. WCF servis tarafında bir filtreleme mantığı

## Etki

`stok_guncelle_by_barkod` node'u bu API'ye bağımlıydı. SelectVaryasyon
güvenilmez olduğu sürece barkod bazlı stok güncelleme çalışmaz.

## Çözüm Seçenekleri (ticket cevabına göre)

1. **Ticimax düzeltir** — SelectVaryasyon tüm varyasyonları döner →
   mevcut node direkt çalışır
2. **SelectUrun kullan + barkod index** — ilk seferde tüm ürünleri çek,
   Barkod→VaryasyonID haritasını SQLite'a yaz, sonraki çalıştırmalarda
   index'ten oku. Spec gerekir.
3. **Farklı bir API endpoint** — Ticimax'tan barkod bazlı toplu
   güncelleme API'si öğrenilir (varsa)

## Bekleyen

- [ ] Ticimax ticket cevabı
- [ ] Cevaba göre mimari karar
- [ ] Spec → implement → test (Ersin disiplini)
