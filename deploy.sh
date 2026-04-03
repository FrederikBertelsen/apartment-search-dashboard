#!/bin/bash

# apartment-search-dashboard Deployment Script
# Automatically deploys project to the remote server

set -e  # Exit on error

# Load configuration from .env file
if [ ! -f .env ]; then
  echo "❌ Error: .env file not found!"
  echo "Please create a .env file based on .env.example"
  exit 1
fi

source .env

echo "🚀 Starting deployment to $SERVER_HOST..."

# Execute remote commands
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_HOST" bash << 'REMOTE_SCRIPT'
  set -e
  
  PROJECT_ROOT="/portainer/apartment-search-dashboard"
  
  echo "📍 Navigating to project root..."
  cd "$PROJECT_ROOT" || exit 1
  
  echo "📂 Current directory: $(pwd)"
  
  echo "📥 Pulling latest changes..."
  git pull

  # Pre-download camoufox relapse-free build asset (optional but recommended)
  if [ ! -f "scraper/camoufox.zip" ]; then
    echo "⬇️  Downloading camoufox archive for Docker build..."
    mkdir -p scraper
    curl --fail --show-error -L --retry 8 --retry-delay 5 -o scraper/camoufox.zip \
      "https://github.com/daijro/camoufox/releases/download/v135.0.1-beta.24/camoufox-135.0.1-beta.24-lin.x86_64.zip"
    # Ensure the file exists and is non-empty
    if [ ! -s scraper/camoufox.zip ]; then
      echo "❌ camoufox download failed or file is empty"
      rm -f scraper/camoufox.zip || true
      exit 1
    fi
  else
    echo "✅ camoufox archive already exists, skipping download"
  fi

  echo "🛑 Stopping containers..."
  docker compose down
  
  echo "🏗️  Rebuilding both images (web + scraper)..."
  docker compose build --no-cache web scraper
  
  echo "🚀 Starting web container only..."
  docker compose up -d --no-build --force-recreate web
  
  echo "✅ Deployment complete!"
  echo "📊 Container status:"
  docker compose ps

REMOTE_SCRIPT

echo "✨ Deployment finished successfully!"
