FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System deps: chromium + fonts for headless rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

# Ensure Selenium can find Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV PATH="/usr/lib/chromium:${PATH}"

WORKDIR /app

# Install Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    beautifulsoup4>=4.12.3,<5 \
    python-dotenv>=1.0.1,<2 \
    python-telegram-bot>=22.4 \
    requests>=2.32.3,<3 \
    schedule>=1.2.2,<2 \
    selenium>=4.35.0 \
    ipykernel>=6.30.1

# App
COPY flipkart_price_alert.py tracked_products.json ./

# Default command
CMD ["python", "flipkart_price_alert.py"]