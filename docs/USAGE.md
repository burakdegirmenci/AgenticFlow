# AgenticFlow Kullanım Rehberi

Bu rehber, AgenticFlow ile ilk workflow'unuzu kurmayı, agent'a workflow
ürettirmeyi, zamanlanmış çalıştırmayı ve execution history'yi okumayı
adım adım anlatır.

---

## 1. İlk Site Eklemek

UI'da sol sidebar'dan **Sites** > **+ Yeni Site**.

| Alan | Örnek |
|---|---|
| İsim | `Demo Store` |
| Domain | `demo.example.com` (`http://` veya `/` olmadan) |
| Üye Kodu | `FONxXXXXXXXXXXXXXXXXXXXXXXXXXX` (Ticimax panelinden alın — 32 karakter) |

**Kaydet** > listeden sitenize tıklayıp **"Bağlantıyı test et"**. Yeşil
checkmark görmeniz gerekir. Üye kodu Fernet ile şifrelenir, plain text DB'ye
yazılmaz.

---

## 2. İlk Workflow'u Oluşturmak (manuel)

**Workflows** > **+ Yeni**. Site seç, isim ver: `İlk Workflow`.

Canvas açılır. Sol panelden node'ları sürükle:

1. **Triggers > Manuel** — `trigger.manual`
2. **Ticimax > Ürün Listele** — `ticimax.urun.select`
3. **Output > Log** — `output.log`

Node'ları edge ile bağla (mouse'u node'un sağ noktasından bir sonraki node'a
sürükle).

**`ticimax.urun.select`** node'una tıkla, sağ panelde:

| Config | Değer |
|---|---|
| Aktif Durumu | `1` (aktif) |
| Sayfa Büyüklüğü | `10` |

**Save** > **Run** (üst sağ). Birkaç saniye sonra execution paneli açılır,
her step'in input/output'unu göreceksin.

---

## 3. Agent'a Workflow Ürettirme

Üst sağ **Chat** ikonu → "Yeni sohbet" → site seç.

Doğal dilde yaz:

> "Açık destek ticketlarından son 3 tanesini çek, müşteri sorusuna Türkçe
> kibar bir yanıt üret, **ama gönderme** — sadece log'a yaz."

Claude tool calling ile workflow JSON üretir:

```
trigger.manual → ticimax.get_support_tickets → ai.prompt → output.log
```

Canvas'a otomatik yerleşir. **Run** ile dene. Beğendiysen **Save** > isim ver.

> Agent'ın ürettiği workflow'lar **otomatik aktif edilmez**. Manuel `Run` veya
> `is_active=true` yapmadıkça çalışmaz.

---

## 4. Zamanlanmış Çalıştırma (Schedule)

Mevcut bir workflow'a `trigger.schedule` ekle, edge ile ilk işlem node'una
bağla.

**Cron syntax** (5 alan: dakika saat gün ay haftagünü):

| Cron | Anlamı |
|---|---|
| `*/5 * * * *` | Her 5 dakikada bir |
| `0 6 * * *` | Her gün 06:00 |
| `0 9 * * 1-5` | Hafta içi her gün 09:00 |
| `0 */2 * * *` | Her 2 saatte bir (00, 02, 04, ...) |

Workflow'u **Active** yap (toggle veya `is_active: true`). APScheduler
otomatik kayıt eder. Aktif jobs'u görmek için:

```bash
curl http://127.0.0.1:8000/api/workflows/scheduler/jobs
```

Workflow deaktif edilince veya silinince scheduler kaydını otomatik temizler.
Backend yeniden başladığında tüm aktif workflow'lar `refresh_all()` ile
geri yüklenir.

---

## 5. Polling (Yeni Kayıt İzleme)

**Schedule** "her cron'da çalıştır" demek. **Polling** ise "her N saniyede bir
sorgula, sadece yeni kayıtlar varsa devam et" demek. Bu pattern için iki node
gerekir:

1. **`trigger.polling`** — saf zaman tetikleyicisi
   - `interval_seconds: 300` (5 dk; minimum 10)
2. **Veri çekme node'u** — örn. `ticimax.siparis.select`
3. **`transform.only_new`** — snapshot diff
   - `id_field: SiparisID` (yeni kayıt tespit alanı)
   - `input_key: siparisler` (boş bırakılırsa otomatik bulunur)
   - `emit_on_first_run: false` (varsayılan; ilk koşuda hiçbir şey emit etmez,
     baseline alır)

Akış:
```
trigger.polling → ticimax.siparis.select → transform.only_new → ai.prompt → ...
```

**İlk koşu davranışı:** `only_new` ilk çağrıldığında `polling_snapshots`
tablosuna mevcut tüm ID'leri yazar ve `count: 0` döner. Sonraki koşularda
yalnızca yeni ID'leri downstream'e iletir.

**Throttle:** `transform.only_new` 0 yeni kayıt bulunca downstream'e boş liste
gönderir. Boş listeyle devam etmek istemiyorsanız `logic.if_condition` node'u
ekleyip `count > 0` kontrolü yapın.

---

## 6. Output Node'ları

| Type | Açıklama | Çıktı Yolu |
|---|---|---|
| `output.log` | Inputs'u execution log'una yazar (debug için) | (DB) |
| `output.csv_export` | İlk list-of-dicts'i CSV'ye yazar | `backend/exports/<filename>_<timestamp>.csv` |
| `output.excel_export` | İlk list-of-dicts'i `.xlsx`'e yazar (header bold + freeze) | `backend/exports/<filename>_<timestamp>.xlsx` |
| `output.json_export` | Tüm inputs'u veya `source_field`'ı pretty JSON yazar | `backend/exports/<filename>_<timestamp>.json` |

Hepsi otomatik kaynak bulma yapar: `source_field` boşsa parent çıktıda en
yakın list-of-dicts'i bulur (Ticimax'ın `{"result": {"UrunList": [...]}}`
şekli için ek config gerekmez).

---

## 7. Template Substitution

Node config'lerinde parent çıktılarına `{{node_id.alan.path}}` ile erişin.
Örnek: `ai.prompt` config'inde

```
prompt: "Şu siparişleri özetle: {{sip.siparisler}}"
system: "Sen {{site.name}} için çalışan bir asistansın."
```

Template engine basit dotted path resolver'dır; nested dict / array index
destekler (`{{tkt.result.0.UyeAdi}}`).

---

## 8. Execution History

Sol sidebar > **Executions**. Filtreler:

- **Durum:** SUCCESS / ERROR / RUNNING / PENDING / CANCELLED
- **Trigger:** MANUAL / SCHEDULE / POLLING / AGENT
- **Ara:** workflow adı veya hata metni (case-insensitive substring)

Bir execution'a tıklayınca step-by-step görüntü açılır:

- Her step'in **input** (parent outputs), **output** (node return),
  **error** (varsa stack trace), **süre** (ms), **status**
- Hangi node tipi (`ticimax.urun.select`), hangi node ID (`urn`)

Filtre URL'ye yansır; bookmark'layabilirsiniz.

---

## 9. AI Node'ları (in-workflow)

| Node | Amaç |
|---|---|
| `ai.prompt` | Serbest formda LLM çağrısı (system + prompt + temperature + max_tokens) |
| `ai.classify` | Verilen seçeneklerden birini seçtirir (kategoriler) |
| `ai.extract` | JSON Schema'ya uygun yapılandırılmış çıkarma |

Provider seçimi: config'te `provider` boş bırakılırsa Settings'teki global
default kullanılır (`anthropic_api`, `anthropic_cli`, `google_genai`).

---

## 10. Faydalı Endpoint'ler

```bash
# Tüm node tiplerini listele (kategori bazlı)
curl http://127.0.0.1:8000/api/nodes

# Aktif scheduler jobs
curl http://127.0.0.1:8000/api/workflows/scheduler/jobs

# Bir workflow'u manuel tetikle
curl -X POST http://127.0.0.1:8000/api/workflows/2/run \
  -H 'content-type: application/json' \
  -d '{"input_data": {}}'

# Filtreli execution listesi
curl 'http://127.0.0.1:8000/api/executions?status=ERROR&limit=20'
curl 'http://127.0.0.1:8000/api/executions?search=ticket&trigger_type=MANUAL'
```

API docs: http://127.0.0.1:8000/docs

---

## 11. Demo Workflow'lardan Başlayın

Site eklemenizden sonra:

```bash
cd backend
python -m scripts.seed_db --site-id 1
```

3 demo workflow oluşur. Her birini canvas'ta açıp inceleyebilir, **Run** ile
deneyebilir, modify edebilirsiniz. `--force` ile mevcut demo'lar üzerine yazılır.

---

## 12. Sık Karşılaşılan Hatalar

| Hata | Çözüm |
|---|---|
| `MASTER_KEY not set` | `.env`'de Fernet key yok; `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| Zeep `factory namespace not registered` | `TicimaxService` `fix_factories` çağırmadı; servis cache'i temizle ve restart |
| `ai.prompt` "prompt is empty after interpolation" | Template'in tamamı boş çözüldü; `{{...}}` path'leri yanlış olabilir |
| Excel export "no list-of-dicts found" | Parent çıktıda dict listesi yok veya derin gömülü; `source_field` ile path verin |
| Schedule node aktif olmuyor | Workflow `is_active=False`; UI'dan toggle veya `PATCH /api/workflows/{id} {is_active: true}` |
| Polling sürekli tüm kayıtları işliyor | `transform.only_new` node yok ya da `id_field` yanlış |

Daha fazla bilgi için backend log'larını izleyin (`uvicorn` çıktısı).
