#!/bin/sh
set -eu

PROJECT_DIR="/portainer/apartment-search-dashboard"
CRON_MARKER="apartment-search-dashboard-scraper-cron"
CRON_ENTRY="0 4 * * * cd ${PROJECT_DIR} && docker compose run --rm scraper >> ${PROJECT_DIR}/logs/cron-run.log 2>&1"

# Preserve existing crontab lines and remove any existing marker line(s).
crontab -l 2>/dev/null | grep -v "${CRON_MARKER}" > /tmp/apartment-search-current-cron.tmp || true

# Write updated crontab with our job:
# - a commented marker line (for visibility)
# - the cron entry itself, suffixed with the marker so it can be removed later
{
  cat /tmp/apartment-search-current-cron.tmp
  echo "# ${CRON_MARKER}"
  echo "${CRON_ENTRY} # ${CRON_MARKER}"
} | crontab -

rm -f /tmp/apartment-search-current-cron.tmp

echo "Cron enabled: ${CRON_ENTRY}"
