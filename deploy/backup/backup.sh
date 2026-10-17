#!/bin/sh
# Nightly pg_dump -> gzip -> /backups, keep N daily + N monthly, optional off-site copy.
set -eu
KEEP_DAILY="${KEEP_DAILY:-30}"
KEEP_MONTHLY="${KEEP_MONTHLY:-12}"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="/backups/daily/${PGDATABASE}-${STAMP}.sql.gz"
TMP="${FILE}.partial"

echo "[$(date -Is)] dumping ${PGDATABASE}"
pg_dump --no-owner --no-privileges | gzip -9 > "$TMP"
# A truncated dump is worse than none: verify gzip integrity before keeping it.
gzip -t "$TMP"
mv "$TMP" "$FILE"
echo "[$(date -Is)] wrote ${FILE} ($(du -h "$FILE" | cut -f1))"

# Keep the first dump of every month as the monthly copy.
if [ "$(date +%d)" = "01" ]; then
    cp "$FILE" "/backups/monthly/${PGDATABASE}-$(date +%Y%m).sql.gz"
fi

# Retention: newest KEEP_DAILY dailies and KEEP_MONTHLY monthlies.
ls -1t /backups/daily/*.sql.gz 2>/dev/null | tail -n +$((KEEP_DAILY + 1)) | xargs -r rm -f
ls -1t /backups/monthly/*.sql.gz 2>/dev/null | tail -n +$((KEEP_MONTHLY + 1)) | xargs -r rm -f

if [ -n "${OFFSITE_REMOTE:-}" ]; then
    echo "[$(date -Is)] copying to off-site ${OFFSITE_REMOTE}"
    rclone sync /backups "${OFFSITE_REMOTE}" --transfers 2 --quiet
    echo "[$(date -Is)] off-site copy done"
else
    echo "[$(date -Is)] WARNING: no off-site remote configured; backups exist only on this VPS"
fi
