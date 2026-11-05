#!/usr/bin/env bash
# Backup of the whole Hisaab database (everything up to this moment) into backups/hisaab-<date>_<time>.dump.
# Same as backup.bat on Windows. Safe to run while the app is open.
# Keeps backups for 28 days, but never fewer than the newest 4 files. Restore steps: INSTALL.md, section 7.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
COMPOSE=(docker compose -f docker-compose.dev.yml)
KEEP_DAYS=28
KEEP_AT_LEAST=4
DB="${HISAAB_DB:-hisaab}"  # database name; only tests change it
fail() { echo; echo "BACKUP NAHI HUA: $1" >&2; exit 1; }

docker info >/dev/null 2>&1 || fail "Docker chal nahi raha."
echo "==> Database check"
"${COMPOSE[@]}" up -d db >/dev/null 2>&1 || fail "Database start nahi hua."
for _ in $(seq 60); do "${COMPOSE[@]}" exec -T db pg_isready -U hisaab >/dev/null 2>&1 && break; sleep 1; done
"${COMPOSE[@]}" exec -T db pg_isready -U hisaab >/dev/null 2>&1 || fail "Database 60 second mein tayyar nahi hua."

mkdir -p backups
FILE="backups/hisaab-$(date +%Y-%m-%d_%H%M).dump"
echo "==> Backup ban raha hai"
"${COMPOSE[@]}" exec -T db pg_dump -U hisaab -Fc -f /tmp/hisaab-backup.dump "$DB" || fail "pg_dump nakaam."
# A damaged dump is worse than none: make sure Postgres can read it back before keeping it.
"${COMPOSE[@]}" exec -T db pg_restore -l /tmp/hisaab-backup.dump >/dev/null || fail "Backup file kharab bani."
"${COMPOSE[@]}" cp db:/tmp/hisaab-backup.dump "$FILE" >/dev/null 2>&1 || fail "Backup file save nahi hui."
[ -s "$FILE" ] || fail "Backup file khaali hai."
"${COMPOSE[@]}" exec -T db rm -f /tmp/hisaab-backup.dump

# Old files: older than KEEP_DAYS, but the newest KEEP_AT_LEAST always stay.
removed=0
while IFS= read -r f; do
  if [ -n "$(find "$f" -mtime +"$KEEP_DAYS")" ]; then rm -f "$f"; removed=$((removed + 1)); fi
done < <(ls -1t backups/hisaab-*.dump | tail -n +"$((KEEP_AT_LEAST + 1))")

echo
echo "Backup ho gaya: $FILE ($(du -h "$FILE" | cut -f1))"
[ "$removed" -gt 0 ] && echo "Purane backup mitaye: $removed (28 din se purane)"
echo "Kul backups: $(ls -1 backups/hisaab-*.dump | wc -l)  (folder: $PWD/backups)"
echo "Is file ki ek copy USB ya Google Drive par bhi rakhein."
