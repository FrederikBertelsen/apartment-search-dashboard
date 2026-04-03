FROM mcr.microsoft.com/playwright/python:latest

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY scraper/requirements-scraper.txt  ./

# Ensure any stale apt state is removed, then retry update a few times to
# avoid intermittent "Hash Sum mismatch" errors from mirrors.
RUN rm -rf /var/lib/apt/lists/* \
 && set -eux; \
 for i in 1 2 3 4 5; do \
     apt-get update && break || sleep 200; \
 done; \
 pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements-scraper.txt \
 && rm -rf /var/lib/apt/lists/*

COPY scraper/ /app/

RUN mkdir -p /app/logs /app/data /app/cookies

# Use pre-downloaded camoufox archive from project tree if available.
# If the file is absent, this step logs and continues. No network fallback.
RUN set -eux; \
  if [ -f /app/camoufox.zip ] && [ -s /app/camoufox.zip ]; then \
    echo "Using project-provided camoufox archive"; \
    mkdir -p /root/.cache/camoufox; \
    cp /app/camoufox.zip /root/.cache/camoufox/; \
    python3 -m camoufox install /root/.cache/camoufox/camoufox.zip || true; \
  else \
    echo "camoufox archive missing; skipping install"; \
  fi

RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
