## Flipkart Price Tracker Bot

Run a Telegram bot that tracks Flipkart product prices using headless Chromium + Selenium and sends drop alerts.

### Requirements
- Python 3.12 or Docker
- Telegram bot token set in env var `TELEGRAM_TOKEN`

### Quick start (Docker recommended)
```bash
docker build -t flipkart-bot .
docker run -d --name flipkart-bot \
  -e TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN \
  --shm-size=2g \
  --restart unless-stopped \
  flipkart-bot

docker logs -f flipkart-bot | cat
```

### Run locally (Linux)
```bash
sudo apt-get update
sudo apt-get install -y chromium chromium-driver fonts-liberation
python -m pip install -U pip
python -m pip install -r <(printf "python-telegram-bot>=22.4\nselenium>=4.35.0\nrequests>=2.32.3\npython-dotenv>=1.0.1\nbeautifulsoup4>=4.12.3\nschedule>=1.2.2\n")
export TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
python flipkart_price_alert.py
```

### Notes
- The background checker now sleeps for 1 hour between runs.
- Chromium path can be configured via `CHROME_BIN` (defaults to `/usr/bin/chromium`).
- Ensure outbound HTTPS is allowed so Telegram API works.

### Troubleshooting
- If Selenium errors mention DevToolsActivePort or `/dev/shm`, run Docker with `--shm-size=2g` or increase `/dev/shm`.
- If you get import errors for `telegram` or `filters`, ensure `python-telegram-bot>=22.4` is installed (Dockerfile already includes this).

### Push to GitHub
```bash
git init
git remote add origin https://github.com/<your-username>/<your-repo>.git
git add .
git commit -m "Fix EC2/Chromium startup, 1h interval, docs"
git branch -M main
git push -u origin main
```

'''
docker build -t flipkart-bot .
docker run -d --name flipkart-bot \
  -e TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN \
  --shm-size=2g \
  --restart unless-stopped \
  flipkart-bot
docker logs -f flipkart-bot | cat
'''
