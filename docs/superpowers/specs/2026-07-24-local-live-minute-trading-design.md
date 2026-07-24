# Yerel Canlı Takip + Dakikalık Kararlar — Tasarım

Tarih: 2026-07-24

## Amaç

Proje artık kullanıcının kendi bilgisayarında çalışacak. Botlar saatte bir yerine
**dakikada bir** borsayı okuyup karar verecek. Kullanıcı canlı olarak **hangi botun
hangi kararı verdiğini** ve her botun **net kâr/zarar** durumunu tarayıcıdan
izleyebilecek.

## Mevcut Durum (özet)

- 5 bot (agent): `trend_follower`, `mean_reversion`, `momentum_breakout`,
  `grid_trader`, `ml_predictor`. Her biri $10.000 ile başlar.
- `SimulationEngine.run_tick(watchlist)` her sembol için kline çeker, her botun
  stratejisini çalıştırır, BUY/SELL uygular, stop-loss uygular.
- Scheduler (`BlockingScheduler`, tek worker): saat başı tick (`CronTrigger(minute=0)`)
  + gece yarısı günlük rapor.
- SQLite tabloları: `portfolios`, `trades`, `daily_reports`, `balance_snapshots`.
- Sadece BUY/SELL `trades` tablosuna loglanır. HOLD kararları kaydedilmez.
- Günlük rapor Pushbullet ile gönderilir.

## Kararlar

1. **Görüntüleme:** Yerel web paneli (tarayıcı), her ~5 sn otomatik yenilenir.
2. **Mum aralığı:** 1 dakikalık mumlar (`interval="1m"`).

## Tasarım

### 1. Dakikalık tick

- `Config`'e `KLINE_INTERVAL = "1m"` eklenir. Motor kline çekerken bu aralığı kullanır.
- `build_scheduler` içindeki `CronTrigger(minute=0)` yerine `IntervalTrigger(minutes=1)`
  kullanılır. `run_tick` her dakika çalışır.
- Tek-worker `ThreadPoolExecutor(max_workers=1)` korunur — tick ve günlük rapor asla
  eşzamanlı çalışmaz, paylaşılan SQLite bağlantısı ve portföy state'i güvende kalır.
- Günlük rapor + Pushbullet aynen kalır (`CronTrigger(hour=0, minute=0)`).
- Yük: 1m × 4 sembol = dakikada 4 istek. Binance limitleri için sorun yok.

### 2. Kararların yakalanması (HOLD dahil)

- Yeni `src/web/live_state.py`: thread-safe `LiveState` sınıfı (`threading.Lock`).
  Bot adı → şu alanları tutar:
  `{decision, symbol, pnl_abs, pnl_pct, cash, total_value, positions, updated_at}`.
  Ayrıca son güncelleme zaman damgası ve toplam portföy değeri.
- `SimulationEngine`, opsiyonel bir `live_state` alır. Her `_run_agent_tick` sonunda
  o botun güncel kaydını yazar. Bir sembolde BUY/SELL olursa `decision` o olur; hiç
  işlem olmazsa `decision = "HOLD"`, `symbol = None`.
- Net K/Z, o tick'te zaten çekilmiş kapanış fiyatları (`prices_by_symbol`) ile
  `Portfolio.total_pnl` üzerinden hesaplanır → ekstra API çağrısı yok.
- HOLD'lar DB'ye yazılmaz (günde on binlerce satır olurdu). Sadece bellekte tutulur.
  Gerçek işlemler (BUY/SELL) eskisi gibi `trades` tablosuna yazılır.
- `live_state` `None` ise motor eskisi gibi davranır (mevcut testler kırılmaz).

### 3. Web paneli

- `src/web/dashboard.py`: Flask uygulaması, arka planda ayrı bir daemon thread'de
  çalışır. `BlockingScheduler` ana thread'de kalır.
- Endpoint'ler:
  - `GET /` → tek sayfalık HTML; JS her ~5 sn'de `/api/state`'i çeker ve tabloyu günceller.
  - `GET /api/state` → `LiveState`'ten JSON (bot listesi + toplam K/Z + son güncelleme).
- Sayfa içeriği: tepede toplam portföy değeri ve toplam net K/Z; altında bot başına
  satır — bot adı, son karar (BUY=yeşil, SELL=kırmızı, HOLD=gri), sembol, net K/Z ($ ve %),
  nakit, açık pozisyonlar.
- Port `Config.WEB_PORT = 8000` (varsayılan). `localhost:8000`.

### 4. main.py bağlantısı

- `LiveState` oluşturulur → `SimulationEngine`'e verilir.
- Flask uygulaması `LiveState` ile başlatılır (daemon thread).
- Scheduler ana thread'de `start()` edilir. Ctrl+C ile temiz durur.

## Değişecek / Eklenecek Dosyalar

Değişecek:
- `src/config.py` — `KLINE_INTERVAL`, `WEB_PORT`.
- `src/scheduler/jobs.py` — `IntervalTrigger(minutes=1)`.
- `src/engine/simulation_engine.py` — opsiyonel `live_state`, tick sonu güncelleme.
- `main.py` — `LiveState` oluştur, web thread'ini başlat, motora bağla.
- `requirements.txt` — `flask`.

Yeni:
- `src/web/__init__.py`
- `src/web/live_state.py` — thread-safe canlı durum.
- `src/web/dashboard.py` — Flask app + HTML.

Dokunulmayacak:
- Strateji mantığı, portföy/işlem hesapları, DB şeması, günlük rapor/Pushbullet.
- Mevcut testlerin davranışı (motor `live_state=None` ile geriye uyumlu).

## Test Kriterleri

- `LiveState`: eşzamanlı güncelleme/okuma altında tutarlı snapshot döndürür;
  başlangıçta boş; güncelleme sonrası doğru alanlar.
- Motor: `live_state` verildiğinde her botun kararını (BUY/SELL/HOLD) ve net K/Z'sini
  doğru yazar; `live_state=None` iken eski davranış korunur.
- Scheduler: `IntervalTrigger(minutes=1)` ile tick job'u eklenir; günlük rapor cron'u kalır.
- Dashboard: `/api/state` `LiveState`'in snapshot'ını JSON olarak döner; `/` HTML döner.
- Mevcut tüm testler geçmeye devam eder.

## Kapsam Dışı (not)

- 1m mumlarla sinyaller sıklaşır; mevcut %25 pozisyon + %5 stop-loss ile botlar daha
  çok al-sat (churn/komisyon) yapabilir. Bu bir strateji ayarı konusudur, bu işin
  kapsamında değildir; ayrıca ele alınabilir.
