#!/usr/bin/env sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$project_dir"
. "$project_dir/packaging/python-runtime.sh"
if select_puppeteer_python; then
    exec "$python_bin" -m puppeteer "$@"
else
    report_puppeteer_python_errors
    printf '%s\n' 'Önce ./setup.sh çalıştır veya dağıtımının PySide6 paketini kur.' >&2
    exit 2
fi
