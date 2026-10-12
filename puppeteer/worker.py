"""Run a reviewed multi-step plan inside the user's external terminal.

Only the system package manager itself uses sudo. This Python worker is never
launched as root by the GUI. Status is written to a private job directory.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from .core import atomic_json, validate_runtime


def run_job(job_dir: Path, pause: bool = True) -> int:
    plan = json.loads((job_dir / "plan.json").read_text())
    env = os.environ.copy()
    env["DBX_CONTAINER_MANAGER"] = validate_runtime(plan["runtime"])
    env["DBX_NON_INTERACTIVE"] = "1"
    status_path = job_dir / "status.json"
    status = {"state": "running", "title": plan["title"], "step": "", "exit_code": None, "pid": os.getpid()}
    atomic_json(status_path, status)
    code = 0
    child = None

    def cancelled(_signum, _frame):
        nonlocal code
        code = 130
        if child is not None and child.poll() is None:
            child.terminate()
        raise KeyboardInterrupt

    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, cancelled)
    try:
        with (job_dir / "output.log").open("a", buffering=1) as log:
            for step in plan["steps"]:
                status["step"] = step["title"]
                atomic_json(status_path, status)
                print("\n" + step["title"], flush=True)
                log.write(step["title"] + "\n")
                argv = step["argv"]
                if not isinstance(argv, list) or not argv or not all(isinstance(value, str) and "\x00" not in value for value in argv):
                    raise ValueError("Invalid command vector")
                # Inherit the terminal's tty: sudo and distrobox prompts work.
                child = subprocess.Popen(argv, env=env)
                code = child.wait()
                log.write(f"exit={code}\n")
                if code != 0:
                    break
    except KeyboardInterrupt:
        code = 130
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    except (OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        status["error"] = str(error)
        code = 127
    finally:
        status.update(state="done" if code == 0 else "cancelled" if code == 130 else "failed", exit_code=code, finished_at=time.time())
        atomic_json(status_path, status)
    print("\nThe Puppeteer: " + ("işlem tamamlandı." if code == 0 else f"işlem başarısız / iptal edildi ({code})."), flush=True)
    if pause and sys.stdin.isatty():
        try:
            input("Pencereyi kapatmak için Enter… ")
        except (EOFError, KeyboardInterrupt):
            pass
    return code


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m puppeteer.worker JOB_DIRECTORY", file=sys.stderr)
        return 2
    return run_job(Path(sys.argv[1]))


if __name__ == "__main__":
    raise SystemExit(main())
