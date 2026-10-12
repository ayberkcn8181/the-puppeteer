"""Qt-independent command planning, discovery and validation.

Every command is an argument vector. Display strings are never executed.
"""
from __future__ import annotations

import configparser
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
from dataclasses import dataclass, field, asdict
from typing import Callable


class ValidationError(ValueError):
    pass


@dataclass
class Step:
    title: str
    argv: list[str]


@dataclass
class Plan:
    title: str
    steps: list[Step]
    runtime: str = "podman"
    resource: str = ""
    interactive: bool = False
    metadata: dict = field(default_factory=dict)

    def payload(self) -> dict:
        return asdict(self)

    def preview(self) -> str:
        return "\n".join(shlex.join(step.argv) for step in self.steps)


CATALOG = [
    {"id": "ubuntu", "name": "Ubuntu", "version": "24.04 LTS", "image": "docker.io/library/ubuntu:24.04", "manager": "APT", "mark": "U"},
    {"id": "fedora", "name": "Fedora", "version": "Stable / latest", "image": "registry.fedoraproject.org/fedora:latest", "manager": "DNF", "mark": "F"},
    {"id": "arch", "name": "Arch Linux", "version": "Rolling", "image": "docker.io/library/archlinux:latest", "manager": "Pacman", "mark": "A"},
    {"id": "debian", "name": "Debian", "version": "Stable", "image": "docker.io/library/debian:stable", "manager": "APT", "mark": "D"},
    {"id": "opensuse", "name": "openSUSE", "version": "Tumbleweed", "image": "registry.opensuse.org/opensuse/tumbleweed:latest", "manager": "Zypper", "mark": "S"},
]

NAME_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}\Z")
IMAGE_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_./:@-]{0,511}\Z")
ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def validate_name(name: str) -> str:
    if not NAME_PATTERN.fullmatch(name):
        raise ValidationError("Ortam adı 1–63 karakter olmalı; harf/rakamla başlamalı ve yalnızca harf, rakam, nokta, tire veya alt çizgi içermeli.")
    return name


def validate_runtime(runtime: str) -> str:
    if runtime not in ("podman", "docker"):
        raise ValidationError("Desteklenmeyen konteyner motoru.")
    return runtime


def validate_image(image: str) -> str:
    if not IMAGE_PATTERN.fullmatch(image) or "/" not in image:
        raise ValidationError("Tam bir registry/imaj:sürüm adresi kullan.")
    return image


def data_home() -> Path:
    raw = os.environ.get("XDG_DATA_HOME", "")
    return (Path(raw) if raw and Path(raw).is_absolute() else Path.home() / ".local/share") / "the-puppeteer"


def config_home() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME", "")
    return (Path(raw) if raw and Path(raw).is_absolute() else Path.home() / ".config") / "the-puppeteer"


def default_home(name: str) -> str:
    return str(data_home() / "homes" / validate_name(name))


def parse_os_release(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            values = shlex.split(value, comments=False)
            result[key] = " ".join(values)
        except ValueError:
            continue
    return result


def host_profile(path: Path = Path("/etc/os-release")) -> dict:
    try:
        release = parse_os_release(path.read_text())
    except OSError:
        release = {}
    identities = [release.get("ID", ""), *release.get("ID_LIKE", "").split()]
    variant = release.get("VARIANT_ID", "")
    immutable = (Path("/run/ostree-booted").exists() or release.get("ID") in ("steamos", "bazzite", "ublue", "nixos", "aeon", "kalpa") or variant in ("silverblue", "kinoite", "sericea", "onyx"))
    family = next((family for family, ids in (("arch", {"arch", "cachyos", "manjaro"}), ("fedora", {"fedora", "rhel"}), ("debian", {"debian", "ubuntu", "linuxmint"}), ("opensuse", {"opensuse", "opensuse-leap", "opensuse-tumbleweed", "suse"})) if set(identities) & ids), "unknown")
    return {"name": release.get("PRETTY_NAME", "Linux"), "id": release.get("ID", "unknown"), "version": release.get("VERSION_ID", ""), "family": family, "immutable": immutable}


def installation_plan(host: dict, runtime: str, which: Callable = shutil.which) -> Plan:
    validate_runtime(runtime)
    if host.get("immutable") or host.get("family") == "unknown":
        raise ValidationError("Bu sistem için otomatik paket kurulumu sunulmuyor. Resmi dağıtım yönergesini kullan.")
    if runtime == "docker" and not which("docker"):
        raise ValidationError("Bu sürüm yeni Docker servisi yapılandırmaz. Podman seç veya Docker'ı resmi yönergeyle kur.")
    packages = []
    if not which("distrobox"):
        packages.append("distrobox")
    if runtime == "podman" and not which("podman"):
        packages.append("podman")
    if not packages:
        raise ValidationError("Gerekli komutlar zaten kurulu. Motor erişimini yeniden denetle.")
    manager, prefix = {
        "arch": ("pacman", ["-S", "--needed"]),
        "fedora": ("dnf", ["install"]),
        "debian": ("apt", ["install"]),
        "opensuse": ("zypper", ["install"]),
    }[host["family"]]
    binary = which(manager)
    sudo = which("sudo")
    if not binary or not sudo:
        raise ValidationError("Paket yöneticisi veya sudo bulunamadı.")
    return Plan("Distrobox kurulumu", [Step("Sistem paketleri kuruluyor", [sudo, "--", binary, *prefix, *packages])], runtime, "host-install", True)


def parse_list(output: str) -> list[dict]:
    """Parse documented pipe-separated output; reject unknown formats visibly."""
    output = ANSI_PATTERN.sub("", output)
    rows = []
    seen = set()
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("|")]
        if parts[0].upper() in ("ID", "CONTAINER ID"):
            continue
        if len(parts) != 4:
            raise ValidationError("Distrobox liste çıktısı tanınamadı. İşlem kaydını ve kurulu Distrobox sürümünü kontrol et.")
        ident, name, status, image = parts
        validate_name(name)
        if name in seen:
            raise ValidationError("Liste çıktısında yinelenen ortam adı var.")
        seen.add(name)
        rows.append({"id": ident, "name": name, "status": status, "running": status.lower().startswith(("up", "running")), "image": image, "home": "", "distro": image.split("/")[-1].split(":")[0], "runtime": "", "apps": []})
    return rows


class Commands:
    def __init__(self, runtime: str = "podman", binary: str = "distrobox"):
        self.runtime = validate_runtime(runtime)
        self.binary = binary

    def enter(self, name: str, command: list[str] | None = None, no_tty: bool = False) -> list[str]:
        argv = [self.binary, "enter", "--name", validate_name(name)]
        if no_tty:
            argv.append("--no-tty")
        return argv + (["--", *command] if command else [])

    def create(self, name: str, image: str, own_home: bool, developer: bool = False, nvidia: bool = False, existing: list[str] = ()) -> Plan:
        validate_name(name)
        validate_image(image)
        if name in existing:
            raise ValidationError("Bu ortam adı zaten kullanılıyor.")
        argv = [self.binary, "create", "--name", name, "--image", image, "--yes"]
        home = default_home(name) if own_home else str(Path.home())
        if own_home:
            argv += ["--home", home]
        if developer:
            argv += ["--additional-packages", "git cmake"]
        if nvidia:
            argv.append("--nvidia")
        return Plan(f"Oluşturma · {name}", [Step("İmaj ve konteyner oluşturuluyor", argv), Step("İlk açılış hazırlanıyor", self.enter(name, ["true"]))], self.runtime, name, True, {"home": home, "name": name, "image": image})

    def clone(self, source: str, name: str, own_home: bool, existing: list[str]) -> Plan:
        validate_name(source)
        validate_name(name)
        if source not in existing or name in existing:
            raise ValidationError("Kaynak ortam bulunamadı veya yeni ad zaten kullanılıyor.")
        argv = [self.binary, "create", "--clone", source, "--name", name, "--yes"]
        home = default_home(name) if own_home else str(Path.home())
        argv += ["--home", home]
        return Plan(f"Klonlama · {name}", [Step("Kaynak ortam klonlanıyor", argv), Step("Klon hazırlanıyor", self.enter(name, ["true"]))], self.runtime, source, True, {"name": name, "home": home})

    def action(self, action: str, name: str, confirmation: str = "", exports: list[str] = ()) -> Plan:
        validate_name(name)
        if action == "start":
            return Plan(f"Başlatma · {name}", [Step("Ortam başlatılıyor", self.enter(name, ["true"]))], self.runtime, name, True)
        if action == "stop":
            argv = [self.binary, "stop", "--yes", name]
        elif action == "upgrade":
            return Plan(f"Güncelleme · {name}", [Step("Paketler güncelleniyor", [self.binary, "upgrade", name])], self.runtime, name, True)
        elif action == "remove":
            if confirmation != name:
                raise ValidationError("Silme onayı için ortam adı eşleşmeli.")
            steps = [Step("Menü kısayolu kaldırılıyor", self.export(name, path, True).steps[0].argv) for path in exports]
            steps.append(Step("Konteyner siliniyor; ev dizini korunuyor", [self.binary, "rm", "--force", name]))
            return Plan(f"Silme · {name}", steps, self.runtime, name, True)
        else:
            raise ValidationError("Bilinmeyen işlem.")
        return Plan(f"Durdurma · {name}", [Step("Ortam durduruluyor", argv)], self.runtime, name)

    def export(self, name: str, path: str, delete: bool = False) -> Plan:
        validate_name(name)
        if not path.startswith("/") or not path.endswith(".desktop") or "\x00" in path or "\n" in path or ".." in PurePosixPath(path).parts:
            raise ValidationError("Geçersiz uygulama dosyası.")
        argv = self.enter(name, ["distrobox-export", "--app", path, *(["--delete"] if delete else [])], True)
        return Plan(("Kısayol kaldırma" if delete else "Menüye ekleme") + f" · {name}", [Step("Uygulama kısayolu düzenleniyor", argv)], self.runtime, name)


# This is a constant, portable discovery program. User inputs are never inserted.
DISCOVER_APPS = '''for directory in /usr/share/applications /usr/local/share/applications "$HOME/.local/share/applications"; do
  [ -d "$directory" ] || continue
  for entry in "$directory"/*.desktop; do
    [ -f "$entry" ] || continue
    printf '%s\\0' "$entry"
    cat -- "$entry"
    printf '\\0'
  done
done'''


def parse_apps(output: str, locale: str = "tr") -> list[dict]:
    blocks = output.split("\0")
    apps = []
    seen = set()
    for index in range(0, len(blocks) - 1, 2):
        path, contents = blocks[index:index + 2]
        if not path.startswith("/") or not path.endswith(".desktop") or "\n" in path or ".." in PurePosixPath(path).parts:
            continue
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        try:
            parser.read_string(contents)
            entry = parser["Desktop Entry"]
        except (configparser.Error, KeyError):
            continue
        if entry.get("Type") != "Application" or entry.get("Hidden", "false").lower() == "true" or entry.get("NoDisplay", "false").lower() == "true":
            continue
        name = entry.get(f"Name[{locale}]", entry.get("Name", ""))
        if not name or Path(path).name in seen:
            continue
        seen.add(Path(path).name)
        apps.append({"name": name, "path": path, "icon": entry.get("Icon", "application-x-executable"), "exported": False})
    return sorted(apps, key=lambda app: app["name"].casefold())


def exported_desktops(name: str, directory: Path | None = None) -> set[str]:
    """Recognize actual Distrobox launcher commands, never just substring names."""
    validate_name(name)
    if directory is None:
        directory = data_home().parent / "applications"
    result = set()
    for path in directory.glob("*.desktop"):
        try:
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            parser.optionxform = str
            parser.read_string(path.read_text())
            tokens = shlex.split(parser["Desktop Entry"].get("Exec", ""))
        except (OSError, ValueError, configparser.Error, KeyError):
            continue
        positions = [i for i, token in enumerate(tokens) if Path(token).name in ("distrobox-enter", "distrobox")]
        matched = False
        for i in positions:
            tail = tokens[i + 1:]
            if Path(tokens[i]).name == "distrobox" and (not tail or tail.pop(0) != "enter"):
                continue
            for j, value in enumerate(tail):
                if value in ("--", "-e"):
                    break
                if value in ("--name", "-n") and j + 1 < len(tail) and tail[j + 1] == name:
                    matched = True
                if j == 0 and value == name:
                    matched = True
        prefix = name + "-"
        if matched and path.name.startswith(prefix):
            result.add(path.name[len(prefix):])
    return result


TERMINALS = ("konsole", "gnome-terminal", "kgx", "kitty", "alacritty", "foot", "xterm", "x-terminal-emulator")


def terminal_command(command: list[str], preference: str = "auto", which: Callable = shutil.which) -> list[str]:
    choices = TERMINALS if preference == "auto" else (preference,)
    if any(choice not in TERMINALS for choice in choices):
        raise ValidationError("Desteklenmeyen terminal.")
    for name in choices:
        binary = which(name)
        if not binary:
            continue
        if name == "konsole":
            return [binary, "--separate", "-e", *command]
        if name in ("gnome-terminal", "kgx"):
            return [binary, "--", *command]
        if name == "kitty":
            return [binary, "--title", "The Puppeteer", *command]
        if name == "foot":
            return [binary, "--title=The Puppeteer", *command]
        return [binary, "-e", *command]
    raise ValidationError("Terminal bulunamadı. Konsole, GNOME Terminal, Kitty, Alacritty, Foot veya xterm kur.")


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    os.replace(temp, path)


def load_settings(path: Path | None = None) -> dict:
    settings = {"runtime": "podman", "terminal": "auto", "theme": "system", "language": "tr"}
    try:
        raw = json.loads((path or config_home() / "settings.json").read_text())
        if raw.get("runtime") in ("podman", "docker"):
            settings["runtime"] = raw["runtime"]
        if raw.get("terminal") in ("auto", *TERMINALS):
            settings["terminal"] = raw["terminal"]
        if raw.get("theme") in ("system", "dark", "light"):
            settings["theme"] = raw["theme"]
        if raw.get("language") in ("tr", "en"):
            settings["language"] = raw["language"]
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return settings
