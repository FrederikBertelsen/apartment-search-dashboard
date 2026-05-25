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

  echo "📁 Ensuring runtime folders exist..."
  mkdir -p data logs cookies

  CLEAN_COUNT=$(find data -maxdepth 1 -type f -name "*_clean.csv" | wc -l | tr -d ' ')
  echo "🧮 Found $CLEAN_COUNT cleaned CSV file(s) in ./data"

  if [ "$CLEAN_COUNT" -eq 0 ]; then
    echo "⚠️  No cleaned data found. Running scraper once to populate ./data..."
    docker compose --profile scraper up --build --abort-on-container-exit scraper

    CLEAN_COUNT=$(find data -maxdepth 1 -type f -name "*_clean.csv" | wc -l | tr -d ' ')
    echo "🧮 Cleaned CSV files after scraper run: $CLEAN_COUNT"

    if [ "$CLEAN_COUNT" -eq 0 ]; then
      echo "❌ Scraper did not produce cleaned CSV files in ./data"
      exit 1
    fi
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
