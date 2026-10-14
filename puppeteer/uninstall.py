"""Scoped removal of The Puppeteer; containers and their homes are untouched."""
from __future__ import annotations

import argparse
import configparser
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


class UninstallError(Exception):
    pass


@dataclass
class RemovalPlan:
    paths: list[Path] = field(default_factory=list)
    pip_argv: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    parents: list[Path] = field(default_factory=list)
    protected: list[Path] = field(default_factory=list)
    home_tree: Path | None = None


SOURCE_FILES = (
    "README.md", "LICENSE", "MANIFEST.in", "pyproject.toml", "requirements.txt",
    "run.sh", "setup.sh", "uninstall.sh", ".gitignore",
    "packaging/install-launcher.py", "tests/test_core.py", "tests/test_qt.py", "tests/test_uninstall.py", "tests/test_features.py", "tests/test_live.py",
    "puppeteer/__init__.py", "puppeteer/__main__.py", "puppeteer/app.py",
    "puppeteer/backend.py", "puppeteer/core.py", "puppeteer/worker.py", "puppeteer/uninstall.py",
    "puppeteer/catalog.py", "puppeteer/diagnostics.py", "puppeteer/manifests.py",
    "puppeteer/qml/__init__.py", "puppeteer/qml/Main.qml", "puppeteer/qml/logo.svg",
    "CHANGELOG.md", "examples/python-work.ini", ".github/workflows/test.yml",
)


def xdg_base(variable: str, fallback: str) -> Path:
    raw = os.environ.get(variable, "")
    return (Path(raw) if raw and Path(raw).is_absolute() else Path.home() / fallback).resolve()


def source_root() -> Path | None:
    root = Path(__file__).resolve().parent.parent
    try:
        contents = (root / "pyproject.toml").read_text()
        if re.search(r'^name\s*=\s*["\']the-puppeteer["\']\s*$', contents, re.MULTILINE):
            return root
    except OSError:
        pass
    return None


def quoted_exec(path: Path) -> str:
    value = str(path).replace("%", "%%").replace("\\", "\\\\")
    for char in ('"', '$', '`'):
        value = value.replace(char, "\\" + char)
    return '"' + value.replace("\\", "\\\\") + '"'


def guarded_child(base: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise UninstallError("Kaldırma yolu uygulama kapsamının dışında.")
    path = base / rel
    # Leaf symlinks are unlinked, never followed. Parent symlinks outside the
    # approved base would otherwise let unlink() affect unrelated directories.
    if not path.parent.resolve().is_relative_to(base.resolve()):
        raise UninstallError("Dış dizine yönlenen bağlantı nedeniyle kaldırma durduruldu: " + str(path))
    return path


def launcher_owned(path: Path, source: Path | None, pip_install: bool) -> bool:
    if path.is_symlink():
        return False
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read_string(path.read_text())
        entry = parser["Desktop Entry"]
    except (OSError, configparser.Error, KeyError):
        return False
    if entry.get("Name") != "The Puppeteer":
        return False
    command = entry.get("Exec", "")
    return (source is not None and command == quoted_exec(source / "run.sh")) or (pip_install and command == "the-puppeteer")


def package_info(python: str) -> dict:
    program = '''import importlib.metadata as m,json,site,sys
try:
 d=m.distribution("the-puppeteer")
 print(json.dumps({"found":True,"location":str(d.locate_file("")),"installer":(d.read_text("INSTALLER") or "").strip(),"prefix":sys.prefix,"base_prefix":sys.base_prefix,"user_base":site.getuserbase()}))
except m.PackageNotFoundError:
 print(json.dumps({"found":False}))'''
    try:
        result = subprocess.run([python, "-c", program], capture_output=True, text=True, timeout=15, check=True, cwd="/")
        information = json.loads(result.stdout)
        if not isinstance(information, dict):
            raise ValueError("Invalid package metadata")
        return information
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise UninstallError("Seçili Python kurulumu denetlenemedi: " + str(error)) from error


def require_inactive(config: Path, data: Path) -> None:
    lock = config / "the-puppeteer/application.lock"
    try:
        pid = int(lock.read_text().splitlines()[0])
        if pid > 0:
            os.kill(pid, 0)
            raise UninstallError("The Puppeteer açık görünüyor. Kaldırmadan önce uygulamayı kapat.")
    except (FileNotFoundError, ProcessLookupError, ValueError, IndexError):
        pass
    except PermissionError as error:
        raise UninstallError("Uygulama kilidi denetlenemedi; kaldırma yapılmadı.") from error
    for path in (data / "the-puppeteer/jobs").glob("*/status.json"):
        try:
            status = json.loads(path.read_text())
            if status.get("state") != "running":
                continue
            pid = status.get("pid")
            if not isinstance(pid, int) or pid <= 0:
                continue
            args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            if b"puppeteer.worker" in args and str(path.parent).encode() in args:
                raise UninstallError("Konteyner veya kurulum işlemi sürüyor. Önce tamamlanmasını bekle veya uygulamadan iptal et.")
        except (OSError, ValueError, AttributeError):
            continue


def build_plan(source: Path | None, config: Path, data: Path, info: dict, python: str,
               purge: bool = False, keep_source: bool = False, remove_venv: bool = False) -> RemovalPlan:
    plan = RemovalPlan()
    plan.home_tree = (data / "the-puppeteer/homes").resolve()
    plan.protected = [Path.home().resolve(), plan.home_tree]
    try:
        homes = json.loads((config / "the-puppeteer/environments.json").read_text())
        if isinstance(homes, dict):
            plan.protected += [Path(value).resolve() for value in homes.values() if isinstance(value, str) and Path(value).is_absolute()]
    except (OSError, ValueError):
        pass
    if source is not None:
        source = source.resolve()
        if source in (Path("/"), Path.home().resolve(), config.resolve(), data.resolve()):
            raise UninstallError("Ana dizinden veya geniş sistem dizininden kaynak dosyaları kaldırılmaz.")
    env = guarded_child(source, ".venv") if source else None
    remove_environment = False
    if env is not None and (env.exists() or env.is_symlink()):
        if env.is_symlink():
            if remove_venv:
                plan.paths.append(env)
            else:
                plan.notes.append(".venv bir bağlantı; hedefi korunacak. Bağlantıyı da kaldırmak için --remove-venv kullan.")
        else:
            marker = env / ".the-puppeteer-owned"
            try:
                ownership = json.loads(marker.read_text())
            except (OSError, ValueError):
                ownership = {}
            if not isinstance(ownership, dict):
                ownership = {}
            if (ownership.get("application") == "the-puppeteer" and ownership.get("source") == str(source)) or (remove_venv and (env / "pyvenv.cfg").is_file()):
                plan.paths.append(env)
                remove_environment = True
            else:
                plan.notes.append("İşaretsiz/eski .venv korunacak. Uygulamaya özel olduğunu biliyorsan --remove-venv kullan.")

    found = bool(info.get("found"))
    if found and source is not None and info.get("location") == str(source) and not info.get("installer"):
        found = False  # setuptools source metadata is not an installed package.
    if found:
        try:
            location = Path(info["location"]).resolve()
            prefix = Path(info["prefix"]).resolve()
            base_prefix = Path(info["base_prefix"]).resolve()
            user_base = Path(info["user_base"]).resolve()
        except (KeyError, TypeError) as error:
            raise UninstallError("Paket kurulumu konumu doğrulanamadı.") from error
        covered = remove_environment and location.is_relative_to(env)
        if not covered:
            user_owned = (prefix != base_prefix and location.is_relative_to(prefix)) or location.is_relative_to(user_base)
            if info.get("installer") != "pip" or not user_owned:
                raise UninstallError("The Puppeteer sistem paket yöneticisine ait veya sistem Python'unda kurulu. Bu betik o kurulumu değiştirmez; kurduğun paket yöneticisiyle kaldır.")
            plan.pip_argv = [python, "-m", "pip", "uninstall", "--yes", "the-puppeteer"]

    launcher = guarded_child(data, "applications/the-puppeteer.desktop")
    if launcher_owned(launcher, source, found):
        plan.paths.append(launcher)
    elif launcher.exists() or launcher.is_symlink():
        plan.notes.append("Menü kısayolu bu kurulumla eşleşmiyor; korunacak.")

    if source is not None and not keep_source:
        for relative in SOURCE_FILES:
            path = guarded_child(source, relative)
            if path.is_file() or path.is_symlink():
                plan.paths.append(path)
        for relative in ("dist", "the_puppeteer.egg-info", "build/lib/puppeteer", "puppeteer/__pycache__", "puppeteer/qml/__pycache__", "tests/__pycache__", "packaging/__pycache__"):
            directory = guarded_child(source, relative)
            if directory.is_symlink():
                plan.notes.append("Bağlantı olan önbellek dizini korunacak: " + str(directory))
                continue
            if not directory.is_dir():
                continue
            for path in directory.rglob("*"):
                if not path.is_file() and not path.is_symlink():
                    continue
                rel = path.relative_to(source)
                guarded_child(source, str(rel))
                if relative == "dist" and not path.name.startswith("the_puppeteer-"):
                    continue
                if relative.endswith("__pycache__") and path.suffix != ".pyc":
                    continue
                if relative == "build/lib/puppeteer" and not (path.suffix in (".py", ".pyc", ".qml", ".svg")):
                    continue
                plan.paths.append(path)
                plan.parents.append(path.parent)
        plan.parents += [guarded_child(source, rel) for rel in ("puppeteer/qml", "puppeteer", "tests", "packaging", "examples", ".github/workflows", ".github", "dist", "build/lib", "build", "the_puppeteer.egg-info")]
        plan.parents.append(source)
    if purge:
        # Deliberately avoid data/the-puppeteer itself: it contains homes.
        plan.paths += [guarded_child(config, "the-puppeteer"), guarded_child(data, "the-puppeteer/jobs")]
    plan.paths = list(dict.fromkeys(plan.paths))
    for path in plan.paths:
        if path.is_symlink() or not path.is_dir():
            continue
        target = path.resolve()
        if any(home == target or home.is_relative_to(target) for home in plan.protected):
            raise UninstallError("Kaldırma kapsamı bir konteyner ev dizinini içeriyor; işlem yapılmadı: " + str(path))
    return plan


def execute(plan: RemovalPlan) -> None:
    if plan.pip_argv:
        result = subprocess.run(plan.pip_argv, check=False)
        if result.returncode:
            raise UninstallError("Pip kaldırma başarısız; kaynak dosyaları silinmedi.")
    for path in plan.paths:
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    for directory in sorted(set(plan.parents), key=lambda p: len(p.parts), reverse=True):
        target = directory.resolve()
        if (directory.is_symlink()
                or any(home == target or home.is_relative_to(target) for home in plan.protected)
                or (plan.home_tree is not None and target.is_relative_to(plan.home_tree))):
            continue
        try:
            directory.rmdir()
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The Puppeteer'ı kaldır; Distrobox ve konteyner ev dizinlerini koru.")
    parser.add_argument("--dry-run", action="store_true", help="Yalnızca kaldırma planını göster")
    parser.add_argument("--yes", action="store_true", help="Kaldırma planını soru sormadan uygula")
    parser.add_argument("--purge", action="store_true", help="Uygulama ayarlarını ve işlem kayıtlarını da kaldır; homes korunur")
    parser.add_argument("--keep-source", action="store_true", help="Kaynak kod klasöründeki dosyaları koru")
    parser.add_argument("--remove-venv", action="store_true", help="İşaretsiz eski .venv'i de kaldır; başka bağımlılıklar içeriyorsa kullanma")
    parser.add_argument("--python", default=sys.executable, help="Wheel kurulumunun Python yorumlayıcısı")
    args = parser.parse_args(argv)
    try:
        if os.geteuid() == 0 and not args.dry_run:
            raise UninstallError("Betiği normal kullanıcı hesabından çalıştır; sudo kullanma.")
        config, data = xdg_base("XDG_CONFIG_HOME", ".config"), xdg_base("XDG_DATA_HOME", ".local/share")
        require_inactive(config, data)
        python = shutil.which(args.python) or args.python
        plan = build_plan(source_root(), config, data, package_info(python), python,
                          args.purge, args.keep_source, args.remove_venv)
        print("The Puppeteer kaldırma planı:")
        if plan.pip_argv:
            print("  Python paketini kaldır:", " ".join(plan.pip_argv))
        for path in plan.paths:
            if path.exists() or path.is_symlink():
                print("  Sil:", path)
        for note in plan.notes:
            print("  " + note)
        print("Distrobox, Podman/Docker, sistem PySide6 paketi ve konteyner ev dizinleri korunur.")
        if args.dry_run:
            print("Önizleme: hiçbir değişiklik yapılmadı.")
            return 0
        if not plan.paths and not plan.pip_argv:
            print("Kaldırılacak uygulama kurulumu bulunamadı.")
            return 0
        if not args.yes:
            try:
                confirmed = input("Bu kaldırma planı uygulansın mı? [e/H] ").strip().lower() in ("e", "evet", "y", "yes")
            except (EOFError, KeyboardInterrupt):
                confirmed = False
            if not confirmed:
                print("Kaldırma iptal edildi.")
                return 0
        execute(plan)
        print("The Puppeteer kaldırıldı.")
        return 0
    except (UninstallError, OSError) as error:
        print("Kaldırma tamamlanmadı: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
