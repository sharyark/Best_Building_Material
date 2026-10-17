#!/bin/sh
# Restores the newest dump into a throw-away database and checks the books still balance.
# Exits non-zero (loudly) if the backup is unusable. Run monthly by cron, or by hand any time:
#   docker compose exec backup /scripts/restore-test.sh
set -eu
LATEST="$(ls -1t /backups/daily/*.sql.gz 2>/dev/null | head -n 1 || true)"
[ -n "$LATEST" ] || { echo "RESTORE TEST FAILED: no backup found"; exit 1; }
TESTDB="restore_test_$$"
echo "[$(date -Is)] restore test of $LATEST into ${TESTDB}"
# The app role may not create databases, so the scratch restore uses the admin login.
export PGUSER="${ADMIN_PGUSER:-$PGUSER}" PGPASSWORD="${ADMIN_PGPASSWORD:-$PGPASSWORD}"
psql -d postgres -qc "CREATE DATABASE ${TESTDB}"
trap 'psql -d postgres -qc "DROP DATABASE IF EXISTS ${TESTDB}" >/dev/null 2>&1 || true' EXIT
gunzip -c "$LATEST" | psql -d "$TESTDB" -q -v ON_ERROR_STOP=1 >/dev/null

BALANCE="$(psql -d "$TESTDB" -Atc "SELECT COALESCE(SUM(debit),0) = COALESCE(SUM(credit),0) FROM journal_lines")"
ENTRIES="$(psql -d "$TESTDB" -Atc "SELECT count(*) FROM journal_entries")"
USERS="$(psql -d "$TESTDB" -Atc "SELECT count(*) FROM users")"
echo "restored: ${ENTRIES} journal entries, ${USERS} users, debits equal credits: ${BALANCE}"
[ "$BALANCE" = "t" ] || { echo "RESTORE TEST FAILED: restored books do not balance"; exit 1; }
[ "$USERS" -ge 1 ] || { echo "RESTORE TEST FAILED: no users in restored database"; exit 1; }
echo "[$(date -Is)] RESTORE TEST PASSED"
