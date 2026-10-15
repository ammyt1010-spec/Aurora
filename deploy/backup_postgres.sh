#!/usr/bin/env bash
# Offline-compatible PostgreSQL backup. Keep backup directory encrypted.
set -Eeuo pipefail
: "${AURORA_BACKUP_DIR:?AURORA_BACKUP_DIR is required}"
: "${PGDATABASE:?PGDATABASE is required}"
command -v pg_dump >/dev/null || { echo 'pg_dump not found' >&2; exit 1; }
umask 077
mkdir -p -- "$AURORA_BACKUP_DIR"
chmod 700 -- "$AURORA_BACKUP_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
file="$AURORA_BACKUP_DIR/aurora-${PGDATABASE}-${ts}.dump"
tmp="${file}.partial"
trap 'rm -f -- "$tmp"' EXIT
pg_dump --format=custom --no-owner --no-acl --file="$tmp"
pg_restore --list "$tmp" >/dev/null
mv -- "$tmp" "$file"
trap - EXIT
echo "Verified backup written to: $file"
