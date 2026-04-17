# output.telegram — Node Specification

> Status: Draft · Date: 2026-04-16

## 1. Problem

Workflow sonuçları şu an sadece `output.log`'a veya `output.excel_export`'a
gidebiliyor. Kullanıcı sonuçları **anında** görmek istiyor — telefona
bildirim, ekibe mesaj.

Ticimax kullanıcılarının en yaygın iletişim kanalı: **Telegram**.

## 2. Solution

Yeni `output.telegram` node'u. Telegram Bot API'ye HTTP POST yapar.
Sıfır ek bağımlılık — `httpx` (mevcut runtime dep) yeterli.

## 3. User Stories

### 3.1 Sabah raporu Telegram'a
```
trigger.schedule(08:00) → siparis.select → aggregate → ai.prompt
  → output.telegram(chat_id="-100123456", message="{{ai_ozet.text}}")
```

### 3.2 Stok kritik uyarı
```
trigger.schedule(09:00) → urun.select → filter(stok<5) → aggregate
  → output.telegram("⚠️ {{sayac.result.count}} ürün kritik stokta!")
```

### 3.3 Yeni sipariş bildirimi
```
trigger.polling(300s) → siparis.select → only_new
  → output.telegram("🛒 Yeni sipariş: {{only_new.new_items.0.AdiSoyadi}}")
```

## 4. Architecture

```
output.telegram node
  │
  ├─ Config: bot_token (Settings'ten veya env), chat_id
  ├─ Input: upstream node çıktıları (template ile mesaj oluşturulur)
  │
  └─ POST https://api.telegram.org/bot{token}/sendMessage
       body: { chat_id, text, parse_mode: "HTML" }
```

### Bot Token yönetimi

İki seviye:
1. **Global**: Settings > Telegram Bot Token (tüm workflow'lar için)
2. **Per-node override**: node config'de `bot_token` alanı (opsiyonel)

Global token `app_settings` tablosunda Fernet-encrypted saklanır.
Per-node token, workflow graph_json'da plaintext durur — bu nedenle
global tercih edilmeli.

### Chat ID

Her node'un kendi `chat_id`'si var. Kullanıcı:
- Kişisel chat: BotFather'dan aldığı bot'a /start yapar, chat_id'yi alır
- Grup: botu gruba ekler, grup chat_id'sini alır
- Kanal: botu kanal admin'i yapar, kanal chat_id'sini kullanır

## 5. Config Schema

```json
{
  "type": "object",
  "properties": {
    "chat_id": {
      "type": "string",
      "title": "Chat ID",
      "description": "Telegram chat/group/channel ID. Grup için '-' ile başlar.",
      "default": ""
    },
    "message": {
      "type": "string",
      "title": "Mesaj",
      "description": "Gönderilecek metin. Template destekler: {{node_id.field}}",
      "default": ""
    },
    "parse_mode": {
      "type": "string",
      "title": "Format",
      "default": "HTML",
      "enum": ["HTML", "Markdown", ""]
    },
    "bot_token": {
      "type": "string",
      "title": "Bot Token (opsiyonel)",
      "description": "Boş = Settings'teki global token kullanılır.",
      "default": ""
    },
    "disable_notification": {
      "type": "boolean",
      "title": "Sessiz Gönder",
      "default": false
    }
  },
  "required": ["chat_id", "message"]
}
```

## 6. Output Schema

```json
{
  "type": "object",
  "properties": {
    "ok": { "type": "boolean" },
    "message_id": { "type": "integer" },
    "chat_id": { "type": "string" },
    "text_length": { "type": "integer" }
  }
}
```

## 7. Behaviour Rules

1. `message` field'ı template resolve edilir SONRA gönderilir.
2. Telegram mesaj limiti: 4096 karakter. Aşarsa truncate + "..." notu.
3. `bot_token` boşsa → `get_llm_setting("TELEGRAM_BOT_TOKEN")` ile
   global token alınır.
4. Her ikisi de boşsa → `NodeError("Telegram bot token ayarlanmamış")`.
5. HTTP hata (401, 403, 400) → `NodeError` ile açık hata mesajı.
6. Timeout: 10 saniye.
7. Başarılı gönderimde `message_id` döner — downstream node'lar
   referans alabilir.

## 8. Dependencies

- `httpx` — mevcut runtime dep (async HTTP client).
- Yeni bağımlılık: **YOK**.

## 9. Settings UI

Settings sayfasına yeni alan:
- **Telegram Bot Token**: encrypted, password input
- **Test**: "Test Mesajı Gönder" butonu (isteğe bağlı, v2)

## 10. Setup Flow (kullanıcı için)

1. Telegram'da @BotFather'a git
2. `/newbot` → bot adı ver → token al (`123456:ABC-DEF...`)
3. AgenticFlow Settings → Telegram Bot Token → yapıştır
4. Bot'a Telegram'dan /start yaz (veya gruba ekle)
5. Chat ID'yi öğren:
   - `https://api.telegram.org/bot{TOKEN}/getUpdates` → chat.id
   - Veya @userinfobot kullan
6. Workflow'da `output.telegram` node'u ekle → chat_id + mesaj template

## 11. Test Plan

| Test | Type | What |
|---|---|---|
| Mesaj gönderimi (mock HTTP) | unit | httpx mock → 200 OK |
| Template resolve + truncate | unit | 5000 char mesaj → 4096'ya kesilir |
| Token yoksa NodeError | unit | |
| Chat ID yoksa NodeError | unit | |
| HTTP 401 → anlaşılır hata | unit | "Bot token geçersiz" |
| HTTP 403 → anlaşılır hata | unit | "Bot bu chat'e erişemiyor" |
| Contract test | contract | Node registry'de var |

## 12. Implementation Plan

1. `backend/app/nodes/output/telegram.py` — node implementasyonu (~80 satır)
2. `backend/app/nodes/__init__.py` — registry'ye ekle
3. `backend/tests/unit/nodes/test_telegram_node.py` — 7+ test
4. Settings'e `TELEGRAM_BOT_TOKEN` alanı (config.py + settings_service)
5. `docs/nodes/OUTPUT_TELEGRAM_SPEC.md` — bu dosya (zaten yazıldı)

Toplam: ~150 satır kod + ~100 satır test. Sıfır yeni bağımlılık.
