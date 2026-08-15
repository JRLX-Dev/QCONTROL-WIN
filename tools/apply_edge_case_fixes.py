#!/usr/bin/env python3
"""
Apply edge-case hardening fixes to Main.py in-place.

Run from the repo root:
    python tools/apply_edge_case_fixes.py

Safe to run more than once (idempotent markers).
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "Main.py"
PATCH = ROOT / "patches" / "edge_case_methods.py"

MARKER_INIT = "self._drag_source_id = None"
MARKER_MOUSE = "self.cue_list.mousePressEvent = self.cue_list_mouse_press"
MARKER_REPAIR = "self.repair_cue_links()"


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def extract_methods(patch_text: str) -> dict[str, str]:
    """Pull top-level def blocks out of the patch file."""
    methods: dict[str, str] = {}
    lines = patch_text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("def "):
            name = line[4:].split("(", 1)[0].strip()
            block = [line]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.startswith("def ") and not nxt.startswith("def "):
                    break
                if nxt.startswith("def ") and block:
                    break
                # end of method: next top-level def or end of file
                if nxt.startswith("def ") and len(block) > 1:
                    break
                block.append(nxt)
                i += 1
            methods[name] = "".join(block).rstrip() + "\n\n"
            continue
        i += 1
    return methods


def replace_method(src: str, name: str, new_body: str) -> str:
    """Replace an existing `def name(...):` block with new_body."""
    # Match from '    def name' (or 'def name') through the next method at same indent
    pattern = re.compile(
        rf"(^    def {re.escape(name)}\(.*?(?=^    def |^class |^# =====|\Z))",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(src)
    if not m:
        # Method missing — insert before 'def do_crossfade' or before add-cue helpers
        anchor = re.search(r"^    def do_crossfade\(", src, re.MULTILINE)
        if not anchor:
            anchor = re.search(r"^    def _add_and_select\(", src, re.MULTILINE)
        if not anchor:
            die(f"Could not find insertion point for new method {name}")
        return src[: anchor.start()] + "    " + new_body.replace("\ndef ", "\n    def ", 1) + src[anchor.start():]

    # Ensure the replacement is indented as a class method
    body = new_body
    if not body.startswith("    def "):
        body = "    " + body.replace("\ndef ", "\n    def ", 1)
    if not body.endswith("\n\n"):
        body = body.rstrip() + "\n\n"
    return src[: m.start()] + body + src[m.end():]


def main() -> None:
    if not MAIN.exists():
        die(f"Main.py not found at {MAIN}")
    if not PATCH.exists():
        die(f"Patch file not found at {PATCH}")

    src = MAIN.read_text(encoding="utf-8")
    patch_text = PATCH.read_text(encoding="utf-8")
    methods = extract_methods(patch_text)

    required = [
        "repair_cue_links",
        "cue_list_mouse_press",
        "cue_list_drop_event",
        "reorder_cue",
        "start_cue",
        "_maybe_auto_fire",
        "_next_cue_after",
        "update_running_list",
    ]
    for name in required:
        if name not in methods:
            die(f"Patch file is missing method: {name}")

    changed = False

    # 1) __init__ flag
    if MARKER_INIT not in src:
        needle = "self._debounce_timers = {}"
        if needle not in src:
            die("Could not find self._debounce_timers = {} in __init__")
        src = src.replace(
            needle,
            needle + "\n        " + MARKER_INIT,
            1,
        )
        changed = True
        print("+ added self._drag_source_id = None")

    # 2) mousePress binding
    if MARKER_MOUSE not in src:
        needle = "self.cue_list.dragMoveEvent = self.cue_list_drag_move"
        if needle not in src:
            die("Could not find dragMoveEvent binding")
        src = src.replace(
            needle,
            needle + "\n        " + MARKER_MOUSE,
            1,
        )
        changed = True
        print("+ bound cue_list.mousePressEvent")

    # 3) repair after load
    if src.count(MARKER_REPAIR) < 1:
        # After cues are loaded in load_show
        load_anchor = re.search(
            r"(for cdata in data\.get\(\"cues\", \[\]\):\n\s+self\.cues\.append\(cue_from_dict\(cdata\)\)\n)",
            src,
        )
        if load_anchor:
            src = (
                src[: load_anchor.end()]
                + "\n        self.repair_cue_links()\n"
                + src[load_anchor.end():]
            )
            changed = True
            print("+ repair_cue_links() after load_show")
        else:
            print("! could not auto-insert repair after load_show — add manually")

    # 4) repair after delete (before refresh_cue_list in delete_cue_by_id)
    # Only add if we still have fewer than 2 calls
    if src.count(MARKER_REPAIR) < 2:
        del_anchor = re.search(
            r"(self\.cues = \[c for c in self\.cues if c\.id != cue_id\]\n\s+self\.destroy_window\(cue\)\n)",
            src,
        )
        if del_anchor:
            src = (
                src[: del_anchor.end()]
                + "\n        self.repair_cue_links()\n"
                + src[del_anchor.end():]
            )
            changed = True
            print("+ repair_cue_links() after delete")
        else:
            print("! could not auto-insert repair after delete — add manually")

    # 5) Replace / insert method bodies
    for name in required:
        before = src
        src = replace_method(src, name, methods[name])
        if src != before:
            changed = True
            print(f"~ replaced/inserted method: {name}")
        else:
            print(f"= method unchanged (already present?): {name}")

    if not changed:
        print("Main.py already fully integrated — nothing to do.")
        return

    backup = MAIN.with_suffix(".py.bak")
    backup.write_text(MAIN.read_text(encoding="utf-8"), encoding="utf-8")
    MAIN.write_text(src, encoding="utf-8")
    print(f"\nDone. Backup written to {backup.name}")
    print("Run Main.py and exercise the test matrix.")


if __name__ == "__main__":
    main()
