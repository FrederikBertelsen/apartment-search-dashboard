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
  
  echo "�🛑 Stopping containers..."
  docker compose down
  
  echo "📥 Pulling latest changes..."
  git pull
  
  echo "🏗️  Rebuilding both images (web + scraper)..."
  docker compose build web scraper
  
  echo "🚀 Starting web container only..."
  docker compose up -d --no-build --force-recreate web
  
  echo "✅ Deployment complete!"
  echo "📊 Container status:"
  docker compose ps

REMOTE_SCRIPT

echo "✨ Deployment finished successfully!"
