"""Application entry point."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
from .runtime import load_qt, report_qt_error


def main() -> int:
    parser = argparse.ArgumentParser(prog="the-puppeteer")
    parser.add_argument("--demo", action="store_true", help="Example data; execute no system commands")
    parser.add_argument("--smoke-test", action="store_true", help="Load QML, verify startup and quit after one second")
    args = parser.parse_args()
    if os.geteuid() == 0 and not args.demo:
        print("The Puppeteer kullanıcı hesabıyla çalıştırılmalı; sudo ile başlatma.", file=sys.stderr)
        return 2
    try:
        qt = load_qt()
    except (ImportError, OSError) as error:
        report_qt_error(error)
        return 2
    from .backend import Backend
    from .core import config_home
    app = qt.QGuiApplication([sys.argv[0]])
    app.setApplicationName("The Puppeteer")
    app.setOrganizationName("ThePuppeteer")
    app.setApplicationVersion("0.1.0")
    app.setDesktopFileName("the-puppeteer")
    assets = Path(__file__).parent / "qml"
    app.setWindowIcon(qt.QIcon(str(assets / "logo.svg")))
    lock = None
    if not args.demo:
        config_home().mkdir(parents=True, exist_ok=True)
        lock = qt.QLockFile(str(config_home() / "application.lock"))
        if not lock.tryLock(100):
            print("The Puppeteer zaten açık.", file=sys.stderr)
            return 1
    qt.QQuickStyle.setStyle("Basic")
    backend = Backend(demo=args.demo)
    engine = qt.QQmlApplicationEngine()
    backend.setParent(engine)
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(qt.QUrl.fromLocalFile(str(assets / "Main.qml")))
    if not engine.rootObjects():
        return 1
    qt.QTimer.singleShot(0, backend.refresh)
    if args.smoke_test:
        qt.QTimer.singleShot(1000, app.quit)
    return app.exec()
