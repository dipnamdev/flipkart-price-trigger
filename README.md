## Flipkart Price Tracker Bot

Run a Telegram bot that tracks Flipkart product prices using headless Chromium + Selenium and sends drop alerts.

### Requirements
- Python 3.12 or Docker
- Telegram bot token set in env var `TELEGRAM_TOKEN`

### EC2 setup (without Docker)
```bash
# 1) System packages
sudo apt-get update
sudo apt-get install -y python3-pip chromium chromium-driver fonts-liberation unzip

# 2) Project setup
cd ~/Flipkart-Trigger   # adjust to your path
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip

# Install from requirements.txt (recommended) or fallback to inline list
pip install -r requirements.txt || true

# If requirements.txt not present on EC2, install key deps directly
python -m pip install \
  python-telegram-bot>=22.4 selenium>=4.35.0 requests>=2.32.3 \
  python-dotenv>=1.0.1 beautifulsoup4>=4.12.3 schedule>=1.2.2 webdriver-manager>=4.0.1

# 3) Configure environment
cp .env.example .env  # then edit TELEGRAM_TOKEN
export $(grep -v '^#' .env | xargs)

# 4) Run
python flipkart_price_alert.py
```

### Quick start with Docker (optional)
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
- The background checker sleeps for 30 minutes between runs (configurable in `flipkart_price_alert.py`).
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

```
