#!/usr/bin/env sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$project_dir"
# Only the standard library is required, including after .venv is removed.
exec python3 -m puppeteer.uninstall "$@"
