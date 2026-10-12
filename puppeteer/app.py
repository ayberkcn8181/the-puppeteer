"""Application entry point."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="the-puppeteer")
    parser.add_argument("--demo", action="store_true", help="Example data; execute no system commands")
    parser.add_argument("--smoke-test", action="store_true", help="Load QML, verify startup and quit after one second")
    args = parser.parse_args()
    if os.geteuid() == 0 and not args.demo:
        print("The Puppeteer kullanıcı hesabıyla çalıştırılmalı; sudo ile başlatma.", file=sys.stderr)
        return 2
    try:
        from PySide6.QtCore import QTimer, QUrl, QLockFile
        from PySide6.QtGui import QGuiApplication, QIcon
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtQuickControls2 import QQuickStyle
        from .backend import Backend
        from .core import config_home
    except ImportError:
        print("PySide6 eksik. README'deki kurulum adımlarını uygula.", file=sys.stderr)
        return 2
    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName("The Puppeteer")
    app.setOrganizationName("ThePuppeteer")
    app.setApplicationVersion("0.1.0")
    app.setDesktopFileName("the-puppeteer")
    assets = Path(__file__).parent / "qml"
    app.setWindowIcon(QIcon(str(assets / "logo.svg")))
    lock = None
    if not args.demo:
        config_home().mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(config_home() / "application.lock"))
        if not lock.tryLock(100):
            print("The Puppeteer zaten açık.", file=sys.stderr)
            return 1
    QQuickStyle.setStyle("Basic")
    backend = Backend(demo=args.demo)
    engine = QQmlApplicationEngine()
    backend.setParent(engine)
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(assets / "Main.qml")))
    if not engine.rootObjects():
        return 1
    QTimer.singleShot(0, backend.refresh)
    if args.smoke_test:
        QTimer.singleShot(1000, app.quit)
    return app.exec()
