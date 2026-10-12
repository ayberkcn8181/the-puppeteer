import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from puppeteer.core import (Commands, ValidationError, atomic_json, exported_desktops,
                            installation_plan, load_settings, parse_apps, parse_list,
                            parse_os_release, terminal_command)
from puppeteer.worker import run_job


class CoreTests(unittest.TestCase):
    def test_shell_metacharacters_and_option_injection_rejected(self):
        for name in ("--all", "test;touch /tmp/unwanted", "$(whoami)", "bad\nname", "../a", "x" * 64):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                Commands().create(name, "docker.io/library/ubuntu:24.04", True)
        with self.assertRaises(ValidationError):
            Commands().create("valid", "--privileged", False)

    def test_duplicate_name_rejected_before_running(self):
        with self.assertRaises(ValidationError):
            Commands().create("existing", "docker.io/library/debian:stable", True, existing=["existing"])

    def test_create_preserves_paths_with_spaces_as_one_argument(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/Puppeteer Test"}):
            plan = Commands("docker").create("work", "docker.io/library/ubuntu:24.04", True, True)
        self.assertEqual(plan.steps[0].argv[plan.steps[0].argv.index("--home") + 1], "/tmp/Puppeteer Test/the-puppeteer/homes/work")
        self.assertEqual(plan.runtime, "docker")
        self.assertEqual(plan.steps[1].argv[-2:], ["--", "true"])

    def test_deletion_requires_exact_confirmation_and_preserves_home(self):
        with self.assertRaises(ValidationError):
            Commands().action("remove", "work", "other")
        plan = Commands().action("remove", "work", "work", ["/usr/share/applications/vlc.desktop"])
        self.assertEqual(len(plan.steps), 2)
        self.assertIn("--delete", plan.steps[0].argv)
        self.assertNotIn("--rm-home", plan.steps[-1].argv)
        self.assertNotIn("--all", plan.steps[-1].argv)

    def test_list_parser_avoids_generic_containers_and_fails_on_unknown_format(self):
        rows = parse_list("ID | NAME | STATUS | IMAGE\nabcd | dev | Up 2 hours | docker.io/library/ubuntu:24.04\ndefg | tools | Exited (0) | archlinux:latest\n")
        self.assertEqual([r["name"] for r in rows], ["dev", "tools"])
        self.assertTrue(rows[0]["running"])
        self.assertFalse(rows[1]["running"])
        with self.assertRaises(ValidationError):
            parse_list("Unrecognized output instead of a container list")

    def test_app_parser_filters_hidden_and_uses_localized_name(self):
        fixture = "/usr/share/applications/vlc.desktop\0[Desktop Entry]\nType=Application\nName=VLC\nName[tr]=VLC oynatıcı\nExec=vlc %U\n\0/usr/share/applications/hidden.desktop\0[Desktop Entry]\nType=Application\nName=Hidden\nNoDisplay=true\n\0"
        apps = parse_apps(fixture)
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["name"], "VLC oynatıcı")
        self.assertEqual(apps[0]["path"], "/usr/share/applications/vlc.desktop")

    def test_export_detection_matches_exact_container_name(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            (directory / "work-vlc.desktop").write_text("[Desktop Entry]\nExec=/usr/bin/distrobox-enter -n work -e vlc %U\n")
            (directory / "work-fake.desktop").write_text("[Desktop Entry]\nExec=echo work\n")
            (directory / "work-other.desktop").write_text("[Desktop Entry]\nExec=distrobox-enter -n work-other -e vlc\n")
            self.assertEqual(exported_desktops("work", directory), {"vlc.desktop"})

    def test_installation_reuses_components_and_blocks_immutable_system(self):
        installed = {"distrobox": "/usr/bin/distrobox", "sudo": "/usr/bin/sudo", "pacman": "/usr/bin/pacman"}
        plan = installation_plan({"family": "arch", "immutable": False}, "podman", installed.get)
        self.assertEqual(plan.steps[0].argv, ["/usr/bin/sudo", "--", "/usr/bin/pacman", "-S", "--needed", "podman"])
        with self.assertRaises(ValidationError):
            installation_plan({"family": "fedora", "immutable": True}, "podman", installed.get)
        with self.assertRaises(ValidationError):
            installation_plan({"family": "arch", "immutable": False}, "docker", installed.get)

    def test_terminal_argv_does_not_flatten_or_execute_shell_text(self):
        command = ["distrobox", "enter", "--name", "dev"]
        result = terminal_command(command, "konsole", lambda n: "/usr/bin/konsole" if n == "konsole" else None)
        self.assertEqual(result, ["/usr/bin/konsole", "--separate", "-e", *command])
        with self.assertRaises(ValidationError):
            terminal_command(command, "auto", lambda _: None)

    def test_os_release_is_parsed_without_evaluating_shell(self):
        parsed = parse_os_release('ID=cachyos\nID_LIKE="arch"\nPRETTY_NAME="Example $(id)"\n')
        self.assertEqual(parsed["PRETTY_NAME"], "Example $(id)")

    def test_corrupt_settings_fall_back_and_private_atomic_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"runtime":"unknown","terminal":"sh -c evil","theme":"dark"}')
            self.assertEqual(load_settings(path)["runtime"], "podman")
            self.assertEqual(load_settings(path)["terminal"], "auto")
            atomic_json(path, {"hello": "world"})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_worker_stops_on_failure_and_passes_runtime(self):
        import sys
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            result = directory / "marker"
            plan = {"runtime": "docker", "title": "Test", "steps": [
                {"title": "Runtime", "argv": [sys.executable, "-c", "import os;assert os.environ['DBX_CONTAINER_MANAGER']=='docker'"]},
                {"title": "Failure", "argv": [sys.executable, "-c", "raise SystemExit(7)"]},
                {"title": "Must not execute", "argv": [sys.executable, "-c", f"from pathlib import Path;Path({str(result)!r}).touch()"]}]}
            atomic_json(directory / "plan.json", plan)
            self.assertEqual(run_job(directory, pause=False), 7)
            self.assertFalse(result.exists())
            status = json.loads((directory / "status.json").read_text())
            self.assertEqual(status["exit_code"], 7)
            self.assertEqual(status["state"], "failed")


if __name__ == "__main__":
    unittest.main()
