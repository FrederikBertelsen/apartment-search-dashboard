#!/usr/bin/env bash
set -euo pipefail

# Pull cleaned CSV data from remote deployment host into local ./data
# Usage: ./scripts/pull_data.sh [TARGET_DIR]
# Reads SERVER_HOST, SERVER_USER and SSH_KEY from .env (same as deploy.sh)

HERE=$(cd "$(dirname "$0")/.." && pwd)
cd "$HERE"

if [ ! -f .env ]; then
  echo "Error: .env not found in project root. Create it or copy from .env.example"
  exit 1
fi

source .env

if [ -z "${SERVER_HOST:-}" ] || [ -z "${SERVER_USER:-}" ] || [ -z "${SSH_KEY:-}" ]; then
  echo "Error: SERVER_HOST, SERVER_USER and SSH_KEY must be set in .env"
  exit 1
fi

REMOTE_DIR="/portainer/apartment-search-dashboard/data/"
LOCAL_DIR="${1:-data}"

mkdir -p "$LOCAL_DIR"

echo "Pulling data from ${SERVER_USER}@${SERVER_HOST}:${REMOTE_DIR} -> ${LOCAL_DIR}"

if command -v rsync >/dev/null 2>&1; then
  RSYNC_SSH_OPTS="-e \"ssh -i \"$SSH_KEY\" -o StrictHostKeyChecking=accept-new\""
  # shellcheck disable=SC2086
  rsync -avz --progress -e "ssh -i \"$SSH_KEY\" -o StrictHostKeyChecking=accept-new" "${SERVER_USER}@${SERVER_HOST}:${REMOTE_DIR}" "$LOCAL_DIR/"
else
  echo "rsync not found; falling back to scp (slower)."
  scp -r -i "$SSH_KEY" "${SERVER_USER}@${SERVER_HOST}:${REMOTE_DIR}"* "$LOCAL_DIR/"
fi

echo "Done. Local files in: $LOCAL_DIR"
