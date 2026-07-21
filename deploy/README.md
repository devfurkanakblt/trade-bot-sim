# Deployment - Oracle Cloud Free Tier

## Prerequisites

- An Oracle Cloud Free Tier "Always Free" VM instance (Ubuntu), reachable via SSH
- A Pushbullet account with an access token (Settings -> Account -> Create Access Token)

## Steps

1. Copy this repository to the VM (e.g. `git clone` or `scp -r`).
2. SSH into the VM and run:

   ```bash
   cd trade-bot-sim
   ./deploy/setup_vm.sh
   ```

3. Edit `/opt/trade-bot-sim/.env` and set `PUSHBULLET_TOKEN` to your real token.
4. Start the service:

   ```bash
   sudo systemctl start trade-bot-sim
   ```

5. Verify it's running:

   ```bash
   sudo systemctl status trade-bot-sim
   sudo journalctl -u trade-bot-sim -f
   ```

## What to expect

- The bot polls Binance and evaluates all 5 agents once per hour.
- Every day at 00:00 Europe/Istanbul time, a summary is pushed to your Pushbullet-connected devices.
- If the VM reboots or the process crashes, systemd (`Restart=always`) brings it back up automatically; portfolio state is restored from `/opt/trade-bot-sim/trade_bot_sim.db`.

## Updating the deployed code

```bash
cd trade-bot-sim
git pull
sudo rsync -a --exclude venv --exclude .git --exclude "*.db" ./ /opt/trade-bot-sim/
sudo systemctl restart trade-bot-sim
```
