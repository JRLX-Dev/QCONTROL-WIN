"""CueControl launch helper: packages once, Main.py updates from GitHub.

Never writes into runtime\\python. Offline or a bad download starts the local copy.
Set CC_SKIP_UPDATE=1 to skip the GitHub check (booth / no-network).
"""
from __future__ import annotations

import ast
import hashlib
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime"
STAMP = RUNTIME / "pkgs.ok"
REQ = ROOT / "requirements.txt"
VERSION_FILE = ROOT / "VERSION.txt"
MAIN = ROOT / "Main.py"

REPO_RAW = "https://raw.githubusercontent.com/JRLX-Dev/QCONTROL-WIN/main"
TIMEOUT = 5


def _py() -> str:
    return sys.executable


def _read_version(text: str) -> str:
    line = (text or "").strip().splitlines()
    return line[0].strip() if line else "0"


def _ver_tuple(s: str):
    parts = []
    for bit in s.replace("-", ".").split("."):
        try:
            parts.append(int(bit))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CueControl-Windows-Updater"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def ensure_packages() -> None:
    if not REQ.is_file():
        return
    digest = hashlib.sha256(REQ.read_bytes()).hexdigest()
    if STAMP.is_file() and STAMP.read_text(encoding="utf-8", errors="ignore").strip() == digest:
        try:
            import PySide6  # noqa: F401
            return
        except Exception:
            pass
    print("Installing packages into runtime\\ (once per requirements change)...")
    import subprocess

    cmd = [_py(), "-m", "pip", "install", "-r", str(REQ)]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("ERROR: pip install failed. First run needs internet.")
        raise SystemExit(1)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(digest + "\n", encoding="utf-8")


def maybe_update_app() -> None:
    if os.environ.get("CC_SKIP_UPDATE", "").strip() in ("1", "true", "yes"):
        print("Updates skipped (CC_SKIP_UPDATE).")
        return
    if not MAIN.is_file():
        print("ERROR: Main.py missing.")
        raise SystemExit(1)
    local = _read_version(VERSION_FILE.read_text(encoding="utf-8", errors="ignore") if VERSION_FILE.is_file() else "0")
    try:
        remote_v = _read_version(_fetch(REPO_RAW + "/VERSION.txt").decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        print("No update check (offline or GitHub unreachable). Starting local copy.")
        print("  ", e.__class__.__name__)
        return
    if _ver_tuple(remote_v) <= _ver_tuple(local):
        print("CueControl", local, "— up to date.")
        return
    print("Update available:", local, "->", remote_v)
    print("Downloading Main.py from GitHub main...")
    try:
        body = _fetch(REPO_RAW + "/Main.py")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print("Download failed. Starting local copy.")
        print("  ", e)
        return
    try:
        ast.parse(body.decode("utf-8"))
    except SyntaxError as e:
        print("Download did not parse. Keeping local Main.py.")
        print("  ", e)
        return
    bak = ROOT / "Main.py.bak"
    tmp = ROOT / "Main.py.new"
    tmp.write_bytes(body)
    try:
        if MAIN.is_file():
            bak.write_bytes(MAIN.read_bytes())
        os.replace(tmp, MAIN)
        VERSION_FILE.write_text(remote_v + "\n", encoding="utf-8")
    finally:
        if tmp.is_file():
            tmp.unlink()
    print("Updated to", remote_v)


def main() -> int:
    os.chdir(ROOT)
    maybe_update_app()
    ensure_packages()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:
        print("Updater error (starting local copy):", e)
        raise SystemExit(0)
