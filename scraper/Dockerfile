FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY scraper/ /app/

RUN set -eux; \
 python -m pip install --upgrade pip; \
 for i in 1 2 3 4 5; do \
	 python -m pip install --no-cache-dir --retries 10 --timeout 60 -r /app/requirements-scraper.txt && break; \
	 echo "pip install failed (attempt $i/5), retrying..."; \
	 sleep 5; \
 done

RUN mkdir -p /app/logs /app/data /app/cookies

RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
