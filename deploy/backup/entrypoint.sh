#!/bin/sh
set -eu
mkdir -p /backups/daily /backups/monthly
# 02:00 every night: dump. 04:00 on the 1st: prove the newest dump actually restores.
cat > /etc/crontabs/root <<CRON
0 2 * * * /scripts/backup.sh >> /proc/1/fd/1 2>&1
0 4 1 * * /scripts/restore-test.sh >> /proc/1/fd/1 2>&1
CRON
echo "backup container ready: nightly dump 02:00, monthly restore test 04:00 on the 1st"
exec crond -f -l 8
