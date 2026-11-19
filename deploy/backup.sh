#!/usr/bin/env bash
# Nightly Postgres backup with 7-day retention. Installed as a cron job by bootstrap.sh.
# Restore: gunzip -c launchscout-YYYYmmdd-HHMM.sql.gz | docker compose exec -T postgres psql -U launchscout launchscout
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
STAMP="$(date +%Y%m%d-%H%M)"
OUT="$BACKUP_DIR/launchscout-$STAMP.sql.gz"

mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  sh -c 'pg_dump --no-owner --clean --if-exists -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip -9 > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
chmod 600 "$OUT"
find "$BACKUP_DIR" -name 'launchscout-*.sql.gz' -type f -mtime +"$((RETENTION_DAYS - 1))" -delete
echo "$(date -Is) backup ok: $OUT ($(du -h "$OUT" | cut -f1))"
