#!/bin/sh
set -eu

CRON_MARKER="# apartment-search-dashboard-scraper-cron"

crontab -l 2>/dev/null | grep -v "${CRON_MARKER}" | crontab -

echo "Cron disabled (marker removed)."