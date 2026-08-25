"""Assemble dist/CueControl-Portable from the PyInstaller COLLECT output."""
from __future__ import annotations

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    src = os.path.join(HERE, "dist", "CueControl")
    kit = os.path.join(HERE, "dist", "CueControl-Portable")
    if not os.path.isdir(src):
        print("ERROR: dist/CueControl not found. Run PyInstaller first.")
        return 1
    if os.path.isdir(kit):
        shutil.rmtree(kit)
    shutil.copytree(src, kit)

    for name in ("VERSION.txt", "CUECONTROL_PORTABLE.txt", "README-USB.txt"):
        p = os.path.join(HERE, name)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(kit, name))

    for rel in ("Shows", "Media/Audio", "Media/Video", "Media/Images", "Media/PDF", "Logs"):
        os.makedirs(os.path.join(kit, *rel.split("/")), exist_ok=True)

    keep = os.path.join(kit, "Shows", "PUT-SHOW-FILES-HERE.txt")
    with open(keep, "w", encoding="utf-8") as f:
        f.write("Save CueControl shows (.ccs) in this folder.\n")

    start_bat = os.path.join(kit, "Start CueControl.bat")
    with open(start_bat, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("start \"\" \"%~dp0CueControl.exe\"\n")

    exe = os.path.join(kit, "CueControl.exe")
    print("Kit ready:", kit)
    print("CueControl.exe:", "YES" if os.path.isfile(exe) else "MISSING")
    return 0 if os.path.isfile(exe) else 1


if __name__ == "__main__":
    sys.exit(main())
