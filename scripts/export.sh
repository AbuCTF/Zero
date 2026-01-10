#!/bin/bash
# ZeroPool Export Script - Easy VPS Migration
# Usage: ./scripts/export.sh [backup_name]

set -e

BACKUP_NAME="${1:-zeropool_backup_$(date +%Y%m%d_%H%M%S)}"
BACKUP_DIR="/tmp/$BACKUP_NAME"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🔄 ZeroPool Export Starting..."
echo "📁 Backup: $BACKUP_NAME"

mkdir -p "$BACKUP_DIR"

# Export PostgreSQL database
echo "📦 Exporting database..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T db pg_dump -U zeropool zeropool > "$BACKUP_DIR/database.sql"

# Copy .env file
echo "📋 Copying .env..."
cp "$PROJECT_DIR/.env" "$BACKUP_DIR/.env"

# Export storage volume (certificates, uploads)
echo "📂 Exporting storage..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" cp api:/app/storage "$BACKUP_DIR/storage"

# Export fonts
echo "🔤 Copying fonts..."
cp -r "$PROJECT_DIR/fonts" "$BACKUP_DIR/fonts"

# Create archive
echo "🗜️ Creating archive..."
cd /tmp
tar -czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME"

# Move to project dir
mv "$BACKUP_NAME.tar.gz" "$PROJECT_DIR/"

# Cleanup
rm -rf "$BACKUP_DIR"

echo ""
echo "✅ Export complete: $PROJECT_DIR/$BACKUP_NAME.tar.gz"
echo ""
echo "To import on new server:"
echo "  1. Copy $BACKUP_NAME.tar.gz to new server"
echo "  2. Clone repo: git clone git@github.com:AbuCTF/Zero.git"
echo "  3. Run: ./scripts/import.sh $BACKUP_NAME.tar.gz"
