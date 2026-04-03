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

# Attempt to fetch camoufox browser if camoufox is used. Retry transient SSL failures.
RUN set -eux; \
  attempts=0; \
  max_attempts=5; \
  until [ "$attempts" -ge "$max_attempts" ]; do \
    attempts=$((attempts + 1)); \
    python3 -m camoufox fetch && break || echo "camoufox fetch failed on attempt $attempts/$max_attempts"; \
    sleep 5; \
  done; \
  if [ "$attempts" -ge "$max_attempts" ]; then \
    echo "camoufox fetch failed after $max_attempts attempts, continuing without failing build"; \
  fi

RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
