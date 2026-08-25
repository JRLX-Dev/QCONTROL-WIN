"""Portable USB/SSD helpers for CueControl Windows.

Imported by CueControl_launch.py (the .exe and Run CueControl.bat).
Main.py is not modified. If this file is missing, the app still runs
with absolute media paths.

Kit root = folder that contains CUECONTROL_PORTABLE.txt, walking up
from the exe (frozen) or this file (source). Shows\\ and Media\\ live
there so a drive-letter change (E: -> F:) does not break a show.
"""
from __future__ import annotations

import json
import os
import sys

MARKER = "CUECONTROL_PORTABLE.txt"
PATH_KEYS = ("media_path", "image_path", "video_path", "pdf_path")
_KIT_CACHE = None


class _Tee:
    def __init__(self, *streams):
        self.streams = [s for s in streams if s is not None]

    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def kit_root(start=None):
    """Folder that owns Shows/, Media/, and the portable marker."""
    global _KIT_CACHE
    if start is None and _KIT_CACHE and os.path.isdir(_KIT_CACHE):
        return _KIT_CACHE

    env = os.environ.get("CUECONTROL_ROOT")
    if env and os.path.isdir(env):
        root = os.path.abspath(env)
        if start is None:
            _KIT_CACHE = root
        return root

    cur = os.path.abspath(start or app_dir())
    for _ in range(8):
        if os.path.isfile(os.path.join(cur, MARKER)):
            if start is None:
                _KIT_CACHE = cur
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    root = os.path.abspath(start or app_dir())
    if start is None:
        _KIT_CACHE = root
    return root


def reset_kit_cache():
    global _KIT_CACHE
    _KIT_CACHE = None


def shows_dir(root=None):
    d = os.path.join(root or kit_root(), "Shows")
    os.makedirs(d, exist_ok=True)
    return d


def media_dir(kind=None, root=None):
    d = os.path.join(root or kit_root(), "Media")
    os.makedirs(d, exist_ok=True)
    sub = {
        "audio": "Audio",
        "video": "Video",
        "image": "Images",
        "images": "Images",
        "pdf": "PDF",
        "select audio": "Audio",
        "select video": "Video",
        "select image": "Images",
        "select pdf": "PDF",
    }.get((kind or "").strip().lower())
    if sub:
        d = os.path.join(d, sub)
        os.makedirs(d, exist_ok=True)
    return d


def ensure_kit_folders(root=None):
    root = root or kit_root()
    for rel in ("Shows", "Media/Audio", "Media/Video", "Media/Images", "Media/PDF", "Logs"):
        os.makedirs(os.path.join(root, *rel.split("/")), exist_ok=True)
    marker = os.path.join(root, MARKER)
    if not os.path.isfile(marker):
        try:
            with open(marker, "w", encoding="utf-8") as f:
                f.write("CueControl portable kit. Keep this file next to Shows and Media.\n")
        except OSError:
            pass
    return root


def to_portable(path, root=None):
    """Absolute path -> kit-relative with / slashes. Unchanged if outside the kit."""
    if not path or not isinstance(path, str):
        return path
    path = os.path.abspath(os.path.expanduser(path))
    root = os.path.abspath(root or kit_root())
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        return path
    if rel.startswith("..") or os.path.isabs(rel):
        return path
    return rel.replace("\\", "/")


def _split_win_parts(stored):
    s = stored.replace("/", "\\").strip()
    parts = [p for p in s.split("\\") if p and p != "."]
    if parts and len(parts[0]) >= 2 and parts[0][1] == ":":
        parts = parts[1:]
    return parts


def resolve_path(stored, show_dir=None, root=None):
    """Turn a saved path (relative, absolute, or old drive letter) into a live path."""
    if not stored or not isinstance(stored, str):
        return stored
    stored = stored.strip()
    if not stored:
        return stored
    if os.path.exists(stored):
        return os.path.abspath(stored)

    root = os.path.abspath(root or kit_root())
    candidates = []

    norm = stored.replace("/", os.sep)
    if not os.path.isabs(norm):
        candidates.append(os.path.join(root, norm))
        if show_dir:
            candidates.append(os.path.join(show_dir, norm))

    parts = _split_win_parts(stored)
    for marker in ("Media", "Shows"):
        if marker in parts:
            i = parts.index(marker)
            candidates.append(os.path.join(root, *parts[i:]))
            break
    else:
        if parts:
            candidates.append(os.path.join(root, *parts))
            candidates.append(os.path.join(root, "Media", parts[-1]))

    seen = set()
    for c in candidates:
        c = os.path.abspath(c)
        if c in seen:
            continue
        seen.add(c)
        if os.path.exists(c):
            return c
    return stored


def portableize_value(value, root=None):
    if not value or not isinstance(value, str):
        return value
    if not os.path.isabs(value):
        return value.replace("\\", "/")
    return to_portable(value, root)


def rewrite_ccs_file(path, root=None):
    """Rewrite media fields in a .ccs to kit-relative paths. Idempotent."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    root = os.path.abspath(root or kit_root())
    changed = False
    for cue in data.get("cues") or []:
        if not isinstance(cue, dict):
            continue
        for key in PATH_KEYS:
            old = cue.get(key)
            new = portableize_value(old, root)
            if new != old:
                cue[key] = new
                changed = True
    data["portable"] = True
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return changed


def resolve_cue_list(cues, show_dir=None, root=None):
    root = root or kit_root()
    for cue in cues:
        for key in PATH_KEYS:
            val = getattr(cue, key, "")
            if val:
                setattr(cue, key, resolve_path(val, show_dir=show_dir, root=root))


def dir_for_caption(caption):
    cap = (caption or "").lower()
    if "show" in cap:
        return shows_dir()
    if "audio" in cap:
        return media_dir("audio")
    if "video" in cap:
        return media_dir("video")
    if "image" in cap:
        return media_dir("image")
    if "pdf" in cap:
        return media_dir("pdf")
    return kit_root()


def bootstrap():
    """chdir to the kit, create folders, tee stdout/stderr to Logs\\cuecontrol.log."""
    root = ensure_kit_folders()
    try:
        os.chdir(root)
    except OSError:
        pass
    log_path = os.path.join(root, "Logs", "cuecontrol.log")
    try:
        log_f = open(log_path, "a", encoding="utf-8", buffering=1)
        log_f.write("\n---- CueControl start ----\n")
        sys.stdout = _Tee(getattr(sys, "stdout", None), log_f)
        sys.stderr = _Tee(getattr(sys, "stderr", None), log_f)
    except OSError:
        pass
    return root


def install_hooks(main_mod):
    """Wrap save/load + file dialogs. Safe to call once after `import Main`."""
    from PySide6.QtWidgets import QFileDialog

    orig_open = QFileDialog.getOpenFileName
    orig_save = QFileDialog.getSaveFileName

    def getOpenFileName(parent=None, caption="", directory="", filter="", *args, **kwargs):
        if not directory:
            directory = dir_for_caption(caption)
        return orig_open(parent, caption, directory, filter, *args, **kwargs)

    def getSaveFileName(parent=None, caption="", directory="", filter="", *args, **kwargs):
        if not directory:
            directory = dir_for_caption(caption)
        return orig_save(parent, caption, directory, filter, *args, **kwargs)

    QFileDialog.getOpenFileName = staticmethod(getOpenFileName)
    QFileDialog.getSaveFileName = staticmethod(getSaveFileName)

    MW = main_mod.MainWindow
    orig_save_show = MW.save_show
    orig_load_show = MW.load_show
    orig_title = MW.update_window_title

    def save_show(self, force_dialog=False):
        orig_save_show(self, force_dialog)
        path = getattr(self, "current_show_path", None)
        if path and os.path.isfile(path):
            try:
                rewrite_ccs_file(path)
            except Exception:
                pass

    def load_show(self):
        orig_load_show(self)
        path = getattr(self, "current_show_path", None)
        if not path:
            return
        try:
            resolve_cue_list(self.cues, show_dir=os.path.dirname(path))
            self.refresh_cue_list()
            cid = getattr(self, "current_cue_id", None)
            if cid:
                self.select_cue_by_id(cid)
        except Exception:
            pass

    def update_window_title(self):
        orig_title(self)
        title = self.windowTitle()
        if "portable" not in title.lower():
            self.setWindowTitle(title + "  ·  portable")

    MW.save_show = save_show
    MW.load_show = load_show
    MW.update_window_title = update_window_title
