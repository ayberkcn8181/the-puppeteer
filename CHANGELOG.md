# Changelog

## 0.2.0 — 2026-10-14

- Added diagnostics with separate engine, inventory, terminal and rootless checks, and a copyable report.
- Added distribution version selection and native platform reporting in the image catalog.
- Added Python, C/C++, Rust and Node.js recipes with distribution-specific package names and editable extra packages.
- Added reviewed INI definition import/export, local file dialogs, clipboard support and persistent creation recipes.
- Import only executes the selected entry, rejects unsupported options, checks name collisions and preserves `start_now=false` after initialization.
- Custom homes are recorded before a create attempt to preserve them during uninstall even if initialization fails.
- Extended uninstall coverage for new source files; containers and their homes remain protected.
- Added Qt/QML workflow tests, manifest validation tests, opt-in real Podman/Docker tests and GitHub Actions.

## 0.1.0

- Initial native Qt/QML release with purple themes, Distrobox management, installation planning, desktop app export, job tracking and scoped uninstall.
