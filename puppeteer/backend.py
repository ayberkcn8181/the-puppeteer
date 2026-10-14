"""Qt bridge: asynchronous host probes and real, reviewed Distrobox jobs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time
import uuid
import tempfile

from PySide6.QtCore import QObject, Property, QProcess, QProcessEnvironment, QTimer, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtCore import QUrl, Qt

from .core import (CATALOG, DISCOVER_APPS, Commands, Plan, Step, ValidationError,
                   atomic_json, config_home, data_home, default_home, exported_desktops,
                   host_profile, installation_plan, load_settings, parse_apps, parse_list,
                   terminal_command, validate_name)
from .catalog import TEMPLATES, native_platform, template_packages
from .diagnostics import diagnostic_checks
from .manifests import MAX_MANIFEST_BYTES, parse_manifest, serialize_manifest


class Backend(QObject):
    inventoryChanged = Signal()
    appsChanged = Signal()
    stateChanged = Signal()
    settingsChanged = Signal()
    jobsChanged = Signal()
    messageChanged = Signal()
    manifestChanged = Signal()

    def __init__(self, demo: bool = False, parent=None):
        super().__init__(parent)
        self._demo = demo
        self._settings = load_settings() if not demo else {"runtime": "podman", "terminal": "auto", "theme": "dark", "language": "tr"}
        if not demo and not (config_home() / "settings.json").exists() and not shutil.which("podman") and shutil.which("docker"):
            self._settings["runtime"] = "docker"
        self._containers = []
        self._apps = []
        self._selected = ""
        self._host = {"name": "Linux", "family": "unknown", "distrobox": False, "motor": False, "ready": False, "rootless": False, "display": False, "immutable": False, "engineError": ""}
        self._jobs = []
        self._processes = set()
        self._active_job = None
        self._active_process = None
        self._refreshing = False
        self._generation = 0
        self._message = ""
        self._error = False
        self._cancel_requested = False
        self._homes = {}
        self._definitions = {}
        self._manifest_text = ""
        self._manifest_entries = []
        self._manifest_error = ""
        self._demo_initialized = False
        self._demo_exports = set()
        if not demo:
            try:
                self._homes = json.loads((config_home() / "environments.json").read_text())
                if not isinstance(self._homes, dict):
                    self._homes = {}
            except (OSError, ValueError):
                pass
            try:
                path = config_home() / "definitions.json"
                if path.stat().st_size <= 1024 * 1024:
                    definitions = json.loads(path.read_text())
                    if isinstance(definitions, dict):
                        self._definitions = {k: v for k, v in definitions.items() if isinstance(v, dict)}
            except (OSError, ValueError):
                pass
            self._load_history()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(700)
        self._poll_timer.timeout.connect(self._poll_terminal)
        self._poll_timer.start()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(15000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self.settingsChanged.emit())

    @Property(bool, constant=True)
    def demo(self):
        return self._demo

    @Property("QVariantList", constant=True)
    def catalog(self):
        return CATALOG

    @Property("QVariantList", constant=True)
    def templates(self):
        return TEMPLATES

    @Property(str, constant=True)
    def nativePlatform(self):
        return native_platform()

    @Property("QVariantList", notify=stateChanged)
    def diagnostics(self):
        return diagnostic_checks(self._host, self.runtime, self.terminal, self.language, demo=self.demo)

    @Property(str, notify=manifestChanged)
    def manifestText(self):
        return self._manifest_text

    @Property(str, notify=manifestChanged)
    def manifestError(self):
        return self._manifest_error

    @Property("QVariantList", notify=manifestChanged)
    def manifestEntries(self):
        return self._manifest_entries

    @Property("QVariantList", notify=inventoryChanged)
    def containers(self):
        return self._containers

    @Property("QVariantMap", notify=inventoryChanged)
    def selected(self):
        return next((dict(c) for c in self._containers if c["name"] == self._selected), {})

    @Property("QVariantList", notify=appsChanged)
    def applications(self):
        return self._apps

    @Property("QVariantMap", notify=stateChanged)
    def host(self):
        return self._host

    @Property("QVariantList", notify=jobsChanged)
    def jobs(self):
        return list(reversed(self._jobs))

    @Property(bool, notify=stateChanged)
    def busy(self):
        return self._active_job is not None

    @Property(bool, notify=stateChanged)
    def refreshing(self):
        return self._refreshing

    @Property(str, notify=messageChanged)
    def message(self):
        return self._message

    @Property(bool, notify=messageChanged)
    def messageError(self):
        return self._error

    @Property(str, notify=settingsChanged)
    def runtime(self):
        return self._settings["runtime"]

    @Property(str, notify=settingsChanged)
    def language(self):
        return self._settings["language"]

    @Property(str, notify=settingsChanged)
    def theme(self):
        return self._settings["theme"]

    @Property(str, notify=settingsChanged)
    def terminal(self):
        return self._settings["terminal"]

    @Property(bool, notify=settingsChanged)
    def systemDark(self):
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    def _say(self, text: str, error: bool = False):
        self._message, self._error = text, error
        self.messageChanged.emit()

    def _persist_job(self, job):
        if self.demo:
            return
        try:
            directory = data_home() / "jobs" / job["id"]
            directory.mkdir(parents=True, mode=0o700, exist_ok=True)
            os.chmod(directory, 0o700)
            atomic_json(directory / "job.json", job)
        except OSError as error:
            job["log"] = (job["log"] + "\nHistory: " + str(error))[-150000:]

    def _load_history(self):
        for path in (data_home() / "jobs").glob("*/job.json"):
            try:
                if path.stat().st_size > 1024 * 1024:
                    continue
                job = json.loads(path.read_text())
                if not isinstance(job, dict) or not all(key in job for key in ("id", "title", "state", "stage", "log", "started", "runtime", "terminal")) or path.parent.name != job["id"]:
                    continue
                if job["state"] == "running":
                    try:
                        status = json.loads((path.parent / "status.json").read_text())
                    except (OSError, ValueError):
                        status = {}
                    if status.get("state") in ("done", "failed", "cancelled"):
                        job["state"] = "done" if status.get("state") == "done" else "failed"
                        job["stage"] = "Tamamlandı" if job["state"] == "done" else "İşlem başarısız / iptal edildi"
                    elif job["runtime"] == self.runtime and self._worker_alive(path.parent, status.get("pid")):
                        payload = json.loads((path.parent / "plan.json").read_text())
                        plan = Plan(payload["title"], [Step(s["title"], s["argv"]) for s in payload["steps"]], payload["runtime"], payload.get("resource", ""), payload.get("interactive", False), payload.get("metadata", {}))
                        self._active_job = {"job": job, "plan": plan, "directory": path.parent}
                    else:
                        job["state"], job["stage"] = "failed", "Önceki işlem durumu doğrulanamadı; ortamı denetle"
                float(job["started"])
                self._jobs.append(job)
            except (OSError, ValueError, TypeError, KeyError):
                continue
        self._jobs = sorted(self._jobs, key=lambda j: float(j["started"]))[-30:]

    @staticmethod
    def _worker_alive(directory, pid):
        if not isinstance(pid, int) or pid <= 0:
            return False
        try:
            args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            return b"puppeteer.worker" in args and str(directory).encode() in args
        except OSError:
            return False

    @Slot(str, str)
    def setPreference(self, key: str, value: str):
        choices = {"runtime": ("podman", "docker"), "language": ("tr", "en"), "theme": ("system", "dark", "light"), "terminal": ("auto", "konsole", "gnome-terminal", "kgx", "kitty", "alacritty", "foot", "xterm", "x-terminal-emulator")}
        if key not in choices or value not in choices[key] or (key == "runtime" and self.busy):
            return
        self._settings[key] = value
        try:
            if not self.demo:
                atomic_json(config_home() / "settings.json", self._settings)
        except OSError as error:
            self._say(str(error), True)
        self.settingsChanged.emit()
        self.stateChanged.emit()
        if key == "runtime":
            self._generation += 1
            self._refreshing = False
            self._containers, self._apps, self._selected = [], [], ""
            self.inventoryChanged.emit()
            self.appsChanged.emit()
            self.refresh()

    def _env(self, runtime: str | None = None) -> QProcessEnvironment:
        env = QProcessEnvironment.systemEnvironment()
        env.insert("DBX_CONTAINER_MANAGER", runtime or self.runtime)
        env.insert("DBX_NON_INTERACTIVE", "1")
        env.insert("LC_ALL", "C.UTF-8")
        return env

    @staticmethod
    def _detach(argv, env):
        process = QProcess()
        environment = QProcessEnvironment()
        for key, value in env.items():
            environment.insert(key, value)
        process.setProcessEnvironment(environment)
        process.setProgram(argv[0])
        process.setArguments(argv[1:])
        process.setStandardOutputFile(QProcess.nullDevice())
        process.setStandardErrorFile(QProcess.nullDevice())
        if not process.startDetached():
            raise OSError("Terminal başlatılamadı: " + process.errorString())

    def _capture(self, argv, callback, timeout=25000, output_callback=None):
        proc = QProcess(self)
        self._processes.add(proc)
        proc.setProcessEnvironment(self._env())
        stdout, stderr = bytearray(), bytearray()
        finished = False
        timed_out = False
        timer = QTimer(proc)
        timer.setSingleShot(True)

        def drain():
            out = bytes(proc.readAllStandardOutput())
            err = bytes(proc.readAllStandardError())
            stdout.extend(out)
            stderr.extend(err)
            if output_callback:
                output_callback((out + err).decode("utf-8", errors="replace"))
            if len(stdout) + len(stderr) > 8 * 1024 * 1024:
                proc.kill()

        def finish(code=127, *_):
            nonlocal finished
            if finished:
                return
            finished = True
            timer.stop()
            drain()
            if timed_out:
                stderr.extend(b"\nOperation timed out.")
                code = 124
            self._processes.discard(proc)
            callback(code, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"))
            proc.deleteLater()

        def error(error_code):
            if error_code == QProcess.ProcessError.FailedToStart:
                stderr.extend(proc.errorString().encode())
                finish()

        def expire():
            nonlocal timed_out
            timed_out = True
            proc.kill()

        proc.readyReadStandardOutput.connect(drain)
        proc.readyReadStandardError.connect(drain)
        proc.finished.connect(finish)
        proc.errorOccurred.connect(error)
        timer.timeout.connect(expire)
        proc.start(argv[0], argv[1:])
        timer.start(timeout)
        return proc

    @Slot()
    def refresh(self):
        if self.busy or self._refreshing:
            return
        if self.demo:
            if not self._demo_initialized:
                self._containers = [
                    {"name": "ubuntu-dev", "id": "demo1", "image": CATALOG[0]["image"], "distro": "Ubuntu", "status": "Up", "running": True, "home": default_home("ubuntu-dev"), "runtime": "podman"},
                    {"name": "arch-tools", "id": "demo2", "image": CATALOG[2]["image"], "distro": "Arch Linux", "status": "Exited", "running": False, "home": default_home("arch-tools"), "runtime": "podman"},
                ]
                self._demo_initialized = True
            self._host = {"name": "CachyOS · Demo", "family": "arch", "distrobox": True, "motor": True, "ready": True, "engineReady": True, "rootless": True, "engineError": "", "version": "Demo", "display": True, "immutable": False}
            if not self._selected:
                self._selected = self._containers[0]["name"]
            self.inventoryChanged.emit()
            self.stateChanged.emit()
            return
        self._generation += 1
        generation = self._generation
        runtime = self.runtime
        self._refreshing = True
        self._host = {**host_profile(), "distrobox": bool(shutil.which("distrobox")), "motor": bool(shutil.which(runtime)), "ready": False, "engineReady": False, "rootless": False, "display": bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")), "engineError": "", "inventoryError": "", "version": ""}
        self.stateChanged.emit()

        def done():
            if generation != self._generation:
                return
            self._refreshing = False
            self.stateChanged.emit()

        if not self._host["distrobox"] or not self._host["motor"]:
            self._containers = []
            self._apps = []
            self.inventoryChanged.emit()
            self.appsChanged.emit()
            done()
            return
        info = [runtime, "info", "--format", "json" if runtime == "podman" else "{{json .}}"]

        def motor_done(code, output, error):
            if generation != self._generation:
                return
            if code:
                self._host["engineError"] = error.strip() or output.strip() or "Motor erişimi doğrulanamadı."
                self._containers, self._apps = [], []
                self.inventoryChanged.emit()
                self.appsChanged.emit()
                done()
                return
            try:
                details = json.loads(output)
                if runtime == "podman":
                    self._host["rootless"] = bool(details.get("host", details.get("Host", {})).get("security", {}).get("rootless", False))
                else:
                    self._host["rootless"] = "name=rootless" in details.get("SecurityOptions", [])
            except (ValueError, AttributeError, TypeError):
                self._host["engineError"] = "Motor bilgisi JSON biçiminde okunamadı."
                done()
                return
            self._host["ready"] = True
            self._host["engineReady"] = True
            self._capture(["distrobox", "list", "--no-color"], list_done)

        def list_done(code, output, error):
            if generation != self._generation:
                return
            if code:
                self._host["ready"] = False
                self._host["inventoryError"] = error.strip() or output.strip() or "Ortamlar okunamadı."
                self._containers, self._apps = [], []
                self.inventoryChanged.emit()
                self.appsChanged.emit()
                self._say(error.strip() or output.strip() or "Ortamlar okunamadı.", True)
                done()
                return
            try:
                rows = parse_list(output)
            except ValidationError as error:
                self._host["ready"] = False
                self._host["inventoryError"] = str(error)
                self._containers, self._apps = [], []
                self.inventoryChanged.emit()
                self.appsChanged.emit()
                self._say(str(error), True)
                done()
                return
            for row in rows:
                row["runtime"] = runtime
                row["home"] = self._homes.get(runtime + ":" + row["name"], "")
            self._containers = rows
            if not any(c["name"] == self._selected for c in rows):
                self._selected = rows[0]["name"] if rows else ""
                self._apps = []
                self.appsChanged.emit()
            self.inventoryChanged.emit()
            done()

        self._capture(info, motor_done)

    @Slot(str)
    def selectContainer(self, name: str):
        if any(c["name"] == name for c in self._containers) and self._selected != name:
            self._selected = name
            self._apps = []
            self.inventoryChanged.emit()
            self.appsChanged.emit()

    def _commands(self):
        return Commands(self.runtime)

    def _names(self):
        return [c["name"] for c in self._containers]

    def _require_selected(self):
        if self._selected not in self._names():
            raise ValidationError("Bir ortam seç.")
        return self._selected

    @Slot(str, str, bool, bool, bool, result=str)
    def createPreview(self, name, image, own_home, developer, nvidia):
        try:
            return self._commands().create(name, image, own_home, developer, nvidia, self._names()).preview()
        except ValidationError as error:
            return str(error)

    @Slot(str, result=str)
    def homePreview(self, name):
        try:
            return default_home(name)
        except ValidationError:
            return ""

    @Slot(str, str, bool, bool, bool, result=bool)
    def createContainer(self, name, image, own_home, developer, nvidia):
        try:
            return self._start(self._commands().create(name, image, own_home, developer, nvidia, self._names()))
        except (ValidationError, OSError) as error:
            self._say(str(error), True)
            return False

    def _profile_plan(self, name, image, own_home, template, extra, nvidia):
        packages = [*template_packages(template, image), *extra.split()]
        return self._commands().create(name, image, own_home, nvidia=nvidia, existing=self._names(), packages=packages, platform=self.nativePlatform)

    @Slot(str, str, bool, str, str, bool, result=str)
    def profilePreview(self, name, image, own_home, template, extra, nvidia):
        try:
            return self._profile_plan(name, image, own_home, template, extra, nvidia).preview()
        except ValueError as error:
            return str(error)

    @Slot(str, str, bool, str, str, bool, result=bool)
    def createProfile(self, name, image, own_home, template, extra, nvidia):
        try:
            return self._start(self._profile_plan(name, image, own_home, template, extra, nvidia))
        except (ValueError, OSError) as error:
            self._say(str(error), True)
            return False

    @Slot(str, str, str, result=str)
    def packagePreview(self, template, image, extra):
        try:
            from .core import validate_packages
            return " ".join(validate_packages([*template_packages(template, image), *extra.split()])) or "—"
        except ValueError as error:
            return str(error)

    @Slot(str, result=bool)
    def reviewManifest(self, text):
        self._manifest_text = text
        try:
            self._manifest_entries = parse_manifest(text)
            self._manifest_error = ""
        except ValueError as error:
            self._manifest_entries = []
            self._manifest_error = str(error)
        self.manifestChanged.emit()
        return bool(self._manifest_entries)

    @Slot(str)
    def editManifest(self, text):
        self._manifest_text = text
        self.clearManifestReview()

    @Slot()
    def clearManifestReview(self):
        self._manifest_entries = []
        self._manifest_error = ""
        self.manifestChanged.emit()

    def _manifest_plan(self, index):
        if index < 0 or index >= len(self._manifest_entries):
            raise ValidationError("Önce ortam tanımını incele ve bir ortam seç.")
        entry = self._manifest_entries[index]
        return self._commands().create(entry["name"], entry["image"], False, nvidia=entry["nvidia"], existing=self._names(), packages=entry["packages"], home=entry["home"], pull=entry["pull"], start_now=entry["start_now"])

    @Slot(int, result=str)
    def manifestPreview(self, index):
        try:
            return self._manifest_plan(index).preview()
        except ValueError as error:
            return str(error)

    @Slot(int, result=bool)
    def canImport(self, index):
        try:
            self._manifest_plan(index)
            return True
        except ValueError:
            return False

    @Slot(int, result=bool)
    def importEnvironment(self, index):
        try:
            return self._start(self._manifest_plan(index))
        except (ValueError, OSError) as error:
            self._say(str(error), True)
            return False

    @Slot(result=bool)
    def exportDefinition(self):
        try:
            name = self._require_selected()
            entry = self._definitions.get(self.runtime + ":" + name)
            known = bool(entry and entry.get("image") == self.selected.get("image"))
            if not known:
                entry = {"name": name, "image": self.selected["image"], "home": self.selected.get("home") or str(Path.home())}
            if not self.reviewManifest(serialize_manifest(entry, incomplete=not known)):
                return False
            self._say("Ortam tarifi hazır; kişisel dosyalar ve sonradan kurulan paketler bu dosyada yer almaz.")
            return True
        except (ValueError, OSError, KeyError) as error:
            self._say(str(error), True)
            return False

    @staticmethod
    def _local_file(value):
        url = QUrl(value)
        if url.isLocalFile():
            return Path(url.toLocalFile())
        if not url.scheme() and Path(value).is_absolute():
            return Path(value)
        raise ValidationError("Yalnızca yerel, mutlak dosya yolları destekleniyor.")

    @Slot(str, result=bool)
    def loadManifestFile(self, value):
        try:
            path = self._local_file(value)
            with path.open("rb") as handle:
                content = handle.read(MAX_MANIFEST_BYTES + 1)
            if len(content) > MAX_MANIFEST_BYTES:
                raise ValidationError("Dosya 128 KiB sınırını aşıyor.")
            return self.reviewManifest(content.decode("utf-8-sig"))
        except (ValueError, OSError) as error:
            self.clearManifestReview()
            self._say(str(error), True)
            return False

    @Slot(str, str, result=bool)
    def saveManifestFile(self, value, text):
        if self.demo:
            self._say("Demo: dosya yazılmaz; metni kopyalayabilirsin.")
            return False
        temp = None
        try:
            parse_manifest(text)
            path = self._local_file(value)
            if path.is_symlink():
                raise ValidationError("Bağlantı olan dosyanın üzerine yazılmaz.")
            fd, temp = tempfile.mkstemp(prefix=".puppeteer-", dir=path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(temp, path)
            self._say("Ortam tanımı kaydedildi: " + str(path))
            return True
        except (ValueError, OSError) as error:
            self._say(str(error), True)
            return False
        finally:
            if temp and Path(temp).exists():
                Path(temp).unlink()

    @Slot(str)
    def copyText(self, text):
        QGuiApplication.clipboard().setText(text)

    @Slot(result=str)
    def diagnosticReport(self):
        rows = ["The Puppeteer 0.2.0", "Host: " + self._host.get("name", "Linux"), "Engine: " + self.runtime, "Platform: " + self.nativePlatform]
        rows += [f'[{c["status"]}] {c["title"]}: {c["detail"]}' for c in self.diagnostics]
        return "\n".join(rows)

    @Slot(str, bool, result=bool)
    def cloneContainer(self, name, own_home):
        try:
            source = self._require_selected()
            if self.selected.get("running"):
                raise ValidationError("Tutarlı bir klon için önce kaynak ortamı durdur.")
            return self._start(self._commands().clone(source, name, own_home, self._names()))
        except (ValidationError, OSError) as error:
            self._say(str(error), True)
            return False

    @Slot(str, str, result=bool)
    def containerAction(self, action, confirmation):
        try:
            name = self._require_selected()
            exports = [a["path"] for a in self._apps if a.get("exported")] if action == "remove" else []
            # Removal can proceed without discovering apps; only known exports
            # are cleaned. The UI makes this scope explicit.
            return self._start(self._commands().action(action, name, confirmation, exports))
        except (ValidationError, OSError) as error:
            self._say(str(error), True)
            return False

    @Slot(str, result=bool)
    def exportApp(self, path):
        try:
            name = self._require_selected()
            app = next((a for a in self._apps if a["path"] == path), None)
            if app is None:
                raise ValidationError("Uygulama seçili ortamda keşfedilmedi.")
            return self._start(self._commands().export(name, path, app["exported"]))
        except (ValidationError, OSError) as error:
            self._say(str(error), True)
            return False

    @Slot()
    def discoverApps(self):
        if self.busy or self._refreshing:
            return
        try:
            name = self._require_selected()
        except ValidationError as error:
            self._say(str(error), True)
            return
        if self.demo:
            self._apps = [{"name": "VLC", "path": "/usr/share/applications/vlc.desktop", "exported": False}, {"name": "Gedit", "path": "/usr/share/applications/org.gnome.gedit.desktop", "exported": False}]
            for app in self._apps:
                app["exported"] = (name, app["path"]) in self._demo_exports
            self.appsChanged.emit()
            return
        generation = self._generation
        self._refreshing = True
        self.stateChanged.emit()

        def finished(code, output, error):
            if generation != self._generation:
                return
            self._refreshing = False
            if name == self._selected:
                if code:
                    self._say(error.strip() or "Uygulamalar okunamadı. Önce terminalde ilk açılışı tamamla.", True)
                else:
                    exported = exported_desktops(name)
                    self._apps = parse_apps(output, self.language)
                    for app in self._apps:
                        app["exported"] = Path(app["path"]).name in exported
                    self.appsChanged.emit()
                    self._say(f"{len(self._apps)} grafik uygulama bulundu.")
            self.stateChanged.emit()

        self._capture(self._commands().enter(name, ["sh", "-c", DISCOVER_APPS], True), finished, 60000)

    @Slot(result=str)
    def installPreview(self):
        if self.demo:
            return "sudo pacman -S --needed distrobox podman"
        try:
            return installation_plan(self._host, self.runtime).preview()
        except ValidationError as error:
            return str(error)

    @Slot(result=bool)
    def installDependencies(self):
        try:
            plan = installation_plan(self._host, self.runtime) if not self.demo else Plan("Demo kurulum", [Step("Demo", ["true"])], self.runtime, "host-install", True)
            return self._start(plan, install=True)
        except (ValidationError, OSError) as error:
            self._say(str(error), True)
            return False

    @Slot()
    def openDocumentation(self):
        QDesktopServices.openUrl(QUrl("https://distrobox.it/compatibility/"))

    @Slot()
    def openTerminal(self):
        try:
            name = self._require_selected()
            if self.demo:
                self._say("Demo: terminal komutu " + " ".join(self._commands().enter(name)))
                return
            env = os.environ.copy()
            env["DBX_CONTAINER_MANAGER"] = self.runtime
            argv = terminal_command(self._commands().enter(name), self.terminal)
            self._detach(argv, env)
            self._say(name + " için terminal açıldı.")
        except (ValidationError, OSError) as error:
            self._say(str(error), True)

    def _start(self, plan: Plan, install=False):
        if self.busy or self._refreshing:
            raise ValidationError("Mevcut işlem veya denetim tamamlanınca yeniden dene.")
        if not install and not self._host.get("ready"):
            raise ValidationError("Önce Kurulum ekranında Distrobox ve motor erişimini hazırla.")
        if not self.demo and self.runtime == "podman" and not install and not self._host.get("rootless"):
            raise ValidationError("Podman rootless çalışma doğrulanamadı. Motor yapılandırmasını kontrol et.")
        if plan.metadata.get("home"):
            # Protect custom homes even if first initialization fails after
            # the container was created. A failed attempt remains recorded.
            self._homes[plan.runtime + ":" + plan.metadata["name"]] = plan.metadata["home"]
            if not self.demo:
                atomic_json(config_home() / "environments.json", self._homes)
        ident = uuid.uuid4().hex
        job = {"id": ident, "title": plan.title, "state": "running", "stage": plan.steps[0].title, "log": plan.preview(), "terminal": plan.interactive, "started": time.time(), "runtime": plan.runtime}
        self._jobs.append(job)
        self._jobs = self._jobs[-30:]
        self._active_job = {"job": job, "plan": plan, "directory": None}
        self._cancel_requested = False
        self._persist_job(job)
        self.stateChanged.emit()
        self.jobsChanged.emit()
        if self.demo:
            QTimer.singleShot(350, lambda: self._demo_finish(plan))
            return True
        if plan.interactive:
            try:
                directory = data_home() / "jobs" / ident
                directory.mkdir(parents=True, mode=0o700, exist_ok=True)
                os.chmod(directory, 0o700)
                atomic_json(directory / "plan.json", plan.payload())
                self._active_job["directory"] = directory
                command = [sys.executable, "-m", "puppeteer.worker", str(directory)]
                argv = terminal_command(command, self.terminal)
                env = os.environ.copy()
                env["PYTHONPATH"] = str(Path(__file__).parent.parent) + os.pathsep + env.get("PYTHONPATH", "")
                self._detach(argv, env)
                self._say("İşlem terminalde çalışıyor. Sonuç bu pencerede yeniden denetlenecek.")
            except (OSError, ValidationError) as error:
                self._finish_job(127, str(error))
                return False
        else:
            self._run_step(0)
        return True

    def _run_step(self, index):
        active = self._active_job
        if active is None:
            return
        plan = active["plan"]
        if index >= len(plan.steps):
            self._finish_job(0)
            return
        step = plan.steps[index]
        active["job"]["stage"] = step.title
        self.jobsChanged.emit()

        def output(text):
            active["job"]["log"] = (active["job"]["log"] + "\n" + text)[-150000:]
            self.jobsChanged.emit()

        def finished(code, stdout, stderr):
            self._active_process = None
            if code:
                self._finish_job(code, stderr or stdout)
            else:
                self._run_step(index + 1)

        self._active_process = self._capture(step.argv, finished, 120000, output)

    def _poll_terminal(self):
        active = self._active_job
        if active is None or active["directory"] is None:
            return
        try:
            status = json.loads((active["directory"] / "status.json").read_text())
        except (OSError, ValueError):
            if time.time() - active["job"]["started"] > 40:
                self._finish_job(127, "Terminal işçisi başlamadı. Terminal tercihini ve Python ortamını kontrol et.")
            return
        active["job"]["stage"] = status.get("step", "")
        self.jobsChanged.emit()
        if status.get("state") in ("done", "failed", "cancelled"):
            self._finish_job(status.get("exit_code", 127), status.get("error", ""))
        elif status.get("state") == "running" and not self._worker_alive(active["directory"], status.get("pid")):
            self._finish_job(130, "Terminal işçisi kapandı. Tamamlanmış değişiklikler geri alınmaz; ortam tekrar denetleniyor.")

    @Slot()
    def cancelJob(self):
        active = self._active_job
        if active is None:
            return
        self._cancel_requested = True
        if self.demo:
            self._finish_job(130, "Demo işlemi iptal edildi.")
        elif self._active_process is not None:
            proc = self._active_process
            proc.terminate()
            QTimer.singleShot(5000, lambda: proc.kill() if proc in self._processes else None)
        elif active["directory"] is not None:
            try:
                status = json.loads((active["directory"] / "status.json").read_text())
                if self._worker_alive(active["directory"], status.get("pid")):
                    os.kill(status["pid"], signal.SIGTERM)
                    self._say("İptal istendi. Tamamlanan değişiklikler geri alınmaz.")
                else:
                    self._say("İşçi henüz doğrulanamadı. Terminalde Ctrl+C ile iptal edebilirsin.", True)
            except (OSError, ValueError, KeyError) as error:
                self._say(str(error), True)

    def _finish_job(self, code, error=""):
        active = self._active_job
        if active is None:
            return
        if self._cancel_requested:
            code = 130
        active["job"].update(state="done" if code == 0 else "failed", stage="Tamamlandı" if code == 0 else f"Hata ({code})")
        if error:
            active["job"]["log"] += "\n" + error
        plan = active["plan"]
        if code == 0 and plan.metadata.get("home"):
            self._homes[plan.runtime + ":" + plan.metadata["name"]] = plan.metadata["home"]
            self._selected = plan.metadata["name"]
            if not self.demo:
                try:
                    atomic_json(config_home() / "environments.json", self._homes)
                except OSError as error:
                    active["job"]["log"] += "\n" + str(error)
            if "packages" in plan.metadata and "image" in plan.metadata:
                self._definitions[plan.runtime + ":" + plan.metadata["name"]] = plan.metadata
                if not self.demo:
                    try:
                        atomic_json(config_home() / "definitions.json", self._definitions)
                    except OSError as error:
                        active["job"]["log"] += "\n" + str(error)
        if code == 0 and plan.title.startswith("Silme"):
            self._definitions.pop(plan.runtime + ":" + plan.resource, None)
            if not self.demo:
                try:
                    atomic_json(config_home() / "definitions.json", self._definitions)
                except OSError as error:
                    active["job"]["log"] += "\n" + str(error)
        self._persist_job(active["job"])
        self._active_job = None
        self._active_process = None
        self._say("İşlem tamamlandı. Ortamlar yeniden denetleniyor." if code == 0 else (error.strip() or f"İşlem başarısız ({code}). Ayrıntılar İşlemler ekranında."), code != 0)
        self.jobsChanged.emit()
        self.stateChanged.emit()
        self.refresh()
        if code == 0 and (plan.title.startswith("Menüye") or plan.title.startswith("Kısayol")):
            # Refresh is asynchronous: wait until inventory verification ends.
            QTimer.singleShot(1500, self.discoverApps)

    def _demo_finish(self, plan):
        if self._active_job is None:
            return
        if "name" in plan.metadata:
            name = plan.metadata["name"]
            running = plan.metadata.get("start_now", True)
            self._containers.append({"name": name, "id": "demo-" + name, "image": plan.metadata.get("image", self.selected.get("image", "demo")), "distro": "Demo", "status": "Up" if running else "Exited", "running": running, "home": plan.metadata["home"], "runtime": self.runtime})
            self._selected = name
        elif plan.title.startswith("Silme"):
            self._containers = [c for c in self._containers if c["name"] != plan.resource]
            self._selected = self._containers[0]["name"] if self._containers else ""
        elif plan.title.startswith(("Başlatma", "Durdurma")):
            for c in self._containers:
                if c["name"] == plan.resource:
                    c["running"] = plan.title.startswith("Başlatma")
        elif plan.title.startswith(("Menüye", "Kısayol")):
            argv = plan.steps[0].argv
            path = argv[argv.index("--app") + 1]
            if "--delete" in argv:
                self._demo_exports.discard((plan.resource, path))
            else:
                self._demo_exports.add((plan.resource, path))
        self._finish_job(0)
        self.inventoryChanged.emit()
