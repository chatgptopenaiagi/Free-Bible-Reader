"""Ephemeral Linux-container runner: fresh venv, actual wheel, outside-source cwd."""
from pathlib import Path
import json
import os
import subprocess
import sys


def main():
    evidence = Path("/evidence")
    python = Path("/tmp/fbr-wheel-venv/bin/python")
    subprocess.run([sys.executable, "-m", "venv", str(python.parents[1])], check=True)
    # Copied into this disposable container, not installed from a Windows bind
    # mount: Docker Desktop may expose build-output NTFS modes as unreadable.
    wheel = Path("/tmp/free_bible_reader-0.3.0-py3-none-any.whl")
    wheel.chmod(0o644)
    with (evidence / "linux-install.log").open("w") as log:
        subprocess.run([str(python), "-m", "pip", "install", str(wheel) + "[documents,test]"], stdout=log, stderr=subprocess.STDOUT, check=True)
    outside = Path("/tmp/fbr-outside-source")
    outside.mkdir()
    version = subprocess.run([str(python.parent / "fbr"), "version"], cwd=outside, text=True, capture_output=True, check=True)
    assert version.stdout.strip() == "0.3.0"
    subprocess.run([str(python), "-m", "pip", "check"], cwd=outside, check=True)
    return subprocess.call([str(python), "/verification/verify_python.py", "--output", "/evidence/linux-wheel-verification.json"], cwd=outside)


if __name__ == "__main__":
    raise SystemExit(main())
