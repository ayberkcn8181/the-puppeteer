"""Opt-in real-container smoke test. Never scans or removes unrelated containers."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import uuid

from puppeteer.catalog import native_platform, template_packages
from puppeteer.core import Commands, parse_list
from puppeteer.manifests import parse_manifest, serialize_manifest


@unittest.skipUnless(os.environ.get("PUPPETEER_LIVE_TESTS") == "1", "Set PUPPETEER_LIVE_TESTS=1 to create real test containers")
class LiveContainerTests(unittest.TestCase):
    def test_profile_create_manifest_stop_remove_and_home_preservation(self):
        self.assertNotEqual(os.geteuid(), 0, "Run live tests as a normal user")
        runtime = os.environ.get("PUPPETEER_TEST_RUNTIME", "podman")
        commands = Commands(runtime)
        self.assertTrue(shutil.which("distrobox"), "Distrobox is required")
        self.assertTrue(shutil.which(runtime), "Container engine is required")
        env = {**os.environ, "DBX_CONTAINER_MANAGER": runtime, "DBX_NON_INTERACTIVE": "1", "LC_ALL": "C.UTF-8"}
        def run(argv, timeout=600):
            result = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=timeout)
            self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
            return result.stdout
        # Verify access before claiming ownership of any generated test name.
        info = json.loads(run([runtime, "info", "--format", "json" if runtime == "podman" else "{{json .}}"], 30))
        if runtime == "podman":
            self.assertTrue(info["host"]["security"]["rootless"], "Rootless Podman required")
        name = "puppeteer-test-" + uuid.uuid4().hex[:12]
        self.assertNotIn(name, [row["name"] for row in parse_list(run(["distrobox", "list", "--no-color"], 30))])
        with tempfile.TemporaryDirectory(prefix="puppeteer-live-") as raw:
            home = Path(raw) / "Home With Spaces"
            home.mkdir()
            marker = home / "preserve.txt"
            marker.write_text("personal files")
            image = "docker.io/library/ubuntu:24.04"
            recipe = {"name": name, "image": image, "home": str(home), "packages": template_packages("python", image), "start_now": False}
            imported = parse_manifest(serialize_manifest(recipe))[0]
            plan = commands.create(name, image, False, packages=imported["packages"], home=imported["home"], start_now=False, platform=native_platform())
            # CI should not generate desktop launchers in the runner's home.
            plan.steps[0].argv.append("--no-entry")
            created = False
            try:
                # The UUID was checked absent; cleanup is scoped to this one name.
                created = True
                for step in plan.steps:
                    run(step.argv)
                rows = parse_list(run(["distrobox", "list", "--no-color"], 30))
                container = next(row for row in rows if row["name"] == name)
                self.assertFalse(container["running"])
                run(commands.enter(name, ["python3", "-c", "import venv; print('python-profile-ready')"], no_tty=True))
                run(commands.action("stop", name).steps[0].argv, 60)
                run(commands.action("remove", name, name).steps[-1].argv, 60)
                created = False
                self.assertTrue(marker.exists(), "Container removal must preserve home files")
            finally:
                if created:
                    subprocess.run(["distrobox", "rm", "--force", name], env=env, timeout=60, check=False)


if __name__ == "__main__":
    unittest.main()
