#!/bin/sh
set -eu

CRON_MARKER="apartment-search-dashboard-scraper-cron"

# Remove any lines containing the marker (both the commented marker and the cron entry suffixed with the marker)
crontab -l 2>/dev/null | grep -v "${CRON_MARKER}" | crontab -

echo "Cron disabled (marker removed)."