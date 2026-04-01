FROM mcr.microsoft.com/playwright/python:latest

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements-scraper.txt  ./

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-scraper.txt \
    && rm -rf /var/lib/apt/lists/*

COPY scraper/* ./

RUN mkdir -p /app/logs /app/data /app/cookies

# Attempt to fetch camoufox browser if camoufox is used (no-op on failure)
RUN python3 -m camoufox fetch || true

RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
