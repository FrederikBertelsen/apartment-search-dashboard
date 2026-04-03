#!/bin/sh
set -eu

LOG_FILE="${LOG_FILE:-/app/logs/scrape.log}"

mkdir -p /app/logs /app/data /app/cookies

# Ensure camoufox runtime assets are available. If missing, attempt fetch
# at container start as a fallback (non-fatal here so logs will capture any
# failure and the scripts may still run or fail with clearer messages).
if [ ! -f /root/.cache/camoufox/version.json ]; then
	echo "Camoufox assets missing; attempting fetch..." >> "$LOG_FILE" 2>&1 || true
	python3 -m camoufox fetch >> "$LOG_FILE" 2>&1 || echo "camoufox fetch failed" >> "$LOG_FILE" 2>&1 || true
fi

printf '\n####################################################\n    [%s]\n####################################################\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"

python3 /app/kab_data.py >> "$LOG_FILE" 2>&1
python3 /app/s_dk_data.py >> "$LOG_FILE" 2>&1

echo "Scrape finished at $(date '+%Y-%m-%d %H-%M-%S')" >> "$LOG_FILE"
