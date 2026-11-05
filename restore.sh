#!/usr/bin/env bash
# Put a backup (.dump) back into the Hisaab database, e.g. on a new PC after cloning, or to undo a mistake.
#   ./restore.sh                 pick from the .dump files in backups/ and this folder
#   ./restore.sh path/file.dump  restore that file
# Same as restore.bat on Windows. The database goes back to the moment of that backup: anything entered after it
# is removed. Before restoring it takes a backup of the current data (backup.sh), so a wrong choice can be undone.
# --yes skips the questions (tests only).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
COMPOSE=(docker compose -f docker-compose.dev.yml)
DB="${HISAAB_DB:-hisaab}"  # database name; only tests change it
YES=0
FILE=""
for arg in "$@"; do
  if [ "$arg" = "--yes" ]; then YES=1; else FILE="$arg"; fi
done
fail() { echo; echo "RESTORE NAHI HUA: $1" >&2; echo "Database pehle jaisa hi hai." >&2; exit 1; }

# ---- 1. which backup
if [ -z "$FILE" ]; then
  mapfile -t files < <(ls -1t backups/*.dump ./*.dump 2>/dev/null || true)
  [ "${#files[@]}" -gt 0 ] || fail "Koi .dump file nahi mili. Backup file backups/ folder mein (ya isi folder mein) rakhein."
  echo; echo "Backup files (sab se nayi upar):"
  for i in "${!files[@]}"; do
    printf "  %2d.  %-40s %s  %s\n" "$((i + 1))" "${files[$i]}" "$(date -r "${files[$i]}" '+%d-%m-%Y %H:%M')" "$(du -h "${files[$i]}" | cut -f1)"
  done
  echo; read -rp "Kaunsi file? Number likhein (khaali chhorein to band): " pick
  [ -n "$pick" ] || exit 0
  [[ "$pick" =~ ^[0-9]+$ ]] && [ "$pick" -ge 1 ] && [ "$pick" -le "${#files[@]}" ] || fail "Ghalat number: $pick"
  FILE="${files[$((pick - 1))]}"
fi
[ -f "$FILE" ] || fail "File nahi mili: $FILE"

# ---- 2. Docker and the database
docker info >/dev/null 2>&1 || fail "Docker chal nahi raha."
echo "==> Database check"
"${COMPOSE[@]}" up -d db >/dev/null 2>&1 || fail "Database start nahi hua."
for _ in $(seq 60); do "${COMPOSE[@]}" exec -T db pg_isready -U hisaab >/dev/null 2>&1 && break; sleep 1; done
"${COMPOSE[@]}" exec -T db pg_isready -U hisaab >/dev/null 2>&1 || fail "Database 60 second mein tayyar nahi hua."
# The app must not be writing while the tables are replaced.
if [ "$DB" = hisaab ] && (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -q ':8000 '; then
  fail "App abhi chal rahi hai (port 8000). Pehle dev.sh / dev_without_data.sh band karein (Ctrl+C), phir dobara chalayein."
fi

# ---- 3. check the file before touching anything
echo "==> Backup file check: $FILE"
"${COMPOSE[@]}" cp "$FILE" db:/tmp/restore.dump >/dev/null 2>&1 || fail "File database tak nahi pahunchi."
"${COMPOSE[@]}" exec -T db pg_restore -l /tmp/restore.dump >/dev/null 2>&1 || fail "Ye sahi backup file nahi (ya kharab hai). Koi aur file chunein."

# ---- 4. confirm
if [ "$YES" != 1 ]; then
  echo; echo "DHYAN: database is backup ke waqt par wapas chala jayega: $FILE ($(date -r "$FILE" '+%d-%m-%Y %H:%M'))"
  echo "Abhi database mein jo hai woh hat jayega (pehle us ka backup khud ban jayega)."
  read -rp "Pakka? 'haan' likhein: " ok
  [ "$ok" = haan ] || { echo "Kuch nahi badla."; exit 0; }
fi

# ---- 5. safety backup of what is there now
echo "==> Pehle abhi ke data ka backup"
HISAAB_DB="$DB" ./backup.sh | grep -E "^Backup ho gaya" || fail "Abhi ke data ka backup nahi bana, isliye restore roka."

# ---- 6. restore: all or nothing
echo "==> Backup database mein daala ja raha hai"
"${COMPOSE[@]}" exec -T db pg_restore -U hisaab -d "$DB" --clean --if-exists --no-owner --single-transaction --exit-on-error /tmp/restore.dump \
  || fail "Backup nahi lag saka (upar ka message dekhein)."
"${COMPOSE[@]}" exec -T db rm -f /tmp/restore.dump
counts=$("${COMPOSE[@]}" exec -T db psql -tA -U hisaab -d "$DB" -c "select (select count(*) from users) || ' users, ' || (select count(*) from parties) || ' customers/suppliers, ' || (select count(*) from deliveries) || ' challans'")
echo; echo "Restore ho gaya: $counts"
echo "Ab ./dev_without_data.sh chalayein. Login purane system wala hoga (backup ke users)."
