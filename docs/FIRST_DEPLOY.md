# AgenticFlow — First Deploy & 1-Week Dogfood Plan

> Sprint 8 öncesi gerçek-dünya signal toplamak için.
> v0.5.0 release tag'i hazır, repo public, image build edilebilir.
> Bu doc 1 hafta boyunca AgenticFlow'u **kendi e-ticaret işlerin için**
> çalıştırma rehberi.

---

## 0. Bugün — Lokal smoke test (15 dakika)

Push'ladığın Dockerfile + compose'un gerçekten ayağa kalktığını doğrula.

```bash
cd ~/Desktop/AgenticFlow

# 1. .env hazırla
cp backend/.env.example .env
# Düzenle:
#  - MASTER_KEY: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#  - ANTHROPIC_API_KEY: kendi key'in
#  - (opsiyonel) API_KEY: bir shared secret koy

# 2. Docker Desktop'ı aç + ping et
docker info | grep "Server Version"

# 3. Build et
docker compose build --pull

# 4. Başlat
docker compose up -d

# 5. Doğrula
curl -sf http://localhost:8080/health     # frontend nginx
curl -sf http://localhost:8080/ready      # backend through proxy
curl -sf http://localhost:8080/metrics | head

# 6. UI
# Tarayıcıdan: http://localhost:8080
```

İlk build 5-8 dk sürebilir (Python wheel'ler + node_modules). Kaydet:
- Backend imajı boyutu: `docker images agenticflow-backend:local`
- Frontend imajı boyutu: `docker images agenticflow-frontend:local`
- İlk health check'e ulaşma süresi
- Konsol log'larında JSON parse hatası var mı

**Karşılaşacağın olası sorunlar (önceden tahmin):**
- `MASTER_KEY` boş bırakıldıysa backend instant exit eder — log'da net mesaj.
- Frontend'in `/api`'ye erişmemesi durumu → nginx proxy doğru `backend:8000`'i resolve etmiyor demektir; `docker compose logs frontend` bak.
- Hetzner / VPS'e taşıdığında `CORS_ORIGINS=http://localhost:8080` artık geçersiz — public domain'le güncelle.

---

## 1. Bu hafta — VPS deploy (1-2 saat)

### Önerilen: Hetzner CX22 (~€4/ay)
- 2 vCPU, 4 GB RAM — AgenticFlow için fazla bile.
- Ubuntu 24.04 + Docker.

```bash
# Yerinde
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# Repo + .env
git clone https://github.com/burakdegirmenci/AgenticFlow.git
cd AgenticFlow
cp backend/.env.example .env
# Doldur — özellikle MASTER_KEY ve LLM key'i.

# Reverse proxy: en hızlısı Caddy (otomatik TLS)
sudo apt install -y caddy
echo 'flow.<senin-domain>.com {
    reverse_proxy localhost:8080
}' | sudo tee /etc/caddy/Caddyfile
sudo systemctl reload caddy

# Stack
docker compose up -d
docker compose logs -f --tail=50
```

DNS'i `flow.<senin-domain>.com` → Hetzner IP yap. Caddy 30 saniye içinde Let's Encrypt cert'i alır.

**Güvenlik kapısı:**
- `.env`'de `API_KEY=$(openssl rand -hex 32)` ekle
- Tarayıcıdan UI'a `?api_key=...` veya HTTP header gerekir
- VEYA Caddy'de basic auth: `basicauth { burak <bcrypt-hash> }`

---

## 2. Hafta boyu — 3 gerçek workflow

### Workflow 1: **Sabah Raporu** (en yüksek değer)
Her sabah 08:00 → Telegram'a tek mesaj:
- Dün vs bugün: ciro, sipariş sayısı, dönüşüm
- 🚨 anomali: ödeme hata oranı, X ürün stoksuz, Y rakibi indirimde
- Yeni Trendyol/HB yorumları (top 3 negatif)

**Kullanılacak node'lar** (hepsi mevcut):
- `trigger.schedule` cron `0 8 * * *`
- `ticimax.siparis.select` (son 24 saat)
- `transform.aggregate` (count, sum)
- `ai.prompt` (Claude/Gemini ile özet)
- `output.log` veya HTTP webhook → Telegram

### Workflow 2: **Yorum Toplayıcı**
Saatte bir → Trendyol/HB yeni yorumları çek + Gemini ile sentiment + 3+ negatif olanları kendine SMS at.

- `trigger.polling` (3600 sn)
- `ticimax.<yorum-endpoint>` (ne varsa hand-write gerekirse Sprint 8 işi)
- `transform.only_new` (snapshot diff)
- `ai.classify` (sentiment)
- `transform.filter` (negative only)
- `output.log` → SMS provider

### Workflow 3: **OzelAlan1 Düzenleyici** (zaten demo'da var)
Activate et — gerçek production'da 1 hafta çalıştır. CSV/Excel export'la beraber dry-run'dan canlıya geçişi izle.

---

## 3. Hafta sonu — Sprint 8 backlog'u yaz

Şu listenin **dogfood'tan çıkanını** yaz:

```markdown
# Sprint 8 — Dogfood Findings

## Kullanırken patlayan 3 şey
1. ...
2. ...
3. ...

## Olmayan + acilen lazım olan node'lar
- [ ] ticimax.<X>
- [ ] output.telegram
- [ ] ...

## UI'da en sinirlendiğim 3 şey
1. ...
2. ...

## Performance gözlemi
- Polling 60 sn iken request_count saatte: ...
- /metrics içindeki executions_total: ...
- Disk doluluk artış hızı (logs/, exports/): ... GB/gün

## Doc eksikliği
- ...
```

Bu **Sprint 8'in gerçek scope'u**. Bugün yazdığım deferred listesi (LLM provider testleri vs.) teorik. Dogfood listesi pratik.

---

## 4. Operasyonel notlar (1 hafta canlıyken)

### Günlük (10 dakika)
```bash
# Backup
docker compose exec -T backend \
  sqlite3 /data/agenticflow.db ".backup /data/backup_$(date +%F).sqlite"

# Disk + log doluluk kontrol
docker compose exec backend du -sh /var/log/agenticflow /app/exports

# Yeni execution + scheduler durumu
curl -s http://localhost:8080/metrics | grep -E "(executions_total|scheduler)"
```

### Haftalık
- `docker compose pull && docker compose up -d` — Docker base image'ları taze
- Logs/, exports/ rotation (cron'da)
- Sentry'ye baktın mı? (set ettiysen)
- 100+ execution bittiyse: SQLite size ne kadar arttı?

### Sorun çıkarsa
1. `docker compose logs -f --tail=100 backend` — JSON satırları gerçek hata söyler
2. `/ready` 503 dönerse: backend up değil veya DB lock
3. `/metrics` `agenticflow_execution_steps_total{status="ERROR"}` artıyor mu?
4. Acil rollback: `git checkout v0.5.0 && docker compose up -d`

---

## 5. Hafta sonu deliverable'ları

Hafta bitince elde olacak:

- [ ] Public repo'da en az **1 ⭐** (sen kendin starlasaydın bile sayar)
- [ ] **3 production workflow** çalışıyor
- [ ] **Sprint 8 dogfood backlog'u** yazılı (yukarıdaki şablon)
- [ ] İlk gerçek **kullanıcı geri bildirimi** (kendin de olur, ekipten biri olsa daha iyi)
- [ ] **Bu hafta açtığın 3-5 issue** (gerçek dogfood'tan çıkan, "iyi olur" değil acil olanlar)

---

## Hatırlatma

Disiplin tamam. Şimdi geri bildirim toplama vakti.
- Polish > Yayınlanmamış polish her zaman.
- Sprint 8 = "dogfood-driven Sprint", "checklist-driven" değil.
- Repo public olarak duracak — issue / star / PR gelirse beklenti var.
