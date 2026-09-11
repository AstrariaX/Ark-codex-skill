#!/usr/bin/env python3
"""Create a project-local venv and install the deskpet dependencies."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run(cmd):
    print("RUN", " ".join(str(x) for x in cmd))
    subprocess.check_call(cmd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project", help="deskpet project directory")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--skip-browser",
        action="store_true",
        help="skip downloading Playwright Chromium (use system Chrome instead)",
    )
    args = parser.parse_args()

    venv = Path(args.project) / ".venv"
    # Preserve existing environments on failure; permission errors do not
    # imply Python incompatibility.
    try:
        run([args.python, "-m", "venv", str(venv)])
    except subprocess.CalledProcessError:
        sys.exit("venv/ensurepip failed. Check the preceding error and directory permissions; the existing environment was preserved.")
    py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(py), "-m", "pip", "install", "PySide6", "playwright"])
    if not args.skip_browser:
        run([str(py), "-m", "playwright", "install", "chromium"])
    print("environment ready at", venv)


if __name__ == "__main__":
    main()
