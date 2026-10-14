"""Explain probe results without guessing at privileged host changes."""
from .core import terminal_command, ValidationError


def diagnostic_checks(host: dict, runtime: str, terminal: str, language: str = "tr", *, which=None, demo=False) -> list[dict]:
    def tr(turkish, english):
        return english if language == "en" else turkish
    checks = []
    def add(ident, title, status, detail):
        checks.append({"id": ident, "title": title, "status": status, "detail": detail})
    add("distrobox", "Distrobox", "ok" if host.get("distrobox") else "error", tr("Distrobox bulundu.", "Distrobox is installed.") if host.get("distrobox") else tr("Kurulum ekranındaki paket planını inceleyerek Distrobox'ı kur.", "Review the package plan on Setup to install Distrobox."))
    add("engine", runtime.title(), "ok" if host.get("engineReady", host.get("ready")) else "error", tr("Motor erişimi doğrulandı.", "Engine access verified.") if host.get("engineReady", host.get("ready")) else host.get("engineError") or tr("Motor eksik veya erişilemiyor. Kurulum ekranından denetle.", "Engine is missing or inaccessible. Check Setup."))
    if runtime == "podman":
        add("rootless", "Rootless Podman", "ok" if host.get("rootless") else "error", tr("Kullanıcı hesabıyla çalışma doğrulandı.", "Operation under the user account verified.") if host.get("rootless") else tr("Normal kullanıcıyla 'podman info' çalıştır. Hata çıktısına göre /etc/subuid ve /etc/subgid kayıtlarını ve rootless yönergesini kontrol et.", "Run 'podman info' as your normal user. Follow the error output and rootless instructions to check /etc/subuid and /etc/subgid."))
    try:
        argv = terminal_command(["true"], terminal, **({"which": which} if which else {}))
        detail = argv[0]
        status = "ok"
    except ValidationError:
        status = "error"
        detail = tr("Seçili terminal bulunamadı. Kurulum ekranında başka terminal seç veya Konsole/GNOME Terminal kur.", "Selected terminal not found. Select another on Setup or install Konsole/GNOME Terminal.")
    if demo:
        status, detail = "info", tr("Demo: terminal erişimi kullanılmaz.", "Demo: terminal access is not used.")
    add("terminal", tr("Terminal", "Terminal"), status, detail)
    add("inventory", tr("Ortam listesi", "Environment inventory"), "ok" if host.get("ready") else "error", host.get("inventoryError") or (tr("Liste biçimi ve motor doğrulandı.", "Inventory format and engine verified.") if host.get("ready") else tr("Distrobox ve motor hazır olduğunda yeniden denetle.", "Check again after Distrobox and the engine are ready.")))
    add("display", tr("Grafik oturumu", "Graphical session"), "ok" if host.get("display") else "warning", tr("X11/Wayland oturumu bulundu.", "X11/Wayland session found.") if host.get("display") else tr("DISPLAY/WAYLAND_DISPLAY bulunamadı. Grafik uygulamalarını masaüstü oturumundan çalıştır.", "DISPLAY/WAYLAND_DISPLAY not found. Run graphical apps from a desktop session."))
    if host.get("immutable") or host.get("family") == "unknown":
        add("installation", tr("Sistem paket kurulumu", "System package installation"), "info", tr("Bu sistem için dağıtımın kendi kurulum yönergesini kullan.", "Use this distribution's own installation instructions."))
    return checks
