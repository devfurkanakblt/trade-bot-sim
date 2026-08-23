# 24/7 VM Deployment

The simulator is designed to run as a long-lived Ubuntu service with a local,
persistent SQLite database. Google Compute Engine is the primary free-tier
target; the same setup script also works on an Oracle Ubuntu VM.

## Google Compute Engine free-tier VM

Google's free Compute Engine allowance applies to one non-preemptible
`e2-micro` VM in `us-west1`, `us-central1`, or `us-east1`, plus up to 30 GB of
standard persistent disk. A billing account is required, and usage outside the
free-tier limits can be charged.

1. Create or select a Google Cloud project and attach a billing account.
2. Open **Compute Engine > VM instances > Create instance**.
3. Use these settings:
   - Region: `us-central1` (or `us-west1` / `us-east1`)
   - Machine family: `E2`
   - Machine type: `e2-micro`
   - Provisioning model: Standard (not Spot)
   - Boot image: Ubuntu 24.04 LTS
   - Boot disk type: Standard persistent disk (`pd-standard`)
   - Boot disk size: 20 GB
   - Firewall: do not enable HTTP or HTTPS; the dashboard remains local-only
4. Create the VM and use the Google Cloud **SSH** button.
5. Clone the repository and install the service:

   ```bash
   git clone https://github.com/devfurkanakblt/trade-bot-sim.git
   cd trade-bot-sim
   chmod +x deploy/setup_vm.sh
   ./deploy/setup_vm.sh
   ```

6. Configure the VM-only environment file:

   ```bash
   sudo nano /opt/trade-bot-sim/.env
   ```

   Keep `DB_PATH=trade_bot_sim.db`, set the real `PUSHBULLET_TOKEN`, and leave
   `BACKUP_DIR=backups` / `BACKUP_KEEP=14` enabled. Then start the bot:

   ```bash
   sudo systemctl start trade-bot-sim
   sudo systemctl status trade-bot-sim --no-pager
   sudo journalctl -u trade-bot-sim -f
   ```

## Runtime behavior

- Eight paper-trading agents start from 10,000 USDT each on a fresh database.
- The highest-volume 50 eligible USDT markets are refreshed every 15 minutes.
- Open-position symbols remain monitored even after leaving the top-50 list.
- Only completed one-minute candles are evaluated, once per minute at second 5.
- Full equity, cash, and open-position counts are recorded hourly.
- A daily report is generated at 00:00 Europe/Istanbul.
- `systemd` restarts the process after a crash or VM reboot.
- SQLite is backed up daily with an integrity check; the latest 14 backups are retained.

## Verify service and backups

```bash
sudo systemctl status trade-bot-sim --no-pager
sudo systemctl status trade-bot-sim-backup.timer --no-pager
sudo systemctl list-timers trade-bot-sim-backup.timer
cd /opt/trade-bot-sim
sudo -u tradebot ./venv/bin/python -m src.storage.backup
ls -lh /opt/trade-bot-sim/backups
```

## View the dashboard safely

The Flask dashboard binds to `127.0.0.1` and is not exposed to the internet.
From the Google Cloud SSH terminal, verify it locally with:

```bash
curl http://127.0.0.1:8000/health
```

For browser access, create an SSH tunnel from your own computer instead of
opening port 8000 publicly:

```bash
gcloud compute ssh VM_NAME --zone=VM_ZONE -- -L 8000:127.0.0.1:8000
```

Then open `http://127.0.0.1:8000` locally.

## Start a clean cloud experiment

Do not copy the intermittently-run local `trade_bot_sim.db` to the VM. The
installer deliberately excludes `*.db`, so the cloud process creates a fresh
database and all agents start at the same time with equal balances. Archive the
local DB separately if it must be retained.

## Updating the deployed code

After pushing changes to GitHub:

```bash
cd ~/trade-bot-sim
git pull
sudo rsync -a \
  --exclude venv \
  --exclude .git \
  --exclude .env \
  --exclude "*.db" \
  --exclude backups \
  ./ /opt/trade-bot-sim/
sudo systemctl restart trade-bot-sim
sudo systemctl status trade-bot-sim --no-pager
```

The update command preserves the VM's `.env`, live database, and backups.
