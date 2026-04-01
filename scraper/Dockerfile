FROM mcr.microsoft.com/playwright/python:latest

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY scraper/requirements-scraper.txt  ./

# Ensure any stale apt state is removed, then retry update a few times to
# avoid intermittent "Hash Sum mismatch" errors from mirrors.
RUN rm -rf /var/lib/apt/lists/* \
 && set -eux; \
 for i in 1 2 3; do \
     apt-get update && break || sleep 5; \
 done; \
 pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements-scraper.txt \
 && rm -rf /var/lib/apt/lists/*

COPY scraper/ /app/

RUN mkdir -p /app/logs /app/data /app/cookies

# Attempt to fetch camoufox browser if camoufox is used (no-op on failure)
RUN python3 -m camoufox fetch || true

RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
