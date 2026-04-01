#!/bin/sh
set -eu

# Default schedule can be overridden with the CRON_SCHEDULE environment variable
CRON_SCHEDULE="${CRON_SCHEDULE:-0 4 * * *}" # Default: every day at 4 AM
LOG_FILE="${LOG_FILE:-/app/logs/scrape.log}"

mkdir -p /app/logs /app/data /app/cookies

# Write cron job. Include a dated header before each run (date is evaluated by cron at runtime)
# Place the job in /etc/cron.d (this file must include the user field). Do NOT run
# `crontab` on the file — the system cron daemon reads /etc/cron.d entries directly.
echo "$CRON_SCHEDULE root cd /app && printf '\n####################################################\n    [%s]\n####################################################\n' \"\$(date '+\%Y-\%m-\%d \%H:\%M:\%S')\" >> $LOG_FILE && python3 kab_data.py >> $LOG_FILE 2>&1 && python3 s_dk_data.py >> $LOG_FILE 2>&1" > /etc/cron.d/scrape-cron
chmod 0644 /etc/cron.d/scrape-cron

# Start cron daemon
cron || true

# Run the scraping once at startup to seed logs (failures are tolerated)
printf '\n####################################################\n    [%s]\n####################################################\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
python3 kab_data.py >> "$LOG_FILE" 2>&1 || true
python3 s_dk_data.py >> "$LOG_FILE" 2>&1 || true

# Stream the log to container stdout so `docker logs` contains output
tail -F "$LOG_FILE"
