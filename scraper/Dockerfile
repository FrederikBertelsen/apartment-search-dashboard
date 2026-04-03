FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY scraper/ /app/

RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r /app/requirements-scraper.txt

RUN mkdir -p /app/logs /app/data /app/cookies

RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
