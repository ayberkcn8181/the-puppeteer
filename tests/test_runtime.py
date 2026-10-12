"""Launcher regressions using isolated Python processes; no GUI or pip writes."""
import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from puppeteer import app


ROOT = Path(__file__).resolve().parent.parent
QT_SYMBOLS = {
    "QtCore": "QTimer QUrl QLockFile",
    "QtGui": "QGuiApplication QIcon",
    "QtQml": "QQmlApplicationEngine",
    "QtQuick": "QQuickWindow",
    "QtQuickControls2": "QQuickStyle",
}


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="puppeteer runtime ")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.project = self.base / "project with spaces"
        for name in ("setup.sh", "run.sh", "packaging/python-runtime.sh", "puppeteer/runtime.py", "puppeteer/__init__.py"):
            destination = self.project / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
        (self.project / "puppeteer/__main__.py").write_text(
            "import json, os, sys\n"
            "print(json.dumps([os.environ['TEST_RUNTIME'], sys.argv[1:]]))\n"
        )
        self.path_bin = self.base / "bin"
        self.path_bin.mkdir()
        self.env = dict(os.environ, PATH=str(self.path_bin) + os.pathsep + os.environ["PATH"])

    def interpreter(self, path, label, *, missing=None, library_error=False):
        modules = self.base / (label + " modules")
        package = modules / "PySide6"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
        for module, names in QT_SYMBOLS.items():
            if module == missing:
                continue
            contents = "\n".join(name + " = object()" for name in names.split())
            if module == "QtQml" and library_error:
                contents = "raise OSError('libQt6Qml.so.6: cannot open shared object file')"
            (package / (module + ".py")).write_text(contents + "\n")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "#!/bin/sh\n"
            f"export PYTHONPATH={shlex.quote(str(modules))}\n"
            f"export TEST_RUNTIME={shlex.quote(label)}\n"
            f"exec {shlex.quote(sys.executable)} -S \"$@\"\n"
        )
        path.chmod(0o755)
        return path

    def run_script(self, name, *args):
        return subprocess.run(
            [str(self.project / name), *args], env=self.env, cwd=self.base,
            text=True, capture_output=True, timeout=20,
        )

    def test_incomplete_venv_does_not_hide_working_path_python(self):
        self.interpreter(self.project / ".venv/bin/python", "venv", missing="QtQuickControls2")
        system = self.interpreter(self.path_bin / "python3", "system")
        setup = self.run_script("setup.sh")
        self.assertEqual(setup.returncode, 0, setup.stderr)
        self.assertIn(str(system), setup.stdout)
        run = self.run_script("run.sh", "--demo", "argument with spaces")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), ["system", ["--demo", "argument with spaces"]])

    def test_setup_and_run_prefer_complete_venv(self):
        venv = self.interpreter(self.project / ".venv/bin/python", "venv")
        self.interpreter(self.path_bin / "python3", "system")
        setup = self.run_script("setup.sh")
        self.assertEqual(setup.returncode, 0, setup.stderr)
        self.assertIn(str(venv), setup.stdout)
        run = self.run_script("run.sh", "--demo")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), ["venv", ["--demo"]])

    def test_broken_venv_symlink_falls_back(self):
        venv = self.project / ".venv/bin/python"
        venv.parent.mkdir(parents=True)
        venv.symlink_to(self.base / "removed-python")
        self.interpreter(self.path_bin / "python3", "system")
        run = self.run_script("run.sh", "--demo")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)[0], "system")

    def test_namespace_import_is_insufficient(self):
        python = self.interpreter(self.path_bin / "python3", "partial", missing="QtQuickControls2")
        namespace = subprocess.run([str(python), "-c", "import PySide6"], env=self.env, capture_output=True)
        self.assertEqual(namespace.returncode, 0)
        check = subprocess.run([str(python), "-m", "puppeteer.runtime"], cwd=self.project,
                               env=self.env, text=True, capture_output=True)
        self.assertEqual(check.returncode, 2)
        self.assertIn("PySide6.QtQuickControls2", check.stderr)
        self.assertIn("Python:", check.stderr)

    def test_shared_library_error_is_preserved(self):
        python = self.interpreter(self.path_bin / "python3", "broken", library_error=True)
        check = subprocess.run([str(python), "-m", "puppeteer.runtime"], cwd=self.project,
                               env=self.env, text=True, capture_output=True)
        self.assertEqual(check.returncode, 2)
        self.assertIn("OSError: libQt6Qml.so.6", check.stderr)


class StartupDiagnosticsTests(unittest.TestCase):
    def test_direct_startup_displays_underlying_qt_error(self):
        for error in (ImportError("missing QtQuickControls2"), OSError("missing libQt6Qml.so.6")):
            with self.subTest(error=error), patch.object(app, "load_qt", side_effect=error), \
                    patch.object(sys, "argv", ["the-puppeteer", "--demo"]):
                output = io.StringIO()
                with contextlib.redirect_stderr(output):
                    self.assertEqual(app.main(), 2)
                self.assertIn(str(error), output.getvalue())
                self.assertIn(sys.executable, output.getvalue())


if __name__ == "__main__":
    unittest.main()
