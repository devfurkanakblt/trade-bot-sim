#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/trade-bot-sim

sudo useradd --system --create-home --shell /usr/sbin/nologin tradebot || true
sudo mkdir -p "$APP_DIR"

sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip rsync

sudo rsync -a \
  --exclude venv \
  --exclude .git \
  --exclude .env \
  --exclude "*.db" \
  --exclude backups \
  --exclude .pytest_cache \
  --exclude .pytest_tmp \
  ./ "$APP_DIR"/

cd "$APP_DIR"
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt

if [ ! -f "$APP_DIR/.env" ]; then
  sudo cp .env.example "$APP_DIR/.env"
  echo "Created $APP_DIR/.env from template - edit it and set PUSHBULLET_TOKEN before starting."
fi
sudo chmod 600 "$APP_DIR/.env"

sudo cp deploy/trade-bot-sim.service /etc/systemd/system/trade-bot-sim.service
sudo cp deploy/trade-bot-sim-backup.service /etc/systemd/system/trade-bot-sim-backup.service
sudo cp deploy/trade-bot-sim-backup.timer /etc/systemd/system/trade-bot-sim-backup.timer
sudo chown -R tradebot:tradebot "$APP_DIR"

sudo systemctl daemon-reload
sudo systemctl enable trade-bot-sim
sudo systemctl enable --now trade-bot-sim-backup.timer

echo "Setup complete."
echo "1. Edit $APP_DIR/.env and set PUSHBULLET_TOKEN"
echo "2. Start with: sudo systemctl start trade-bot-sim"
echo "3. Check status with: sudo systemctl status trade-bot-sim"
echo "4. Tail logs with: sudo journalctl -u trade-bot-sim -f"
echo "5. Check backups with: sudo systemctl list-timers trade-bot-sim-backup.timer"
