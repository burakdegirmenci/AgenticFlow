# AgenticFlow

[![CI](https://github.com/burakdegirmenci/agenticflow/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/burakdegirmenci/agenticflow/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Node.js 20+](https://img.shields.io/badge/Node.js-20+-green.svg)](https://nodejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue.svg)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Code style: ruff + prettier](https://img.shields.io/badge/code_style-ruff%20%2B%20prettier-000000.svg)](https://docs.astral.sh/ruff/)

Ticimax e-ticaret SOAP servislerini görsel workflow editor üzerinden
kullanılabilir hale getiren, Claude / Gemini AI destekli **self-hosted** ve
**single-tenant** otomasyon platformu.

n8n tarzı node-based canvas + agentic chat üzerinden **237 Ticimax operasyonunu**
sürükle-bırak workflow olarak kurgulayabilir, manuel / cron / polling tetikleyici
ile otomatik çalıştırabilirsiniz.

> 📖 **İlk kez mi bakıyorsun?** [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md) — projenin ne yaptığını ve yapmadığını tam olarak anlatır.
> 🏗️ **Geliştirmeye mi başlıyorsun?** [`CONTRIBUTING.md`](CONTRIBUTING.md) + [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) zorunlu okuma.

## Dokümantasyon

| Doküman | İçerik |
|---|---|
| [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md) | Authoritative feature list, kalite hedefleri, non-goals |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Sistem tasarımı, katmanlar, veri akışı, extension points |
| [`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md) | Kod kararlarının gerekçeleri |
| [`docs/TASKS.md`](docs/TASKS.md) | Retro + roadmap (living document) |
| [`docs/USAGE.md`](docs/USAGE.md) | Son kullanıcı rehberi |
| [`docs/prompt.md`](docs/prompt.md) | AI asistanı / yeni geliştirici onboarding prompt'u |
| [`CHANGELOG.md`](CHANGELOG.md) | Sürüm geçmişi |
| [`SECURITY.md`](SECURITY.md) | Credential handling, Fernet rotation, güvenlik bildirimi |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Geliştirme kuralları, komutlar, PR süreci |
| [`llms.txt`](llms.txt) | AI asistanları için proje özeti |

## Özellikler

- **Görsel Flow Builder** — React Flow tabanlı drag-and-drop canvas
- **237 Ticimax Node** — Ürün, sipariş, üye, kargo, ticket, kategori, kampanya,
  custom alan, üye, entegrasyon operasyonları
- **Agentic AI (Claude / Gemini)** — Chat panelinden doğal dilde workflow
  ürettir; in-workflow `ai.prompt`, `ai.classify`, `ai.extract` node'ları
- **Çoklu Site** — Birden fazla Ticimax sitesini tek panelden yönetin
  (credentials Fernet ile şifrelenir)
- **Tetikleyiciler**
  - **Manuel** — UI'dan "Run" butonu
  - **Schedule (Cron)** — APScheduler ile her workflow için zamanlanmış
    çalıştırma (ör. `0 6 * * *` her sabah 06:00)
  - **Polling** — `transform.only_new` ile yeni kayıt diff snapshot'ı
- **Execution History** — Filtre + arama (status, trigger, workflow adı, hata
  metni); her step için input/output JSON, süre, hata
- **Output Formatları** — CSV, Excel (`.xlsx`), JSON, log
- **Template Substitution** — Node config'lerinde `{{node_id.field.path}}`
  syntax'ı ile parent çıktılarına erişim
- **Demo Workflow'lar** — `python -m scripts.seed_db` ile örnek workflow'ları
  kurar (OzelAlan1 güncelleme, sipariş raporu, ticket sınıflandırma)

## Mimari

| Katman | Teknoloji |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.x, SQLite, APScheduler, Pydantic v2 |
| LLM | Anthropic SDK (Claude), Google Gemini (opsiyonel), CLI fallback |
| SOAP | `TicimaxClient` (zeep wrapper, factory namespace fix uygulanmış) |
| Frontend | React 18 + TypeScript, Vite, React Flow (`@xyflow/react`), TanStack Query, Zustand, Tailwind |
| Storage | SQLite (`backend/agenticflow.db`), exports `backend/exports/` |

Ayrıntılı sistem mimarisi için [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
kullanım rehberi için [`docs/USAGE.md`](docs/USAGE.md).

## Kurulum

### Gereksinimler

- Python **3.11+**
- Node.js **20+**
- Anthropic API key (`ANTHROPIC_API_KEY`) **veya** Google Gemini API key
- Windows / Linux / macOS

### 1. Projeyi al

```bash
git clone <repo>
cd AgenticFlow
```

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # Linux/macOS
```

`.env` dosyasını düzenle:

```env
# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...

# Fernet master key (credentials için) — şu komutla üret:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
MASTER_KEY=base64-encoded-fernet-key
```

DB'yi kur ve sunucuyu başlat:

```bash
alembic upgrade head            # ilk kurulum
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend `http://127.0.0.1:5173` üzerinde açılır.

### 4. Demo workflow seed (opsiyonel)

UI'dan ilk Ticimax sitenizi ekledikten sonra demo workflow'ları oluşturabilirsiniz:

```bash
cd backend
python -m scripts.seed_db --site-id 1
```

Bu komut 3 demo workflow oluşturur (hepsi pasif, manuel aktivasyon gerekir):

| Workflow | Açıklama |
|---|---|
| **OzelAlan1 Güncelleme (Demo)** | Aktif ürünleri çeker, stok kodundan baz model kodunu türetir, log'a yazar. |
| **Günlük Sipariş Raporu (Demo)** | Cron `0 6 * * *` — her sabah son siparişleri Excel'e döker. |
| **Destek Ticket Sınıflandırma (Demo)** | Açık destek ticketlarını AI ile öncelik/konu sınıflandırır. |

`--force` flag'i ile mevcut demo'lar üzerine yazılır.

## Hızlı Başlatma (Windows)

```cmd
BASLAT.bat
```

Menüden seçim yapın:
- `1` Backend + Frontend ayrı pencerelerde başlat
- `2` Sadece backend (bu pencere)
- `3` Sadece frontend (bu pencere)
- `4` Tarayıcıda UI aç
- `5` Backend API docs aç (`/docs`)

### Masaüstü Kısayolu

`create_shortcut.bat` dosyasına çift tıklayın — masaüstüne **AgenticFlow**
kısayolu oluşturulur. Kısayola çift tıklayarak BASLAT menüsünü açabilirsiniz.

## Kullanım Akışı

1. **Site ekle** — UI > Sites > "+ Yeni Site". Domain (`demo.example.com`) ve
   üye kodu (Ticimax panelinden alacağınız 32 karakterlik token) gir;
   "Bağlantıyı test et" ile doğrula.
2. **Workflow oluştur** — UI > Workflows > "+ Yeni". Site seç, isim ver.
3. **Canvas'ta tasarla** — Sol panelden node sürükle, edge ile bağla, sağ
   panelden config gir. Veya:
4. **Chat'ten agent'a ürettir** — Sağ üst chat ikonu > doğal dilde yaz:
   > "Açık destek ticketlarından son 5 tanesini çek, Türkçe AI yanıtı üret,
   > admin (UyeID=1) olarak gönder."

   Claude workflow JSON'u üretir, canvas'a yerleşir, `Run` ile çalıştırırsın.
5. **Tetikleyici ekle** —
   - **Schedule:** `trigger.schedule` node'u + cron ifadesi (`*/5 * * * *`)
   - **Polling:** `trigger.polling` + interval saniye + sonrasına
     `transform.only_new` (yeni kayıt diff'i için)
   Workflow'u **Active** yap → APScheduler otomatik kayıt eder.
6. **Execution History** — Sol sidebar > Executions. Status/trigger/search
   filtreleriyle çalıştırmaları incele, step-by-step input/output görüntüle.

Detaylı node referansı: **`docs/USAGE.md`**.

## Önemli Yollar

| Yol | İçerik |
|---|---|
| `backend/app/nodes/` | Tüm node implementasyonları (kategori klasörleri) |
| `backend/app/engine/executor.py` | DAG runner (topological + template resolution) |
| `backend/app/services/scheduler_service.py` | APScheduler singleton (cron + polling) |
| `backend/app/services/ticimax_service.py` | Multi-site `TicimaxClient` cache |
| `backend/scripts/seed_db.py` | Demo workflow seeder |
| `backend/scripts/generate_node_catalog.py` | `server.py` AST parse → auto node generator |
| `backend/exports/` | CSV/Excel/JSON export çıktıları (gitignored) |
| `frontend/src/pages/WorkflowEditor.tsx` | Canvas + chat + config panel |
| `frontend/src/pages/ExecutionHistory.tsx` | Filtre + arama UI |

## Sorun Giderme

**`MASTER_KEY not set`** — `.env` dosyasında `MASTER_KEY` yok. `python -c
"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
ile bir tane üret.

**Scheduler job kaydolmuyor** — Workflow'da `trigger.schedule` node yok ya da
workflow `is_active=False`. UI'dan toggle et veya `PATCH /api/workflows/{id}`
ile `is_active: true` gönder. Aktif jobs için: `GET /api/workflows/scheduler/jobs`.

**Polling sürekli aynı kayıtları işliyor** — `trigger.polling` sonrasına
`transform.only_new` node ekleyin; bu node `polling_snapshots` tablosu
kullanarak (workflow_id, node_id) bazında son görülen ID'leri hatırlar.
İlk koşuda kayıtları **emit etmez** (thundering herd koruması); sürekli emit
istiyorsanız `emit_on_first_run: true` config'i ekleyin.

**Zeep `factory namespace not registered` hatası** — `TicimaxService` zaten
`fix_factories` uygular. Hata alıyorsanız muhtemelen WSDL erişim sorunu var;
`backend/app/utils/zeep_helpers.py` kontrol edin.

**Excel export "no list-of-dicts found"** — Parent node çıktısında uygun bir
liste bulunamadı. `source_field` config'ini ayarlayın (örn. `result.UrunList`,
`siparisler`, `urunler`).

## Faz Tamamlanma Durumu

- **Faz 1** — Core skelet (FastAPI + React Flow + 5 core node)
- **Faz 2** — Node katalogu (237 auto-generated + manuel optimizasyonlar)
- **Faz 3** — Async executor + AI nodes + Agent chat (Claude/Gemini)
- **Faz 4** — Schedule + Polling triggers, snapshot diff, execution filters
- **Faz 5** — Excel/JSON export, demo seed, BASLAT launcher, masaüstü kısayolu,
  USAGE rehberi

## Katkıda Bulunma

AgenticFlow açık kaynaktır. Katkılar memnuniyetle karşılanır — önce
[`CONTRIBUTING.md`](CONTRIBUTING.md) ve [`docs/prompt.md`](docs/prompt.md)
okunmalı. Bug / feature istekleri için GitHub Issues; güvenlik açıkları için
[`SECURITY.md`](SECURITY.md).

## Lisans

MIT — ayrıntı [`LICENSE`](LICENSE). Ticimax SOAP credentials ve LLM API
key'leri kişiseldir; asla commit etmeyin (`.env` gitignored).
