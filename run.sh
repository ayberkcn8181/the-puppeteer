#!/usr/bin/env sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$project_dir"
if [ -x "$project_dir/.venv/bin/python" ]; then
    exec "$project_dir/.venv/bin/python" -m puppeteer "$@"
elif python3 -c 'import PySide6' >/dev/null 2>&1; then
    exec python3 -m puppeteer "$@"
else
    printf '%s\n' 'PySide6 bulunamadı. Önce ./setup.sh çalıştır veya dağıtımının PySide6 paketini kur.' >&2
    exit 2
fi
