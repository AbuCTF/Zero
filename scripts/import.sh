#!/bin/bash
# ZeroPool Import Script - Easy VPS Migration
# Usage: ./scripts/import.sh backup_file.tar.gz

set -e

if [ -z "$1" ]; then
    echo "Usage: ./scripts/import.sh backup_file.tar.gz"
    exit 1
fi

BACKUP_FILE="$1"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "🔄 ZeroPool Import Starting..."
echo "📁 Backup: $BACKUP_FILE"

# Extract backup
echo "📦 Extracting backup..."
BACKUP_NAME=$(basename "$BACKUP_FILE" .tar.gz)
cd /tmp
tar -xzf "$BACKUP_FILE"

BACKUP_DIR="/tmp/$BACKUP_NAME"

# Copy .env
echo "📋 Restoring .env..."
cp "$BACKUP_DIR/.env" "$PROJECT_DIR/.env"

# Copy fonts
echo "🔤 Restoring fonts..."
cp -r "$BACKUP_DIR/fonts/"* "$PROJECT_DIR/fonts/"

# Start database
echo "🚀 Starting database..."
cd "$PROJECT_DIR"
docker compose up -d db redis
sleep 5

# Wait for DB to be ready
echo "⏳ Waiting for database..."
until docker compose exec -T db pg_isready -U zeropool; do
    sleep 2
done

# Import database
echo "📥 Importing database..."
docker compose exec -T db psql -U zeropool zeropool < "$BACKUP_DIR/database.sql"

# Start all services
echo "🚀 Starting all services..."
docker compose up -d

# Wait for API
sleep 5

# Restore storage
echo "📂 Restoring storage..."
docker compose cp "$BACKUP_DIR/storage" api:/app/

# Cleanup
rm -rf "$BACKUP_DIR"

echo ""
echo "✅ Import complete!"
echo ""
echo "Your ZeroPool instance should be running at:"
echo "  Frontend: http://localhost:3000"
echo "  API: http://localhost:8000"
echo ""
echo "Update your .env with production URLs and restart:"
echo "  docker compose restart"
