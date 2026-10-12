#!/usr/bin/env python3
"""Install a launcher for this source checkout into the user's app menu."""
import os
from pathlib import Path


def quoted_exec(path: Path) -> str:
    value = str(path)
    if any(char in value for char in ("\n", "\r", "\0")):
        raise ValueError("Launcher path contains an unsupported control character")
    # Desktop Entry escaping followed by Exec argument quoting.
    value = value.replace("%", "%%").replace("\\", "\\\\")
    for char in ('"', '$', '`'):
        value = value.replace(char, "\\" + char)
    return '"' + value.replace("\\", "\\\\") + '"'


root = Path(__file__).resolve().parent.parent
base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
if not base.is_absolute():
    base = Path.home() / ".local/share"
target = base / "applications/the-puppeteer.desktop"
target.parent.mkdir(parents=True, exist_ok=True)
icon = str(root / "puppeteer/qml/logo.svg").replace("\\", "\\\\")
target.write_text("[Desktop Entry]\nType=Application\nName=The Puppeteer\nComment=Distrobox environment manager\nComment[tr]=Distrobox ortam yöneticisi\nExec=" + quoted_exec(root / "run.sh") + "\nIcon=" + icon + "\nTerminal=false\nCategories=System;Utility;\nStartupNotify=true\n")
target.chmod(0o644)
print("Menü kısayolu oluşturuldu:", target)
print("Bu klasörü taşırsan bu betiği yeniden çalıştır.")
