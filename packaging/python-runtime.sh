# Shared by setup.sh and run.sh, after changing into project_dir.
# A leftover venv must not hide a working system installation. Import the Qt
# components the application actually needs, not just the PySide6 namespace.
select_puppeteer_python() {
    python_bin=
    for candidate in "$project_dir/.venv/bin/python" "$(command -v python3 || true)" /usr/bin/python3; do
        [ -x "$candidate" ] || continue
        if "$candidate" -m puppeteer.runtime >/dev/null 2>&1; then
            python_bin=$candidate
            return 0
        fi
    done
    return 1
}

report_puppeteer_python_errors() {
    printf '%s\n' 'Çalışan bir PySide6 / Qt ortamı bulunamadı:' >&2
    for candidate in "$project_dir/.venv/bin/python" "$(command -v python3 || true)" /usr/bin/python3; do
        [ -x "$candidate" ] || continue
        "$candidate" -m puppeteer.runtime >&2 || true
    done
}
