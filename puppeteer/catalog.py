"""Curated image choices and distro-specific development package recipes."""
import platform


CATALOG = [
    {"id": "ubuntu", "name": "Ubuntu", "version": "24.04 LTS", "image": "docker.io/library/ubuntu:24.04", "manager": "APT", "mark": "U", "versions": [
        {"label": "24.04 LTS", "image": "docker.io/library/ubuntu:24.04"},
        {"label": "26.04 LTS", "image": "docker.io/library/ubuntu:26.04"},
        {"label": "22.04 LTS", "image": "docker.io/library/ubuntu:22.04"}]},
    {"id": "fedora", "name": "Fedora", "version": "44", "image": "quay.io/fedora/fedora:44", "manager": "DNF", "mark": "F", "versions": [
        {"label": "44", "image": "quay.io/fedora/fedora:44"},
        {"label": "43", "image": "quay.io/fedora/fedora:43"},
        {"label": "42", "image": "quay.io/fedora/fedora:42"}]},
    {"id": "arch", "name": "Arch Linux", "version": "Rolling", "image": "docker.io/library/archlinux:latest", "manager": "Pacman", "mark": "A", "versions": [
        {"label": "latest", "image": "docker.io/library/archlinux:latest"}]},
    {"id": "debian", "name": "Debian", "version": "Stable", "image": "docker.io/library/debian:stable", "manager": "APT", "mark": "D", "versions": [
        {"label": "stable", "image": "docker.io/library/debian:stable"},
        {"label": "trixie", "image": "docker.io/library/debian:trixie"},
        {"label": "bookworm", "image": "docker.io/library/debian:bookworm"}]},
    {"id": "opensuse", "name": "openSUSE", "version": "Tumbleweed", "image": "registry.opensuse.org/opensuse/tumbleweed:latest", "manager": "Zypper", "mark": "S", "versions": [
        {"label": "Tumbleweed · latest", "image": "registry.opensuse.org/opensuse/tumbleweed:latest"}]},
]

TEMPLATES = [
    {"id": "none", "tr": "Temel ortam", "en": "Base environment"},
    {"id": "python", "tr": "Python geliştirme", "en": "Python development"},
    {"id": "cpp", "tr": "C / C++ geliştirme", "en": "C / C++ development"},
    {"id": "rust", "tr": "Rust geliştirme", "en": "Rust development"},
    {"id": "node", "tr": "Node.js geliştirme", "en": "Node.js development"},
]

RECIPES = {
    "python": {
        "ubuntu": "python3 python3-pip python3-venv python3-dev",
        "debian": "python3 python3-pip python3-venv python3-dev",
        "fedora": "python3 python3-pip python3-devel gcc",
        "arch": "python python-pip python-virtualenv",
        "opensuse": "python3 python3-pip python3-virtualenv python3-devel"},
    "cpp": {
        "ubuntu": "build-essential cmake ninja-build gdb",
        "debian": "build-essential cmake ninja-build gdb",
        "fedora": "gcc gcc-c++ make cmake ninja-build gdb",
        "arch": "base-devel cmake ninja gdb",
        "opensuse": "gcc gcc-c++ make cmake ninja gdb"},
    "rust": {
        "ubuntu": "rustc cargo pkg-config build-essential libssl-dev",
        "debian": "rustc cargo pkg-config build-essential libssl-dev",
        "fedora": "rust cargo pkgconf-pkg-config gcc openssl-devel",
        "arch": "rust base-devel pkgconf openssl",
        "opensuse": "rust cargo pkg-config gcc libopenssl-devel"},
    "node": {family: "nodejs npm" for family in ("ubuntu", "debian", "fedora", "arch", "opensuse")},
}


def native_platform() -> str:
    arch = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64", "amd64": "amd64"}.get(platform.machine().lower())
    return "linux/" + arch if arch else ""


def image_family(image: str) -> str:
    # Match a curated repository, never just a substring of an arbitrary URL.
    repository = image.split("@", 1)[0]
    if ":" in repository.rsplit("/", 1)[-1]:
        repository = repository.rsplit(":", 1)[0]
    if repository == "registry.fedoraproject.org/fedora":
        return "fedora"
    for distro in CATALOG:
        if any(repository == v["image"].rsplit(":", 1)[0] for v in distro["versions"]):
            return distro["id"]
    return ""


def template_packages(template: str, image: str) -> list[str]:
    if template == "none":
        return []
    if template not in RECIPES:
        raise ValueError("Bilinmeyen geliştirme şablonu.")
    family = image_family(image)
    if family not in RECIPES[template]:
        raise ValueError("Bu özel imaj için paket şablonu bilinmiyor. Temel ortamı seç veya paketleri kendin belirt.")
    return ["git", *RECIPES[template][family].split()]
