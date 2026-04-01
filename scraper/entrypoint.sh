#!/bin/sh
set -eu

# Default schedule can be overridden with the CRON_SCHEDULE environment variable
CRON_SCHEDULE="${CRON_SCHEDULE:-0 4 * * *}" # Default: every day at 4 AM
LOG_FILE="${LOG_FILE:-/app/logs/scrape.log}"

mkdir -p /app/logs /app/data /app/cookies

# Create a small wrapper script that cron and the startup run can call. This
# avoids complex escaping in the cron file (percent signs in commands are
# special in crontab entries and caused the "bad minute" errors).
RUNNER="/app/run_scrapers.sh"

cat > "$RUNNER" <<'SH'
#!/bin/sh
set -eu
# Default log path used when cron runs (cron jobs get a very small env)
LOG_FILE="/app/logs/scrape.log"
printf '\n####################################################\n    [%s]\n####################################################\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
python3 /app/kab_data.py >> "$LOG_FILE" 2>&1
python3 /app/s_dk_data.py >> "$LOG_FILE" 2>&1
SH

chmod +x "$RUNNER"

# Write a simple cron job that calls the wrapper script. Keep the line simple
# so cron doesn't choke on percent signs or complex quoting.
echo "$CRON_SCHEDULE root $RUNNER" > /etc/cron.d/scrape-cron
chmod 0644 /etc/cron.d/scrape-cron

# Start cron daemon
cron || true

# Run once at startup to seed logs (failures tolerated)
"$RUNNER" || true

# Stream the log to container stdout so `docker logs` contains output
tail -F "$LOG_FILE"
