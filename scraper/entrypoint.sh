#!/bin/sh
set -eu

LOG_FILE="${LOG_FILE:-/app/logs/scrape.log}"

mkdir -p /app/logs /app/data /app/cookies

printf '\n####################################################\n    [%s]\n####################################################\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"

python3 /app/kab_data.py >> "$LOG_FILE" 2>&1
python3 /app/s_dk_data.py >> "$LOG_FILE" 2>&1

echo "Scrape finished at $(date '+%Y-%m-%d %H-%M-%S')" >> "$LOG_FILE"
