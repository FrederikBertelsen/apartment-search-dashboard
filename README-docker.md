Docker setup for apartment-search-dashboard

Quick start

1) Build and start both services with docker-compose:

```bash
docker compose up --build -d
```

2) The Dash app will be available at http://localhost:8050.

3) Scraper logs:
- Scraper output is appended to `logs/scrape.log` (also streamed to `docker logs`).
- Control the cron schedule using the `CRON_SCHEDULE` environment variable, for example:

```bash
CRON_SCHEDULE="0 * * * *" docker compose up --build -d
```

Notes and caveats
- The scraper container requires Playwright/Camoufox for browser automation; the image will attempt to fetch Camoufox browser during build. This makes the scraper image larger than a minimal Python image.
- If you do not need scraping inside Docker, consider running the scraper scripts on the host to keep containers small.
