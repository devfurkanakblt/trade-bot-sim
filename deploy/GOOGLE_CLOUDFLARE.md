# Zero-cost Google Compute + Cloudflare deployment

This deployment keeps the Compute Engine VM IPv6-only. Cloudflare Worker
proxies the two IPv4-only APIs used by the application. Do not start the bot
until the Worker test succeeds.

## 1. Create the Cloudflare Worker

1. In Cloudflare, open **Workers & Pages > Create application**.
2. Either import this GitHub repository or create a Worker named
   `trade-bot-proxy`. Git imports use the root `wrangler.json`, which points to
   `deploy/cloudflare-worker.js`; no static-assets directory is required.
3. For a manually created Worker, replace the editor contents with
   `deploy/cloudflare-worker.js` and deploy.
4. Under **Settings > Variables and Secrets**, add a secret named
   `PROXY_TOKEN`. Generate its value locally with:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

5. Test the deployed Worker:

   ```bash
   curl -H "X-Proxy-Token: YOUR_TOKEN" \
     "https://YOUR_WORKER.workers.dev/binance/api/v3/ticker/price?symbol=BTCUSDT"
   ```

The request must return a BTC price. The same request without the header must
return HTTP 401.

## 2. Create the IPv6-only Google network

Run in Google Cloud Shell, replacing `PROJECT_ID`:

```bash
gcloud config set project PROJECT_ID
gcloud compute networks create trade-bot-net --subnet-mode=custom
gcloud compute networks subnets create trade-bot-v6 \
  --network=trade-bot-net \
  --stack-type=IPV6_ONLY \
  --ipv6-access-type=EXTERNAL \
  --region=us-central1
gcloud compute firewall-rules create allow-iap-ssh-v6 \
  --network=trade-bot-net \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp:22 \
  --source-ranges=2600:2d00:1:7::/64 \
  --target-tags=iap-ssh
```

## 3. Create the free-tier VM

```bash
gcloud compute instances create trade-bot-sim \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --network-interface=subnet=trade-bot-v6,stack-type=IPV6_ONLY \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-type=pd-standard \
  --boot-disk-size=20GB \
  --tags=iap-ssh
```

Connect through IAP:

```bash
gcloud compute ssh trade-bot-sim \
  --zone=us-central1-a \
  --tunnel-through-iap
```

## 4. Transfer the repository

The VM has no IPv4 route to GitHub. Clone in Cloud Shell, then copy through IAP:

```bash
git clone https://github.com/devfurkanakblt/trade-bot-sim.git
gcloud compute scp --recurse trade-bot-sim trade-bot-sim:~/ \
  --zone=us-central1-a \
  --tunnel-through-iap
gcloud compute ssh trade-bot-sim \
  --zone=us-central1-a \
  --tunnel-through-iap
```

On the VM:

```bash
cd ~/trade-bot-sim
chmod +x deploy/setup_vm.sh
./deploy/setup_vm.sh
sudo nano /opt/trade-bot-sim/.env
```

Use these cloud-specific values, plus the real Pushbullet token:

```dotenv
PUSHBULLET_TOKEN=YOUR_PUSHBULLET_TOKEN
MARKET_DATA_BASE_URL=https://YOUR_WORKER.workers.dev/binance
PUSHBULLET_API_URL=https://YOUR_WORKER.workers.dev/pushbullet/v2/pushes
OUTBOUND_PROXY_TOKEN=YOUR_PROXY_TOKEN
DB_PATH=trade_bot_sim.db
KLINE_INTERVAL=1m
MARKET_UNIVERSE_SIZE=35
MARKET_UNIVERSE_REFRESH_SECONDS=900
BACKUP_DIR=backups
BACKUP_KEEP=14
```

## 5. Verify and start

On the VM:

```bash
set -a
source /opt/trade-bot-sim/.env
set +a
curl -6 -H "X-Proxy-Token: $OUTBOUND_PROXY_TOKEN" \
  "$MARKET_DATA_BASE_URL/api/v3/ticker/price?symbol=BTCUSDT"
sudo systemctl start trade-bot-sim
sudo systemctl status trade-bot-sim --no-pager
sudo journalctl -u trade-bot-sim -f
```

The proxy request must succeed before starting the service. Verify the local
dashboard and backup after startup:

```bash
curl http://127.0.0.1:8000/health
cd /opt/trade-bot-sim
sudo -u tradebot ./venv/bin/python -m src.storage.backup
ls -lh backups
```

## 6. Open the dashboard through IAP

From the local computer:

```bash
gcloud compute ssh trade-bot-sim \
  --zone=us-central1-a \
  --tunnel-through-iap \
  -- -NL 8000:localhost:8000
```

Open `http://127.0.0.1:8000`. Do not create a public firewall rule for port
8000.
