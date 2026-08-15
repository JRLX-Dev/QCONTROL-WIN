# =====================================================================
# DROP-IN METHODS for MainWindow – edge-case hardening
# These replace / extend the corresponding methods in Main.py
# =====================================================================

# --- add to __init__ after other instance vars ---
# self._drag_source_id = None

def repair_cue_links(self):
    """Remove stale parent/child references so no cue becomes invisible."""
    ids = {c.id for c in self.cues}
    for c in self.cues:
        if c.parent_id and c.parent_id not in ids:
            c.parent_id = None
        if c.is_group or c.cue_type == "Group":
            c.group_children = [cid for cid in c.group_children if cid in ids]
            for cid in c.group_children:
                child = self.get_cue_by_id(cid)
                if child is not None:
                    child.parent_id = c.id
        elif c.parent_id:
            parent = self.get_cue_by_id(c.parent_id)
            if parent is not None and c.id not in parent.group_children:
                parent.group_children.append(c.id)

def cue_list_mouse_press(self, event):
    """Capture which cue is being dragged before selection can change."""
    pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
    item = self.cue_list.itemAt(pos)
    if item is not None:
        self._drag_source_id = item.data(Qt.ItemDataRole.UserRole)
    QListWidget.mousePressEvent(self.cue_list, event)

def cue_list_drop_event(self, event):
    if event.mimeData().hasUrls():
        self.handle_external_file_drop(event.mimeData().urls())
        event.acceptProposedAction()
        return

    if event.source() is not self.cue_list:
        event.ignore()
        return

    source_id = getattr(self, "_drag_source_id", None)
    if not source_id:
        source_item = self.cue_list.currentItem()
        if source_item:
            source_id = source_item.data(Qt.ItemDataRole.UserRole)
    if not source_id:
        event.ignore()
        return

    source_cue = self.get_cue_by_id(source_id)
    if not source_cue:
        event.ignore()
        return

    pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
    target_item = self.cue_list.itemAt(pos)

    if target_item is None:
        self.reorder_cue(source_cue, None)
        event.acceptProposedAction()
        self.refresh_cue_list()
        self.select_cue_by_id(source_id)
        self._drag_source_id = None
        return

    target_id = target_item.data(Qt.ItemDataRole.UserRole)
    target_cue = self.get_cue_by_id(target_id)
    if not target_cue or target_id == source_id:
        event.ignore()
        self._drag_source_id = None
        return

    if target_cue.cue_type == "Group" or target_cue.is_group:
        self.add_cue_to_group(source_cue, target_cue)
    else:
        self.reorder_cue(source_cue, target_cue)

    event.acceptProposedAction()
    self.refresh_cue_list()
    self.select_cue_by_id(source_id)
    self._drag_source_id = None

def reorder_cue(self, source_cue, target_cue):
    """Move source relative to target without destroying fractional numbers."""
    if source_cue.parent_id:
        old_group = self.get_cue_by_id(source_cue.parent_id)
        if old_group and source_cue.id in old_group.group_children:
            old_group.group_children.remove(source_cue.id)
        source_cue.parent_id = None

    others = sorted(
        [c for c in self.cues if c.id != source_cue.id],
        key=lambda c: c.number
    )

    if not others:
        source_cue.number = 1.0
        self.statusBar.showMessage(f"Moved “{source_cue.name}”")
        return

    if target_cue is None:
        source_cue.number = others[-1].number + 1.0
    else:
        idx = next((i for i, c in enumerate(others) if c.id == target_cue.id), len(others))
        prev_num = others[idx - 1].number if idx > 0 else 0.0
        next_num = others[idx].number if idx < len(others) else prev_num + 2.0
        gap = next_num - prev_num
        if gap > 0.05:
            source_cue.number = round(prev_num + gap / 2.0, 3)
        else:
            # Neighbours are too close – shift the tail up by 1
            source_cue.number = round(prev_num + 1.0, 3)
            for c in others[idx:]:
                if c.number >= source_cue.number:
                    c.number = round(c.number + 1.0, 3)

    self.statusBar.showMessage(
        f"Moved “{source_cue.name}” → cue {source_cue.number}"
    )

def start_cue(self, cue):
    if cue.id in self.active_cues:
        self.statusBar.showMessage(f"Cue {cue.number} is already running")
        return

    IMPLEMENTED = (
        "Audio", "Video", "Image", "Text", "PDF", "Link", "OSC",
        "Automation", "Wait", "Group"
    )
    if cue.cue_type not in IMPLEMENTED:
        self.statusBar.showMessage(f"{cue.cue_type} cues aren't implemented yet")
        return

    info = {"cue": cue, "start": time.time(), "player": None, "output": None}
    started = False

    if cue.cue_type == "Audio":
        if not cue.media_path or not os.path.exists(cue.media_path):
            self.statusBar.showMessage(f"Audio file missing: {cue.media_path or '(none)'}")
            return
        player, output = self.create_player(cue)
        def on_status(status):
            if status == QMediaPlayer.MediaStatus.LoadedMedia:
                player.play()
        player.mediaStatusChanged.connect(on_status)
        player.setSource(QUrl.fromLocalFile(cue.media_path))
        info["player"] = player
        info["output"] = output
        started = True

    elif cue.cue_type == "Text":
        screen = self.get_screen_by_name(cue.screen_name)
        win = self.get_or_create_window(cue)
        win.show_text(cue, screen, self.display_defaults)
        started = True

    elif cue.cue_type == "Image":
        if not cue.image_path or not os.path.exists(cue.image_path):
            self.statusBar.showMessage(f"Image file missing: {cue.image_path or '(none)'}")
            return
        if cue.image_persistent:
            for other_id, other_info in list(self.active_cues.items()):
                other_cue = other_info["cue"]
                if (other_cue.cue_type == "Image" and
                        other_cue.image_persistent and
                        other_id != cue.id):
                    self.stop_single_cue(other_id)
        screen = self.get_screen_by_name(cue.screen_name)
        win = self.get_or_create_window(cue)
        win.show_image(cue, screen, self.display_defaults)
        started = True

    elif cue.cue_type == "Video":
        if not cue.video_path or not os.path.exists(cue.video_path):
            self.statusBar.showMessage(f"Video file missing: {cue.video_path or '(none)'}")
            return
        screen = self.get_screen_by_name(cue.screen_name)
        win = self.get_or_create_window(cue)
        device = self.get_device_by_id(cue.audio_device_id)
        win.show_video(cue, screen, self.display_defaults, device)
        started = True

    elif cue.cue_type == "PDF":
        if not cue.pdf_path or not os.path.exists(cue.pdf_path):
            self.statusBar.showMessage(f"PDF file missing: {cue.pdf_path or '(none)'}")
            return
        screen = self.get_screen_by_name(cue.screen_name)
        win = self.get_or_create_window(cue)
        win.show_pdf(cue, screen, self.display_defaults)
        started = True

    elif cue.cue_type == "Link":
        url = (cue.link_url or "").strip()
        if not url:
            self.statusBar.showMessage("No URL set for Link cue")
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if cue.link_use_system_browser or not HAS_WEBENGINE:
            webbrowser.open(url)
            self.statusBar.showMessage(f"Opened in system browser: {url}")
            # system browser is fire-and-forget – still count as started briefly
            started = True
        else:
            screen = self.get_screen_by_name(cue.screen_name)
            win = self.get_or_create_window(cue)
            win.show_url(cue, screen, self.display_defaults)
            started = True

    elif cue.cue_type == "OSC":
        if not self.send_osc(cue):
            return
        started = True

    elif cue.cue_type == "Wait":
        if cue.duration_ms <= 0:
            cue.duration_ms = 100
            self.statusBar.showMessage("Wait duration was 0 – using 0.1 s")
        started = True

    elif cue.cue_type == "Group":
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
        # Group is a container – do not keep it in active_cues
        self.statusBar.showMessage(f"Started group {cue.number} – {cue.name}")
        self._maybe_auto_fire(cue)
        return

    elif cue.cue_type == "Automation":
        name_lower = cue.name.lower()
        if "crossfade" in name_lower:
            self.do_crossfade()
        elif "stop & fade" in name_lower or "stop and fade" in name_lower:
            self.fade_and_stop()
        elif "stop" in name_lower:
            self.stop_all()
        started = True

    if not started:
        return

    self.active_cues[cue.id] = info
    self.update_running_list()
    self.statusBar.showMessage(f"Started {cue.number} – {cue.name}")
    self._maybe_auto_fire(cue)

def _maybe_auto_fire(self, cue):
    """If follow mode is Auto-Fire, immediately start the next cue."""
    if cue.follow_mode != "Auto-Fire":
        return
    nxt = self._next_cue_after(cue)
    if nxt is not None:
        self.select_cue_by_id(nxt.id)
        self.start_cue(nxt)

def _next_cue_after(self, cue):
    ordered = sorted(self.cues, key=lambda c: c.number)
    try:
        idx = ordered.index(cue)
    except ValueError:
        return None
    if idx + 1 < len(ordered):
        return ordered[idx + 1]
    return None

def update_running_list(self):
    self.running_list.clear()
    now = time.time()
    finished = []
    for cid, info in list(self.active_cues.items()):
        cue = info["cue"]
        elapsed = (now - info["start"]) * 1000

        # Instant types finish immediately when duration is 0
        if cue.cue_type in ("OSC", "Automation") and cue.duration_ms == 0:
            finished.append(cid)
            continue

        if cue.duration_ms > 0 and elapsed >= cue.duration_ms:
            finished.append(cid)
            continue

        if cue.duration_ms > 0:
            remaining = max(0, cue.duration_ms - elapsed)
            t = f"{int(remaining // 60000):02d}:{int((remaining % 60000) // 1000):02d}"
        else:
            t = "∞"
        self.running_list.addItem(f"▶ {cue.number} - {cue.name}   [{t}]")

    for cid in finished:
        cue = self.active_cues[cid]["cue"] if cid in self.active_cues else None
        self.stop_single_cue(cid)
        # Auto-Follow: when a timed cue finishes, start the next one
        if cue is not None and cue.follow_mode == "Auto-Follow":
            nxt = self._next_cue_after(cue)
            if nxt is not None:
                self.select_cue_by_id(nxt.id)
                self.start_cue(nxt)
