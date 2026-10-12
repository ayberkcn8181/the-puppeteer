"""Check the Qt imports used by startup without creating a GUI application."""
from __future__ import annotations

import sys
from types import SimpleNamespace


def load_qt() -> SimpleNamespace:
    from PySide6.QtCore import QTimer, QUrl, QLockFile
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtQuickControls2 import QQuickStyle

    return SimpleNamespace(
        QTimer=QTimer, QUrl=QUrl, QLockFile=QLockFile,
        QGuiApplication=QGuiApplication, QIcon=QIcon,
        QQmlApplicationEngine=QQmlApplicationEngine,
        QQuickWindow=QQuickWindow, QQuickStyle=QQuickStyle,
    )


def report_qt_error(error: Exception) -> None:
    print("PySide6 / Qt bileşenleri yüklenemedi.", file=sys.stderr)
    print(f"Python: {sys.executable}", file=sys.stderr)
    print(f"{type(error).__name__}: {error}", file=sys.stderr)
    print("./setup.sh çalıştır veya bu Python için dağıtımının PySide6/Qt paketlerini denetle.", file=sys.stderr)


def main() -> int:
    try:
        load_qt()
    except (ImportError, OSError) as error:
        report_qt_error(error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
