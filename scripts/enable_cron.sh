#!/bin/sh
set -eu

PROJECT_DIR="/portainer/apartment-search-dashboard"
CRON_MARKER="# apartment-search-dashboard-scraper-cron"
CRON_ENTRY="0 4 * * * cd ${PROJECT_DIR} && docker compose run --rm scraper >> ${PROJECT_DIR}/logs/cron-run.log 2>&1"

# Preserve existing crontab lines and remove any existing marker line.
crontab -l 2>/dev/null | grep -v "${CRON_MARKER}" > /tmp/apartment-search-current-cron.tmp || true

# Write updated crontab with our job.
{
  cat /tmp/apartment-search-current-cron.tmp
  echo "${CRON_MARKER} ${CRON_ENTRY}"
} | crontab -

rm -f /tmp/apartment-search-current-cron.tmp

echo "Cron enabled: ${CRON_ENTRY}"
