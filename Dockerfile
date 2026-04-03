FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./

RUN rm -rf /var/lib/apt/lists/* \
 && set -eux; \
 for i in 1 2 3 4 5; do \
     apt-get update && apt-get install -y --no-install-recommends build-essential && break || sleep 5; \
 done; \
 pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && apt-get purge -y --auto-remove build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY . .

RUN rm -rf /app/scraper

EXPOSE 8050

CMD ["python3", "app.py"]
