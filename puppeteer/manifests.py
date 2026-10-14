"""A reviewed, non-executable subset of Distrobox assemble INI manifests.

Never source an imported file or pass it to a shell. Unknown options fail closed.
"""
from pathlib import Path
import re
import shlex

from .core import ValidationError, validate_home, validate_image, validate_name, validate_packages


MAX_MANIFEST_BYTES = 128 * 1024
ALLOWED = {"image", "home", "additional_packages", "nvidia", "pull", "start_now", "root", "replace", "init"}
BOOLEANS = {"nvidia", "pull", "start_now", "root", "replace", "init"}


def parse_manifest(text: str) -> list[dict]:
    if len(text.encode("utf-8")) > MAX_MANIFEST_BYTES or "\0" in text:
        raise ValidationError("Ortam tanımı 128 KiB sınırını aşıyor veya geçersiz veri içeriyor.")
    definitions = []
    names = set()
    current = None
    seen = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        section = re.fullmatch(r"\[([^\]]+)\]\s*(?:[#;].*)?", line)
        if section:
            name = validate_name(section.group(1))
            if name in names or len(definitions) >= 16:
                raise ValidationError("Yinelenen ortam adı veya 16 ortam sınırı aşıldı.")
            names.add(name)
            current = {"name": name, "packages": [], "home": str(Path.home()), "nvidia": False, "pull": False, "start_now": False}
            definitions.append(current)
            seen = set()
            continue
        if current is None or "=" not in line:
            raise ValidationError(f"Satır {number}: [ortam-adı] ve anahtar=değer biçimi bekleniyor.")
        key, value = (p.strip() for p in line.split("=", 1))
        if key not in ALLOWED:
            raise ValidationError(f"Satır {number}: '{key}' desteklenmiyor. Hook, shell komutu ve gelişmiş seçenekler otomatik uygulanmaz.")
        if key in seen and key != "additional_packages":
            raise ValidationError(f"Satır {number}: '{key}' yinelenmiş.")
        seen.add(key)
        try:
            tokens = shlex.split(value, comments=True)
        except ValueError as error:
            raise ValidationError(f"Satır {number}: tırnaklar eşleşmiyor.") from error
        if key == "additional_packages":
            current["packages"] = validate_packages([*current["packages"], *" ".join(tokens).split()])
            continue
        if len(tokens) != 1:
            raise ValidationError(f"Satır {number}: tek değer belirt; boşluk içeren yolu tırnakla.")
        value = tokens[0]
        if key in BOOLEANS:
            if value not in ("true", "false"):
                raise ValidationError(f"Satır {number}: '{key}' true veya false olmalı.")
            if key in ("root", "replace", "init") and value == "true":
                raise ValidationError(f"Satır {number}: '{key}=true' bu içe aktarma akışında desteklenmiyor.")
            current[key] = value == "true"
        elif key == "image":
            current[key] = validate_image(value)
        elif key == "home":
            for prefix in ("${HOME}/", "$HOME/", "~/"):
                if value.startswith(prefix):
                    value = str(Path.home() / value[len(prefix):])
                    break
            if value in ("${HOME}", "$HOME", "~"):
                value = str(Path.home())
            current[key] = validate_home(value)
    if not definitions:
        raise ValidationError("Dosyada ortam tanımı bulunamadı.")
    for definition in definitions:
        if "image" not in definition:
            raise ValidationError(definition["name"] + ": imaj adresi eksik.")
    return definitions


def serialize_manifest(definition: dict, *, incomplete: bool = False) -> str:
    name = validate_name(definition["name"])
    image = validate_image(definition["image"])
    home = validate_home(definition.get("home") or str(Path.home()))
    packages = validate_packages(definition.get("packages", []))
    user_home = Path.home()
    if Path(home).is_relative_to(user_home):
        relative = Path(home).relative_to(user_home)
        home = "${HOME}" + ("/" + str(relative) if str(relative) != "." else "")
    lines = ["# The Puppeteer 0.2.0 · Distrobox assemble compatible subset",
             "# Definition only: personal files and container modifications are not backed up."]
    if incomplete:
        lines.append("# Original package/options recipe was not recorded; this exports a base environment.")
    lines += [f"[{name}]", f'image="{image}"', f'home="{home}"',
              'additional_packages="' + " ".join(packages) + '"',
              "nvidia=" + str(bool(definition.get("nvidia", False))).lower(),
              "pull=" + str(bool(definition.get("pull", False))).lower(),
              "start_now=" + str(bool(definition.get("start_now", True))).lower(),
              "root=false", "replace=false", "init=false", ""]
    return "\n".join(lines)
