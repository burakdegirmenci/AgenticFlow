# AgenticFlow Telegram Bot — Specification

> Status: Draft · Date: 2026-04-17

## 1. Vision

Telegram Bot, AgenticFlow'un **ikinci arayüzü**. Web UI masaüstü için,
Telegram Bot cep telefonu ve anlık operasyon için. Aynı backend API'ye
konuşurlar — bot yeni business logic eklemez, mevcut API'nin üzerine
ince bir adapter katmanıdır.

```
┌──────────────┐     ┌──────────────┐
│   Web UI     │     │ Telegram Bot │
│ (React SPA)  │     │ (python-telegram-bot)
└──────┬───────┘     └──────┬───────┘
       │ REST (JSON)        │ REST (JSON)
       └────────┬───────────┘
                ▼
       ┌────────────────┐
       │  FastAPI API   │
       │  (tek backend) │
       └────────────────┘
```

**Prensip:** Bot, UI'ın yapabildiği her şeyi yapabilmeli —
workflow listele, çalıştır, sonuç al, hata bildir. Ama yeni endpoint
eklememeli; mevcut `/api/*` endpoint'lerini kullanmalı.

## 2. User Stories

### 2.1 Sabah telefonu açtığında
> "Dün gece schedule'la çalışan workflow'lar nasıl bitti?"

```
Kullanıcı: /history
Bot:       Son 5 execution:
           ✅ #30 Günlük Sipariş Raporu (08:00, 12s)
           ✅ #31 Stok Kritik Uyarı (09:00, 20s)
           ❌ #32 OzelAlan1 Güncelle (10:00) — timeout
```

### 2.2 Acil workflow tetikleme
> "Depodan yeni stok listesi geldi, hemen çalıştır"

```
Kullanıcı: /run 2
Bot:       ▶ Günlük Sipariş Raporu başlatıldı (exec #33)
           ⏳ Çalışıyor...
Bot:       ✅ #33 tamamlandı (14s)
           50 sipariş, 287.954 TL ciro
           📎 Excel rapor: [indir]
```

### 2.3 Hata anında bildirim
> (Kullanıcı bir şey yapmaz — bot kendisi bildirir)

```
Bot:       🚨 Workflow HATA
           Stok Kritik Uyarı (#34)
           Hata: urun servisi timeout
           Süre: 45s
           [Detay göster] [Tekrar çalıştır]
```

### 2.4 Execution detayı
> "Son çalışan sipariş raporunun sonucunu göster"

```
Kullanıcı: /status 33
Bot:       Execution #33 — ✅ SUCCESS
           Workflow: Günlük Sipariş Raporu
           Trigger: SCHEDULE (08:00)
           Süre: 14s

           Adımlar:
           ✅ trigger        0ms
           ✅ siparisler  1.2s
           ✅ ozet_map      2ms
           ✅ ai_ozet    10.8s
           ✅ excel        0.4s
```

### 2.5 Workflow listesi
```
Kullanıcı: /workflows
Bot:       📋 Workflow'lar:
           1. Ürün Listele - Test (pasif)
           2. Günlük Sipariş Raporu ⏰ 08:00
           3. Destek Ticket Sınıflandırma (pasif)
           4. Stok Kritik Uyarı ⏰ 09:00
           5. Excel Stok Okuma Test (pasif)

           /run <numara> ile çalıştır
```

### 2.6 Abone ol / çık
```
Kullanıcı: /subscribe
Bot:       🔔 Tüm workflow hatalarına abone oldun.
           Her hata anında bildirim alacaksın.

Kullanıcı: /unsubscribe
Bot:       🔕 Abonelik iptal edildi.
```

## 3. Architecture

### 3.1 Component: TelegramBotService

```
app/services/telegram_bot_service.py

class TelegramBotService:
    """Runs as part of FastAPI lifespan, like SchedulerService."""

    def start() → long-polling loop başlat (asyncio task)
    def stop()  → loop durdur
    def send_message(chat_id, text) → proactive bildirim
```

- FastAPI lifespan'de başlar/durur (SchedulerService gibi)
- `TELEGRAM_BOT_TOKEN` env'den veya Settings'ten okunur
- Token yoksa service başlamaz (opsiyonel, mevcut davranışı bozmaz)

### 3.2 Message Handling: Command Router

```
/workflows              → GET /api/workflows → format + reply
/run <workflow_id>      → POST /api/workflows/:id/run → poll → reply
/status <execution_id>  → GET /api/executions/:id → format + reply
/history [n]            → GET /api/executions?limit=n → format + reply
/subscribe              → DB'ye chat_id kaydet
/unsubscribe            → DB'den chat_id sil
/help                   → komut listesi
```

Her komut **mevcut API'yi çağırır** — yeni business logic yok.

### 3.3 Proactive Notifications

Executor zaten `execution_finished` log kaydı atıyor. Buna bir hook
eklenir:

```python
# executor.py — execution bittiğinde:
if execution.status == ExecutionStatus.ERROR:
    telegram_bot_service.notify_error(execution)
elif execution.status == ExecutionStatus.SUCCESS:
    telegram_bot_service.notify_success(execution)  # sadece subscribers'a
```

Notification logic:
- **ERROR**: tüm subscribers'a anında bildir
- **SUCCESS**: sadece o workflow'a subscribe olan chat'lere
- **Throttle**: aynı workflow için dakikada max 1 bildirim (flood koruması)

### 3.4 Data Model

Yeni tablo: `telegram_subscriptions`

```sql
CREATE TABLE telegram_subscriptions (
    id INTEGER PRIMARY KEY,
    chat_id TEXT NOT NULL,
    workflow_id INTEGER NULL,  -- NULL = tüm workflow'lara abone
    notify_on TEXT DEFAULT 'error',  -- 'error' | 'all' | 'success'
    created_at DATETIME
);
```

### 3.5 Security

- `TELEGRAM_ALLOWED_CHAT_IDS` env: virgüllü chat ID listesi.
  Sadece bu chat'lerden gelen komutlar kabul edilir.
  Boş = herkes (sadece token bilen bot'a ulaşabilir, ama yine de
  single-tenant olduğu için kabul edilebilir risk).
- Bot token Settings'te Fernet-encrypted saklanır.
- Workflow çalıştırma (`/run`) yetkili chat'lerle sınırlı.

## 4. Dependency

```
python-telegram-bot>=21.0
```

Tek yeni bağımlılık. Async-native, well-maintained, 10K+ GitHub stars.
Alternatif: raw httpx ile Bot API çağrıları (sıfır dep ama daha fazla
boilerplate). Ersin zero-dep'i sever ama bot framework'ü bu kadar
olgun olunca tekerleği yeniden icat etmek anlamsız.

## 5. Config

```python
# app/config.py
TELEGRAM_BOT_TOKEN: str = ""          # BotFather'dan
TELEGRAM_ALLOWED_CHAT_IDS: str = ""   # virgüllü: "123456,789012"
TELEGRAM_NOTIFY_ON_ERROR: bool = True  # default: hata bildir
```

## 6. Implementation Plan

### Phase 1: Core Bot (tek commit)
1. `app/services/telegram_bot_service.py` — service + command handlers
2. `app/models/telegram_subscription.py` — subscription model
3. `app/config.py` — yeni settings
4. `app/main.py` — lifespan'e ekle
5. Tests: 8+ unit (command parse, format, subscribe/unsubscribe)

### Phase 2: Executor Hook (tek commit)
1. `app/engine/executor.py` — execution bittiğinde notify hook
2. Throttle logic
3. Tests: notify_error, notify_success, throttle

### Phase 3: Polish (ayrı commit'ler)
1. Inline keyboard butonları ([Detay] [Tekrar Çalıştır])
2. `/run` sonrası execution progress polling (⏳ → ✅)
3. Excel/CSV attachment gönderme (export dosyaları)
4. Settings UI'da Telegram config paneli

## 7. File Structure

```
backend/
├── app/
│   ├── services/
│   │   └── telegram_bot_service.py   # NEW — bot lifecycle + handlers
│   ├── models/
│   │   └── telegram_subscription.py  # NEW — subscription table
│   └── main.py                       # MODIFIED — lifespan hook
├── tests/
│   └── unit/services/
│       └── test_telegram_bot.py      # NEW
└── docs/
    └── TELEGRAM_BOT_SPEC.md          # THIS FILE
```

## 8. Message Formatting

```
✅ SUCCESS format:
  ✅ Execution #{id} — {workflow_name}
  Trigger: {trigger_type} · Süre: {duration}
  {step_count} adım tamamlandı

  [Özet: count=50, ciro=287.954 TL gibi key metrics — AI node varsa onun text'i]

❌ ERROR format:
  🚨 Execution #{id} HATA — {workflow_name}
  Hata: {error_message[:200]}
  Adım: {failed_step_node_type}
  Süre: {duration}

  /status {id} ile detay gör
  /run {workflow_id} ile tekrar çalıştır

📋 Workflow list format:
  📋 Workflow'lar:
  {emoji} {id}. {name} {schedule_info}

  /run <id> ile çalıştır

📊 History format:
  📊 Son {n} execution:
  {status_emoji} #{id} {workflow_name} ({time}, {duration})
```

## 9. Non-Goals (v1'de yok)

- Telegram'dan workflow OLUŞTURMA (canvas gerektirir)
- Telegram'dan node config DÜZENLEME
- Dosya gönderip workflow tetikleme (v2 — Excel upload via Telegram)
- Multi-user yetkilendirme (single-tenant, tek operatör)
- Webhook modu (self-hosted = long-polling daha basit)
