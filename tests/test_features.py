import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from puppeteer.catalog import CATALOG, RECIPES, image_family, native_platform, template_packages
from puppeteer.core import Commands, ValidationError, validate_packages
from puppeteer.diagnostics import diagnostic_checks
from puppeteer.manifests import parse_manifest, serialize_manifest


class FeatureTests(unittest.TestCase):
    def test_templates_use_distribution_specific_packages(self):
        for distro in CATALOG:
            for template in RECIPES:
                with self.subTest(distro=distro["id"], template=template):
                    packages = template_packages(template, distro["image"])
                    self.assertIn("git", packages)
                    self.assertEqual(validate_packages(packages), packages)
        self.assertIn("build-essential", template_packages("cpp", CATALOG[0]["image"]))
        self.assertIn("base-devel", template_packages("cpp", CATALOG[2]["image"]))
        self.assertIn("gcc-c++", template_packages("cpp", CATALOG[1]["image"]))
        self.assertEqual(image_family("example.org/not-ubuntu:latest"), "")
        with self.assertRaises(ValueError):
            template_packages("python", "example.org/ubuntu:latest")

    def test_package_option_and_shell_injection_is_rejected(self):
        for package in ("--privileged", "git;touch", "$(id)", "git\n", "https://x", "a b"):
            with self.subTest(package=package), self.assertRaises(ValidationError):
                Commands().create("test", CATALOG[0]["image"], True, packages=[package])
        plan = Commands().create("test", CATALOG[0]["image"], True, packages=["git", "git", "python3"])
        self.assertEqual(plan.metadata["packages"], ["git", "python3"])

    def test_manifest_round_trip_and_home_portability(self):
        with tempfile.TemporaryDirectory() as directory, patch("pathlib.Path.home", return_value=Path(directory)):
            definition = {"name": "python-work", "image": CATALOG[0]["image"], "packages": ["git", "python3"], "home": directory + "/My Homes/python", "nvidia": True, "start_now": True}
            text = serialize_manifest(definition)
            self.assertIn('${HOME}/My Homes/python', text)
            parsed = parse_manifest(text)[0]
            for key in definition:
                self.assertEqual(parsed[key], definition[key])
            argv = Commands().create(parsed["name"], parsed["image"], False, home=parsed["home"], packages=parsed["packages"]).steps[0].argv
            self.assertEqual(argv[argv.index("--home") + 1], definition["home"])

    def test_multiple_definitions_repeated_packages_and_comments(self):
        text = '[one] # comment\nimage="docker.io/library/debian:stable"\nadditional_packages="git cmake"\nadditional_packages=git\n[two]\nimage=docker.io/library/ubuntu:24.04\nstart_now=true\n'
        entries = parse_manifest(text)
        self.assertEqual([e["name"] for e in entries], ["one", "two"])
        self.assertEqual(entries[0]["packages"], ["git", "cmake"])
        self.assertFalse(entries[0]["start_now"])

    def test_unsupported_or_unsafe_manifests_fail_before_planning(self):
        prefix = "[test]\nimage=docker.io/library/ubuntu:24.04\n"
        for tail in ('init_hooks="touch /tmp/no"', 'root=true', 'replace=true', 'init=true', 'image=example.org/other:latest', 'home="$(id)"', 'additional_packages="git; touch /tmp/x"', 'volume=/host:/guest', 'nvidia=yes', '[test]\nimage=x/y:latest'):
            with self.subTest(tail=tail), self.assertRaises(ValidationError):
                parse_manifest(prefix + tail)
        for text in ("[missing]\n", "image=x/y:latest", "x" * (128 * 1024 + 1), prefix + "\0"):
            with self.assertRaises(ValidationError):
                parse_manifest(text)

    def test_import_checks_collisions_and_preserves_stopped_state(self):
        entry = parse_manifest("[work]\nimage=docker.io/library/debian:stable\nstart_now=false\n")[0]
        with self.assertRaises(ValidationError):
            Commands().create(entry["name"], entry["image"], False, existing=["work"])
        plan = Commands().create(entry["name"], entry["image"], False, start_now=entry["start_now"])
        self.assertEqual(plan.steps[-1].argv, ["distrobox", "stop", "--yes", "work"])
        self.assertNotIn("--rm-home", plan.preview())

    def test_exported_home_cannot_become_shell_code_in_distrobox_assemble(self):
        for home in ("/tmp/foo;id", "/tmp/$(id)", "/tmp/foo|id", "/tmp/foo'", "/tmp/foo#comment", "/tmp/foo\nbar"):
            with self.subTest(home=home), self.assertRaises(ValidationError):
                serialize_manifest({"name": "test", "image": CATALOG[0]["image"], "home": home})

    def test_cross_architecture_is_not_silently_emulated(self):
        if native_platform():
            plan = Commands().create("native", CATALOG[0]["image"], False, platform=native_platform())
            self.assertIn("--platform", plan.steps[0].argv)
        foreign = "linux/arm64" if native_platform() != "linux/arm64" else "linux/amd64"
        with self.assertRaises(ValidationError):
            Commands().create("foreign", CATALOG[0]["image"], False, platform=foreign)

    def test_diagnostics_distinguish_engine_inventory_and_terminal_failures(self):
        host = {"distrobox": True, "engineReady": True, "ready": False, "rootless": False, "inventoryError": "Unexpected output", "display": True, "family": "arch"}
        checks = {c["id"]: c for c in diagnostic_checks(host, "podman", "auto", "en", which=lambda _: None)}
        self.assertEqual(checks["engine"]["status"], "ok")
        self.assertEqual(checks["inventory"]["detail"], "Unexpected output")
        self.assertEqual(checks["terminal"]["status"], "error")
        self.assertEqual(checks["rootless"]["status"], "error")
        host.update(rootless=True, ready=True, inventoryError="")
        checks = {c["id"]: c for c in diagnostic_checks(host, "podman", "auto", "en", which=lambda name: "/bin/konsole" if name == "konsole" else None)}
        self.assertEqual(checks["rootless"]["status"], "ok")
        self.assertEqual(checks["terminal"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
