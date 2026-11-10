#!/usr/bin/env bash
# Nightly backup of the whole Nakupak SQLite DB (gzip). Keeps the last KEEP_DAYS days.
# Intended to run from cron.
set -euo pipefail

CONTAINER="${CONTAINER:-nakupak}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"
DB_PATH="${DB_PATH:-/app/data/nakupak.db}"

mkdir -p "$BACKUP_DIR"
out="$BACKUP_DIR/nakupak-db-$(date +%F_%H%M).db.gz"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Consistent snapshot via SQLite's backup API (safe while the app is running)
docker exec -i -e DB_PATH="$DB_PATH" "$CONTAINER" python - <<'PY' | gzip -9 > "$tmp"
import os, sqlite3, sys, tempfile
src = sqlite3.connect(os.environ["DB_PATH"])
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "snap.db")
    dst = sqlite3.connect(p)
    src.backup(dst)
    dst.close()
    sys.stdout.buffer.write(open(p, "rb").read())
PY

# Only keep it if it is a valid gzip containing a SQLite file
gzip -t "$tmp"
[ "$(gzip -dc "$tmp" | head -c 15)" = "SQLite format 3" ] || { echo "DB backup invalid" >&2; exit 1; }

mv "$tmp" "$out"
chmod 600 "$out"

find "$BACKUP_DIR" -maxdepth 1 -type f -name 'nakupak-db-*.db.gz' -mtime +$((KEEP_DAYS - 1)) -delete

echo "$(date -Is) backup ok: $out"
