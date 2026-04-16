# SelectVaryasyon API — Required Fields

> Date: 2026-04-16 · Status: **ÇÖZÜLDÜ** (Ticimax support örneği ile doğrulandı)

## Bulgu

`SelectVaryasyon` boş döner eğer `Aktif` ve `UrunKartiID` alanları
gönderilmezse. Bu alanlar opsiyonel görünse de **zorunlu** — servis
bunlar olmadan sessizce boş döner (hata vermez).

## Root Cause

Ticimax SOAP API'si (.NET/WCF tabanlı) VaryasyonFiltre'deki bazı
alanları zorunlu tutuyor. Gönderilmezse veya boş string gönderilirse
deserialize hatası oluşuyor ve servis boş sonuç döndürüyor.

## Çözüm

Ticimax support'un resmi örneğindeki zorunlu alanları her zaman gönder:

```python
filtre = client.urun_factory.VaryasyonFiltre(
    Aktif=-1,            # -1 = tümü (ZORUNLU)
    Barkod=barkod,       # filtreleme alanı
    UrunKartiID=-1,      # -1 = tümü (ZORUNLU)
)
sayfalama = client.urun_factory.UrunSayfalama(
    BaslangicIndex=0,
    KayitSayisi=10,
    SiralamaDegeri="ID",   # büyük harf
    SiralamaYonu="DESC",   # büyük harf
)
ayar = client.urun_factory.SelectVaryasyonAyar(KategoriGetir=False)
```

## Kural (tüm Ticimax SOAP çağrıları için)

1. **Boş string gönderme** — `StokKodu=""` WCF'i kırar
2. **Int alanları atma** — `Aktif`, `UrunKartiID` gibi alanlar `-1` ile gönderilmeli
3. **Sıralama büyük harf** — `"ID"`, `"DESC"` (küçük harf çalışmayabilir)
4. **`KategoriGetir=False`** — performans için explicit set et
5. Sadece **kullanılan filtreleri** gönder, gerisi hiç eklenmemeli
