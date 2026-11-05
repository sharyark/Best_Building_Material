#!/usr/bin/env bash
# Same as ./dev.sh but never loads demo data: existing data is kept, an empty database stays empty
# (only the first admin login from backend/.env, the cash account and the chart of accounts).
exec "$(dirname "${BASH_SOURCE[0]}")/dev.sh" --no-demo "$@"
