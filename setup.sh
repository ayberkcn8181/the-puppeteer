#!/usr/bin/env sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$project_dir"
. "$project_dir/packaging/python-runtime.sh"
if select_puppeteer_python; then
    printf 'PySide6 / Qt hazır. Python: %s\n' "$python_bin"
    printf '%s\n' 'Uygulamayı ./run.sh ile açabilirsin.'
    exit 0
fi
created_venv=0
if [ ! -e .venv ]; then
    python3 -m venv .venv
    created_venv=1
elif [ ! -x .venv/bin/python ]; then
    printf '%s\n' '.venv mevcut fakat geçerli bir Python ortamı değil.' >&2
    exit 1
fi
if [ "$created_venv" -eq 1 ]; then
    .venv/bin/python - <<'PY'
import json
from pathlib import Path
Path('.venv/.the-puppeteer-owned').write_text(json.dumps({'application':'the-puppeteer','source':str(Path.cwd().resolve())}))
PY
fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m puppeteer.runtime
printf '%s\n' 'Hazır. ./run.sh veya ./run.sh --demo ile başlat.'
