#!/usr/bin/env python3
"""
Apply Organizational + Timeline group support to Main.py in place.
Creates Main.py.bak before modifying.
Run from the project root:
    python tools/apply_groups_timeline.py
"""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "Main.py"
BACKUP = ROOT / "Main.py.bak"

def must_find(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise SystemExit(f"ERROR: could not find anchor for {label}:\n  {needle[:80]}...")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    must_find(text, old, label)
    return text.replace(old, new, 1)

def main() -> None:
    if not MAIN.exists():
        raise SystemExit(f"Main.py not found at {MAIN}")

    src = MAIN.read_text(encoding="utf-8")
    original = src

    # 1) Cue model
    old_cue = '''        self.is_group = False
        self.group_mode = "simultaneous"   # "simultaneous" | "sequence"
        self.group_children = []           # list of child cue IDs
        self.parent_id = None              # if this cue belongs to a group'''
    new_cue = '''        self.is_group = False
        self.group_mode = "organizational"  # "organizational" | "timeline"
        self.group_children = []            # list of child cue IDs
        self.parent_id = None               # if this cue belongs to a group
        self.timeline_offset_ms = 0         # offset from timeline group start'''
    src = replace_once(src, old_cue, new_cue, "Cue.__init__ group fields")

    # 2) Serialization
    old_to = '''        "group_children": cue.group_children,
        "parent_id": cue.parent_id,
        "media_path": cue.media_path,'''
    new_to = '''        "group_children": cue.group_children,
        "parent_id": cue.parent_id,
        "timeline_offset_ms": getattr(cue, "timeline_offset_ms", 0),
        "media_path": cue.media_path,'''
    src = replace_once(src, old_to, new_to, "cue_to_dict")

    old_from = '''    cue.group_mode = data.get("group_mode", "simultaneous")
    cue.group_children = data.get("group_children", [])
    cue.parent_id = data.get("parent_id")'''
    new_from = '''    raw_mode = data.get("group_mode", "organizational")
    if raw_mode in ("simultaneous", "sequence"):
        raw_mode = "organizational"
    cue.group_mode = raw_mode if raw_mode in ("organizational", "timeline") else "organizational"
    cue.group_children = data.get("group_children", [])
    cue.parent_id = data.get("parent_id")
    cue.timeline_offset_ms = int(data.get("timeline_offset_ms", 0) or 0)'''
    src = replace_once(src, old_from, new_from, "cue_from_dict")

    # 3) active_timelines
    old_init = '''        self._drag_source_id = None

        self.global_output_device = None'''
    new_init = '''        self._drag_source_id = None
        self.active_timelines = {}   # group_id -> {start, fired, group}

        self.global_output_device = None'''
    src = replace_once(src, old_init, new_init, "active_timelines in __init__")

    # 4) CueRowWidget
    old_row = '''        if cue.is_group or cue.cue_type == "Group":
            text = f"📁 {num_str}  –  {cue.name}  [Group]"'''
    new_row = '''        if cue.is_group or cue.cue_type == "Group":
            mode = getattr(cue, "group_mode", "organizational")
            text = f"📁 {num_str}  –  {cue.name}  [Group · {mode}]"
        elif indent > 0 and getattr(cue, "timeline_offset_ms", 0):
            text += f"  @{cue.timeline_offset_ms}ms"'''
    src = replace_once(src, old_row, new_row, "CueRowWidget group label")

    # 5) add_cue_to_group
    old_addg = '''        child_cue.parent_id = group_cue.id
        if child_cue.id not in group_cue.group_children:
            group_cue.group_children.append(child_cue.id)

        self.statusBar.showMessage(f'Added "{child_cue.name}" to group "{group_cue.name}"')'''
    new_addg = '''        child_cue.parent_id = group_cue.id
        if child_cue.id not in group_cue.group_children:
            group_cue.group_children.append(child_cue.id)
        if not hasattr(child_cue, "timeline_offset_ms"):
            child_cue.timeline_offset_ms = 0

        self.refresh_cue_list()
        self.statusBar.showMessage(f'Added "{child_cue.name}" to group "{group_cue.name}"')'''
    src = replace_once(src, old_addg, new_addg, "add_cue_to_group")

    # 6) Group branch in start_cue
    old_group_branch = '''        elif cue.cue_type == "Group":
            children = [self.get_cue_by_id(cid) for cid in cue.group_children]
            children = [c for c in children if c is not None]
            children.sort(key=lambda c: c.number)
            if cue.group_mode == "simultaneous":
                for child in children:
                    self.start_cue(child)
            else:
                if children:
                    self.start_cue(children[0])
                    self.select_cue_by_id(children[0].id)
            self.statusBar.showMessage(f"Started group {cue.number} – {cue.name}")
            self._maybe_auto_fire(cue)
            return'''
    new_group_branch = '''        elif cue.cue_type == "Group":
            self.start_group_cue(cue)
            return'''
    src = replace_once(src, old_group_branch, new_group_branch, "start_cue Group branch")

    # 7) Insert group methods before cue_list_mouse_press
    marker = '''    def cue_list_mouse_press(self, event):
        """Capture which cue is being dragged before selection can change."""'''
    must_find(src, marker, "cue_list_mouse_press marker")

    group_methods = '''
    def start_group_cue(self, cue):
        """Organizational = first child only. Timeline = fire by timeline_offset_ms."""
        children = [self.get_cue_by_id(cid) for cid in getattr(cue, "group_children", [])]
        children = [c for c in children if c is not None]
        mode = getattr(cue, "group_mode", "organizational") or "organizational"

        if mode == "timeline":
            children.sort(key=lambda c: getattr(c, "timeline_offset_ms", 0))
            self.active_timelines[cue.id] = {
                "start": time.time(),
                "fired": set(),
                "group": cue,
            }
            for child in children:
                if getattr(child, "timeline_offset_ms", 0) <= 0:
                    self.active_timelines[cue.id]["fired"].add(child.id)
                    self.start_cue(child)
            self.statusBar.showMessage(f"Timeline {cue.number} – {cue.name} started")
        else:
            children.sort(key=lambda c: c.number)
            if children:
                self.start_cue(children[0])
                self.select_cue_by_id(children[0].id)
            self.statusBar.showMessage(
                f"Group {cue.number} – {cue.name} (organizational)"
            )

        self._maybe_auto_fire(cue)

    def tick_timelines(self):
        """Fire timeline-group children whose offset has been reached."""
        if not getattr(self, "active_timelines", None):
            return
        now = time.time()
        finished = []
        for gid, state in list(self.active_timelines.items()):
            group = state.get("group") or self.get_cue_by_id(gid)
            if group is None:
                finished.append(gid)
                continue
            elapsed_ms = (now - state["start"]) * 1000.0
            children = [self.get_cue_by_id(cid) for cid in group.group_children]
            children = [c for c in children if c is not None]
            all_fired = True
            for child in children:
                if child.id in state["fired"]:
                    continue
                if getattr(child, "timeline_offset_ms", 0) <= elapsed_ms:
                    state["fired"].add(child.id)
                    self.start_cue(child)
                else:
                    all_fired = False
            if all_fired:
                still_running = any(cid in self.active_cues for cid in group.group_children)
                if not still_running:
                    finished.append(gid)
        for gid in finished:
            self.active_timelines.pop(gid, None)

    def clear_timelines(self):
        if hasattr(self, "active_timelines"):
            self.active_timelines.clear()

    def on_group_mode_changed(self, text):
        cue = self.get_current_cue()
        if cue and (cue.cue_type == "Group" or getattr(cue, "is_group", False)):
            cue.group_mode = text
            self.refresh_cue_list()
            self.statusBar.showMessage(f"Group mode → {text}")

    def on_timeline_offset_changed(self, value):
        cue = self.get_current_cue()
        if cue is None:
            return
        cue.timeline_offset_ms = int(value)
        self.refresh_cue_list()
        self.statusBar.showMessage(f"Timeline offset {cue.number} → {value} ms")

'''
    src = src.replace(marker, group_methods + marker, 1)

    # 8) update_running_list tick
    old_url_end = '''            if cue is not None and cue.follow_mode == "Auto-Follow":
                nxt = self._next_cue_after(cue)
                if nxt is not None:
                    self.select_cue_by_id(nxt.id)
                    self.start_cue(nxt)

    def _add_and_select(self, cue):'''
    new_url_end = '''            if cue is not None and cue.follow_mode == "Auto-Follow":
                nxt = self._next_cue_after(cue)
                if nxt is not None:
                    self.select_cue_by_id(nxt.id)
                    self.start_cue(nxt)

        self.tick_timelines()

    def _add_and_select(self, cue):'''
    src = replace_once(src, old_url_end, new_url_end, "update_running_list tick")

    # 9) stop_all
    old_stop = '''    def stop_all(self):
        for cid in list(self.active_cues.keys()):
            self.stop_single_cue(cid)'''
    new_stop = '''    def stop_all(self):
        self.clear_timelines()
        for cid in list(self.active_cues.keys()):
            self.stop_single_cue(cid)'''
    src = replace_once(src, old_stop, new_stop, "stop_all clear timelines")

    # 10) add_group_cue default
    old_agc = '''        cue.is_group = True
        cue.group_mode = "simultaneous"
        cue.group_children = []'''
    new_agc = '''        cue.is_group = True
        cue.group_mode = "organizational"
        cue.group_children = []'''
    src = replace_once(src, old_agc, new_agc, "add_group_cue default mode")

    # 11) Fix create_audio_cue_from_path
    soft = '''        cue.duration_ms = self.get_audio_duration_ms(path)
       
    def add_video_cue(self):'''
    soft_new = '''        cue.duration_ms = self.get_audio_duration_ms(path)
        self._add_and_select(cue)

    def get_audio_duration_ms(self, path):
        try:
            info = sf.info(path)
            return int(info.frames / info.samplerate * 1000)
        except Exception:
            return 0

    def add_video_cue(self):'''
    if soft in src:
        src = replace_once(src, soft, soft_new, "audio soft fix")
    elif "def get_audio_duration_ms" not in src:
        print("WARN: could not auto-fix create_audio_cue_from_path")

    # 12) Group settings UI
    old_osc_hide = '''        prop_layout.addWidget(self.osc_group)
        self.osc_group.hide()

        # Waveform'''
    new_osc_hide = '''        prop_layout.addWidget(self.osc_group)
        self.osc_group.hide()

        # Group / Timeline settings
        self.group_settings_group = QGroupBox("Group / Timeline")
        gsl = QFormLayout(self.group_settings_group)
        self.group_mode_combo = QComboBox()
        self.group_mode_combo.addItems(["organizational", "timeline"])
        self.group_mode_combo.currentTextChanged.connect(self.on_group_mode_changed)
        gsl.addRow("Group mode:", self.group_mode_combo)
        self.timeline_offset_spin = QSpinBox()
        self.timeline_offset_spin.setRange(0, 12 * 60 * 60 * 1000)
        self.timeline_offset_spin.setSingleStep(100)
        self.timeline_offset_spin.setSuffix(" ms")
        self.timeline_offset_spin.valueChanged.connect(self.on_timeline_offset_changed)
        gsl.addRow("Timeline offset:", self.timeline_offset_spin)
        note_g = QLabel(
            "organizational = GO starts first child only\n"
            "timeline = children fire at their offsets from GO"
        )
        note_g.setStyleSheet("color:#aaa; font-size:11px;")
        gsl.addRow(note_g)
        prop_layout.addWidget(self.group_settings_group)
        self.group_settings_group.hide()

        # Waveform'''
    src = replace_once(src, old_osc_hide, new_osc_hide, "group settings UI")

    # 13) on_cue_selected
    old_sel_vis = '''        self.osc_group.setVisible(is_osc)
        self.wave_group.setVisible(is_audio)
        self.device_combo.setEnabled(is_audio or is_video)'''
    new_sel_vis = '''        self.osc_group.setVisible(is_osc)
        self.wave_group.setVisible(is_audio)
        self.device_combo.setEnabled(is_audio or is_video)

        is_group = cue.cue_type == "Group" or getattr(cue, "is_group", False)
        has_timeline_parent = False
        if cue.parent_id:
            parent = self.get_cue_by_id(cue.parent_id)
            if parent and getattr(parent, "group_mode", "") == "timeline":
                has_timeline_parent = True
        self.group_settings_group.setVisible(is_group or has_timeline_parent)
        if is_group:
            self.group_mode_combo.blockSignals(True)
            self.group_mode_combo.setCurrentText(
                getattr(cue, "group_mode", "organizational") or "organizational"
            )
            self.group_mode_combo.blockSignals(False)
            self.group_mode_combo.setEnabled(True)
            self.timeline_offset_spin.setEnabled(False)
        elif has_timeline_parent:
            self.group_mode_combo.setEnabled(False)
            self.timeline_offset_spin.blockSignals(True)
            self.timeline_offset_spin.setValue(int(getattr(cue, "timeline_offset_ms", 0)))
            self.timeline_offset_spin.blockSignals(False)
            self.timeline_offset_spin.setEnabled(True)'''
    src = replace_once(src, old_sel_vis, new_sel_vis, "on_cue_selected group UI")

    old_hide_all = '''            for g in (self.overlay_group, self.volume_group, self.text_group,
                      self.image_group, self.video_group, self.pdf_group,
                      self.link_group, self.osc_group, self.wave_group):
                g.hide()'''
    new_hide_all = '''            for g in (self.overlay_group, self.volume_group, self.text_group,
                      self.image_group, self.video_group, self.pdf_group,
                      self.link_group, self.osc_group, self.wave_group,
                      self.group_settings_group):
                g.hide()'''
    if old_hide_all in src:
        src = replace_once(src, old_hide_all, new_hide_all, "hide group_settings on empty")

    if src == original:
        raise SystemExit("No changes applied – anchors may have shifted")

    BACKUP.write_text(original, encoding="utf-8")
    MAIN.write_text(src, encoding="utf-8")
    print("OK – groups/timeline integrated")
    print(f"  Backup: {BACKUP}")
    print(f"  Updated: {MAIN}")
    print()
    print("Modes:")
    print("  organizational – GO starts first child; rest via manual GO / automation")
    print("  timeline       – children fire at timeline_offset_ms from group GO")

if __name__ == "__main__":
    main()
