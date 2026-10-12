"""Native Qt/QML integration and QProcess tests; never require real containers."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

try:
    from PySide6.QtCore import QMetaObject, QObject, QUrl, Qt, qInstallMessageHandler, QCoreApplication, QEvent
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtQuickControls2 import QQuickStyle
    from puppeteer.backend import Backend
    from puppeteer.core import Commands, Plan, Step
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


def pump(predicate, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QGuiApplication.processEvents()
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError("Qt condition timed out")


def visual_find(window, name):
    seen = set()
    def visit(obj):
        if obj in seen:
            return None
        seen.add(obj)
        if obj.objectName() == name:
            return obj
        children = list(obj.children())
        if hasattr(obj, "childItems"):
            children += obj.childItems()
        for child in children:
            found = visit(child)
            if found is not None:
                return found
        return None
    return visit(window) or visit(window.contentItem())


@unittest.skipUnless(QT_AVAILABLE, "PySide6 is not installed")
class QtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle("Basic")
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.messages = []
        self.previous = qInstallMessageHandler(lambda kind, context, message: self.messages.append(message))

    def tearDown(self):
        qInstallMessageHandler(self.previous)

    def test_qml_navigation_create_delete_and_theme(self):
        backend = Backend(demo=True)
        engine = QQmlApplicationEngine()
        backend.setParent(engine)
        engine.rootContext().setContextProperty("backend", backend)
        engine.load(QUrl.fromLocalFile(str(Path(__file__).parent.parent / "puppeteer/qml/Main.qml")))
        self.assertTrue(engine.rootObjects(), self.messages)
        win = engine.rootObjects()[0]
        backend.refresh()
        pump(lambda: len(backend.containers) == 2)
        for index in range(5):
            self.assertIsNotNone(visual_find(win, "nav" + str(index)))
            QMetaObject.invokeMethod(visual_find(win, "nav" + str(index)), "clicked")
            pump(lambda: win.property("page") == index)
        QMetaObject.invokeMethod(visual_find(win, "nav0"), "clicked")
        QMetaObject.invokeMethod(win.findChild(QObject, "newEnvironment"), "clicked")
        dialog = win.findChild(QObject, "createDialog")
        pump(lambda: dialog.property("visible"))
        name = win.findChild(QObject, "createName")
        name.setProperty("text", "ubuntu-dev")
        QMetaObject.invokeMethod(win.findChild(QObject, "confirmCreate"), "clicked")
        self.assertTrue(dialog.property("visible"))
        self.assertTrue(backend.messageError)
        name.setProperty("text", "qt-created")
        QMetaObject.invokeMethod(win.findChild(QObject, "confirmCreate"), "clicked")
        pump(lambda: not backend.busy and any(c["name"] == "qt-created" for c in backend.containers))
        self.assertEqual(backend.selected["name"], "qt-created")
        QMetaObject.invokeMethod(win.findChild(QObject, "deleteEnvironment"), "clicked")
        confirmation = win.findChild(QObject, "deleteConfirmation")
        button = win.findChild(QObject, "confirmDelete")
        pump(lambda: win.findChild(QObject, "removeDialog").property("visible"))
        self.assertFalse(button.property("enabled"))
        confirmation.setProperty("text", "qt-created")
        pump(lambda: button.property("enabled"))
        QMetaObject.invokeMethod(button, "clicked")
        pump(lambda: not backend.busy and not any(c["name"] == "qt-created" for c in backend.containers))
        backend.setPreference("theme", "light")
        pump(lambda: not win.property("dark"))
        backend.setPreference("theme", "dark")
        backend.setPreference("language", "en")
        pump(lambda: win.property("dark"))
        self.assertEqual(visual_find(win, "nav0").property("text"), "Environments")
        win.setProperty("width", 1100)
        win.setProperty("height", 760)
        QGuiApplication.processEvents()
        time.sleep(.1)
        QGuiApplication.processEvents()
        target = os.environ.get("PUPPETEER_QA_IMAGE")
        if target:
            image = win.grabWindow()
            self.assertFalse(image.isNull())
            image.save(target)
        self.assertFalse([m for m in self.messages if "Unable to assign" in m or "ReferenceError" in m or "TypeError" in m or "Binding loop" in m], self.messages)
        win.close()
        backend._refresh_timer.stop()
        backend._poll_timer.stop()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_qprocess_failure_timeout_and_no_shell_execution(self):
        backend = Backend(demo=True)
        result = []
        backend._capture([sys.executable, "-c", "import sys; print('ok'); print('failure',file=sys.stderr); sys.exit(9)"], lambda *v: result.append(v))
        pump(lambda: result)
        self.assertEqual(result[0][0], 9)
        self.assertIn("ok", result[0][1])
        self.assertIn("failure", result[0][2])
        result.clear()
        backend._capture([sys.executable, "-c", "import time;time.sleep(10)"], lambda *v: result.append(v), timeout=50)
        pump(lambda: result)
        self.assertEqual(result[0][0], 124)
        result.clear()
        backend._capture(["/definitely/missing/program"], lambda *v: result.append(v))
        pump(lambda: result)
        self.assertEqual(result[0][0], 127)
        backend.deleteLater()

    def test_async_inventory_and_real_worker_using_fake_tools(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            tools = root / "bin"
            tools.mkdir()
            state = root / "state.json"
            state.write_text(json.dumps({"dev": {"running": True, "image": "docker.io/library/debian:stable"}}))
            program = '''import json,os,sys
from pathlib import Path
p=Path(os.environ['PUPPETEER_TEST_STATE'])
s=json.loads(p.read_text())
a=sys.argv[1:]
tool=Path(sys.argv[0]).name
assert os.environ.get('DBX_CONTAINER_MANAGER')=='podman'
if tool=='podman':
 print(json.dumps({'host':{'security':{'rootless':True}}}));sys.exit(0)
if a[0]=='list':
 print('ID | NAME | STATUS | IMAGE')
 for n,c in s.items():print('id-'+n+' | '+n+' | '+('Up' if c['running'] else 'Exited')+' | '+c['image'])
elif a[0]=='stop':s[a[-1]]['running']=False
elif a[0]=='create':
 n=a[a.index('--name')+1];s[n]={'running':False,'image':a[a.index('--image')+1]}
elif a[0]=='enter':
 n=a[a.index('--name')+1];s[n]['running']=True
elif a[0]=='rm':s.pop(a[-1])
else:sys.exit(5)
p.write_text(json.dumps(s))
'''
            for executable in ("distrobox", "podman"):
                path = tools / executable
                path.write_text("#!" + sys.executable + "\n" + program)
                path.chmod(0o755)
            env = {"PATH": str(tools) + os.pathsep + os.environ["PATH"], "XDG_DATA_HOME": str(root / "data"), "XDG_CONFIG_HOME": str(root / "config"), "PUPPETEER_TEST_STATE": str(state)}
            with patch.dict(os.environ, env):
                backend = Backend()
                backend.refresh()
                pump(lambda: not backend.refreshing)
                self.assertTrue(backend.host["ready"])
                self.assertTrue(backend.host["rootless"])
                self.assertEqual(backend.selected["name"], "dev")
                self.assertTrue(backend.containerAction("stop", ""))
                pump(lambda: not backend.busy and not backend.refreshing)
                self.assertFalse(backend.selected["running"])
                # Replace only terminal dispatch; the real worker and QProcess
                # still execute our temporary fixture programs.
                with patch("puppeteer.backend.terminal_command", side_effect=lambda command, preference: command):
                    self.assertTrue(backend.createContainer("new", "docker.io/library/ubuntu:24.04", True, False, False))
                    pump(lambda: not backend.busy and not backend.refreshing)
                self.assertTrue(any(c["name"] == "new" and c["running"] for c in backend.containers))
                self.assertEqual(backend.selected["name"], "new")
                self.assertTrue(list((root / "data/the-puppeteer/jobs").glob("*/job.json")))
                backend._poll_timer.stop()
                backend._refresh_timer.stop()
                backend.deleteLater()


if __name__ == "__main__":
    unittest.main()
