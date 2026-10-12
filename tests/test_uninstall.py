import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from puppeteer.uninstall import (UninstallError, build_plan, execute, guarded_child,
                                launcher_owned, main, quoted_exec, require_inactive)


class UninstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source = self.base / "The Puppeteer source"
        self.source.mkdir()
        self.config = self.base / "config"
        self.data = self.base / "data"
        (self.source / "puppeteer").mkdir()
        (self.source / "run.sh").write_text("app launcher")
        (self.source / "puppeteer/app.py").write_text("application source")
        (self.source / "my-notes.txt").write_text("private notes")
        self.launcher = self.data / "applications/the-puppeteer.desktop"
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text("[Desktop Entry]\nName=The Puppeteer\nExec=" + quoted_exec(self.source / "run.sh") + "\n")
        self.home = self.data / "the-puppeteer/homes/dev"
        self.home.mkdir(parents=True)
        (self.home / "important.txt").write_text("container files")
        self.appconfig = self.config / "the-puppeteer"
        self.appconfig.mkdir(parents=True)
        (self.appconfig / "settings.json").write_text("{}")
        self.jobs = self.data / "the-puppeteer/jobs/job"
        self.jobs.mkdir(parents=True)
        (self.jobs / "output.log").write_text("job output")

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, **kwargs):
        return build_plan(self.source, self.config, self.data, {"found": False}, sys.executable, **kwargs)

    def test_default_removes_only_app_and_keeps_container_data_and_notes(self):
        execute(self.plan())
        self.assertFalse(self.launcher.exists())
        self.assertFalse((self.source / "puppeteer/app.py").exists())
        self.assertFalse((self.source / "run.sh").exists())
        self.assertTrue((self.source / "my-notes.txt").exists())
        self.assertTrue((self.home / "important.txt").exists())
        self.assertTrue((self.appconfig / "settings.json").exists())
        self.assertTrue((self.jobs / "output.log").exists())

    def test_empty_application_directory_under_user_home_is_removed(self):
        (self.source / "my-notes.txt").unlink()
        with patch("pathlib.Path.home", return_value=self.base):
            execute(self.plan())
        self.assertFalse(self.source.exists())
        self.assertTrue(self.base.exists())
        self.assertTrue((self.home / "important.txt").exists())

    def test_purge_keeps_homes_and_unrelated_application(self):
        unrelated = self.data / "applications/other.desktop"
        unrelated.write_text("other app")
        execute(self.plan(purge=True))
        self.assertFalse(self.appconfig.exists())
        self.assertFalse(self.jobs.parent.exists())
        self.assertTrue((self.home / "important.txt").exists())
        self.assertTrue(unrelated.exists())

    def test_launcher_from_another_checkout_is_preserved(self):
        self.launcher.write_text("[Desktop Entry]\nName=The Puppeteer\nExec=" + quoted_exec(self.base / "another/run.sh") + "\n")
        self.assertFalse(launcher_owned(self.launcher, self.source, False))
        execute(self.plan(keep_source=True))
        self.assertTrue(self.launcher.exists())

    def test_only_marked_private_environment_is_removed_automatically(self):
        env = self.source / ".venv"
        env.mkdir()
        (env / "pyvenv.cfg").write_text("home=/usr/bin")
        self.assertNotIn(env, self.plan().paths)
        (env / ".the-puppeteer-owned").write_text(json.dumps({"application": "the-puppeteer", "source": str(self.source)}))
        execute(self.plan(keep_source=True))
        self.assertFalse(env.exists())
        self.assertTrue((self.source / "puppeteer/app.py").exists())

    def test_explicit_old_venv_removal_and_symlink_target_preservation(self):
        external = self.base / "shared-python"
        external.mkdir()
        (external / "pyvenv.cfg").write_text("home=/usr/bin")
        (external / "keep.txt").write_text("shared")
        env = self.source / ".venv"
        env.symlink_to(external, target_is_directory=True)
        execute(self.plan(remove_venv=True, keep_source=True))
        self.assertFalse(env.is_symlink())
        self.assertTrue((external / "keep.txt").exists())

    def test_outside_parent_symlink_stops_plan_before_any_deletion(self):
        external = self.base / "unrelated"
        external.mkdir()
        (external / "app.py").write_text("must remain")
        (self.source / "puppeteer/app.py").unlink()
        (self.source / "puppeteer").rmdir()
        (self.source / "puppeteer").symlink_to(external, target_is_directory=True)
        with self.assertRaises(UninstallError):
            self.plan()
        self.assertTrue(self.launcher.exists())
        self.assertTrue((external / "app.py").exists())

    def test_purge_symlink_does_not_follow_into_homes(self):
        import shutil
        shutil.rmtree(self.jobs.parent)
        (self.data / "the-puppeteer/jobs").symlink_to(self.home, target_is_directory=True)
        execute(self.plan(purge=True, keep_source=True))
        self.assertTrue((self.home / "important.txt").exists())
        self.assertFalse((self.data / "the-puppeteer/jobs").is_symlink())

    def test_system_package_refused_and_pip_targets_only_the_app(self):
        info = {"found": True, "installer": "pip", "location": "/usr/lib/python/site-packages", "prefix": "/usr", "base_prefix": "/usr", "user_base": str(self.base / "user")}
        with self.assertRaises(UninstallError):
            build_plan(self.source, self.config, self.data, info, sys.executable)
        prefix = self.base / "python-venv"
        info.update(location=str(prefix / "lib/site-packages"), prefix=str(prefix))
        plan = build_plan(self.source, self.config, self.data, info, "/test/python")
        self.assertEqual(plan.pip_argv, ["/test/python", "-m", "pip", "uninstall", "--yes", "the-puppeteer"])

    def test_running_gui_lock_prevents_uninstall(self):
        (self.appconfig / "application.lock").write_text(str(os.getpid()) + "\nThe Puppeteer\nlocalhost\n")
        with self.assertRaises(UninstallError):
            require_inactive(self.config, self.data)
        self.assertTrue(self.launcher.exists())

    def test_custom_container_home_inside_purge_target_stops_before_deletion(self):
        (self.appconfig / "environments.json").write_text(json.dumps({"podman:dev": str(self.appconfig)}))
        with self.assertRaises(UninstallError):
            self.plan(purge=True)
        self.assertTrue(self.appconfig.exists())
        self.assertTrue(self.launcher.exists())

    def test_dry_run_cli_makes_no_changes(self):
        env = {"XDG_CONFIG_HOME": str(self.config), "XDG_DATA_HOME": str(self.data)}
        with patch.dict(os.environ, env), patch("puppeteer.uninstall.source_root", return_value=self.source), patch("puppeteer.uninstall.package_info", return_value={"found": False}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--dry-run", "--purge"]), 0)
        self.assertTrue(self.launcher.exists())
        self.assertTrue((self.source / "run.sh").exists())
        self.assertTrue((self.home / "important.txt").exists())
        self.assertTrue(self.appconfig.exists())

    def test_cancelled_prompt_and_failed_pip_do_not_delete_source(self):
        env = {"XDG_CONFIG_HOME": str(self.config), "XDG_DATA_HOME": str(self.data)}
        with patch.dict(os.environ, env), patch("puppeteer.uninstall.source_root", return_value=self.source), patch("puppeteer.uninstall.package_info", return_value={"found": False}), patch("os.geteuid", return_value=1000), patch("builtins.input", return_value="H"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([]), 0)
        self.assertTrue(self.launcher.exists())
        plan = self.plan()
        plan.pip_argv = ["fake-pip"]
        with patch("subprocess.run") as run:
            run.return_value.returncode = 1
            with self.assertRaises(UninstallError):
                execute(plan)
        self.assertTrue((self.source / "run.sh").exists())


if __name__ == "__main__":
    unittest.main()
