# Apartment Search Dashboard

A minimal Dash app with an integrated scraper that visualizes historical apartment/tenancy queue data from KAB and s.dk and 

## Run the dashboard

```bash
docker compose up -d web
```

Open http://localhost:8050

## Run the scraper

1. Create `scraper/.env` (use `scraper/.env.example` as a template) and add credentials.
2. Run:

```bash
docker compose run --rm scraper
```

## scripts

- `enable_cron.sh`: installs a daily cron job that runs the scraper container
- `disable_cron.sh`: removes that cron job
- `deploy.sh` SSH into a server, pulls latest changes, rebuilds images, and restarts the `web` container. It expects a top-level `.env` with server/SSH config.
