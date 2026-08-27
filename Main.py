# =====================================================================
# CueControl Windows
# Lightweight QLab-style cue system
# Audio | Text | Image | Video | PDF | Link | OSC | Wait | Group
# + Volume + Save/Load + Drag & Drop
# =====================================================================
"""CueControl Windows — a lightweight QLab-style cue playback app.

Built for churches, schools, and small productions on Windows 10/11.
One-file PySide6 app: cue list, GO/STOP, overlays (text/image/video/PDF/web),
audio, OSC, groups, and .ccs show files.

Follow modes
    Off          GO fires this cue only; stand-by stays put
    Auto-Ready   GO fires this cue and arms the next one
    Auto-Follow  when this cue's duration ends, the next cue starts
    Auto-Fire    GO fires this cue and immediately fires the next (capped)
"""

import sys
import os
import time
import uuid
import json
import tempfile
import traceback
import webbrowser
import numpy as np
import soundfile as sf
from copy import deepcopy

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QListWidget, QStatusBar, QFrame, QListWidgetItem, QTabWidget,
    QToolBar, QInputDialog, QFileDialog, QComboBox, QFormLayout, QLineEdit,
    QGroupBox, QSpinBox, QTextEdit, QColorDialog, QDoubleSpinBox, QCheckBox,
    QSizePolicy, QDialog, QDialogButtonBox, QMessageBox, QAbstractItemView,
    QSlider
)
from PySide6.QtCore import Qt, QTimer, QUrl, QPoint, QRect, Signal, QSize, QSettings
from PySide6.QtGui import (
    QColor, QAction, QActionGroup, QFont, QPainter, QPen, QGuiApplication,
    QMouseEvent, QPixmap, QKeySequence, QShortcut
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget

# Optional modules
try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

try:
    from pythonosc import udp_client
    HAS_OSC = True
except ImportError:
    HAS_OSC = False


# =====================================================================
# SECTION: OSC Presets
# =====================================================================
OSC_PRESETS = {
    "ETC EOS": {
        "default_port": 8000,
        "common": [
            {"name": "Fire Cue",     "address": "/eos/cue/fire",   "arg_hint": "cue number (float)"},
            {"name": "Go",           "address": "/eos/key/go",     "arg_hint": ""},
            {"name": "Stop",         "address": "/eos/key/stop",   "arg_hint": ""},
            {"name": "Macro Fire",   "address": "/eos/macro/fire", "arg_hint": "macro number (int)"},
            {"name": "Command Line", "address": "/eos/cmd",        "arg_hint": "command string"},
        ]
    },
    "GrandMA": {
        "default_port": 8000,
        "common": [
            {"name": "Command", "address": "/cmd", "arg_hint": "command string"},
            {"name": "Go+",     "address": "/cmd", "arg_hint": "Go+"},
            {"name": "Go-",     "address": "/cmd", "arg_hint": "Go-"},
            {"name": "Off",     "address": "/cmd", "arg_hint": "Off"},
        ]
    },
    "HOG": {
        "default_port": 7001,
        "common": [
            {"name": "Go",   "address": "/hog/playback/go",   "arg_hint": "cuelist number"},
            {"name": "Halt", "address": "/hog/playback/halt", "arg_hint": "cuelist number"},
        ]
    },
    "Midas / Behringer": {
        "default_port": 10023,
        "common": [
            {"name": "Channel Fader", "address": "/ch/01/mix/fader", "arg_hint": "level 0.0–1.0"},
            {"name": "Mute",          "address": "/ch/01/mix/on",    "arg_hint": "0"},
            {"name": "Unmute",        "address": "/ch/01/mix/on",    "arg_hint": "1"},
        ]
    },
    "Allen & Heath": {
        "default_port": 51320,
        "common": [
            {"name": "Scene Recall", "address": "/scene/recall", "arg_hint": "scene number"},
        ]
    },
    "Yamaha": {
        "default_port": 49280,
        "common": [
            {"name": "Scene Recall", "address": "/scene/recall", "arg_hint": "scene number"},
        ]
    },
    "Custom / Manual": {
        "default_port": 8000,
        "common": []
    }
}


# =====================================================================
# SECTION: Audio device id helper
# =====================================================================
def device_id_to_str(raw_id):
    """Normalize a Qt audio device id to a stable string (or None)."""
    if raw_id is None:
        return None
    if isinstance(raw_id, str):
        return raw_id
    try:
        return bytes(raw_id).hex()
    except TypeError:
        return str(raw_id)


def format_cue_row_text(cue, indent=0, status=""):
    """Cue-list line. Status is written as STANDBY/RUNNING, not color-only."""
    num_str = str(int(cue.number)) if cue.number == int(cue.number) else f"{cue.number:.1f}"
    prefix = "↳  " if indent > 0 else ""
    text = f"{prefix}{num_str}  –  {cue.name}  ({cue.cue_type})"

    if cue.is_group or cue.cue_type == "Group":
        mode = getattr(cue, "group_mode", "organizational")
        text = f"📁 {num_str}  –  {cue.name}  [Group · {mode}]"
    elif indent > 0 and getattr(cue, "timeline_offset_ms", 0):
        text += f"  @{cue.timeline_offset_ms}ms"

    if cue.follow_mode != "Off":
        text += f"  [{cue.follow_mode}]"
    if cue.duration_ms > 0:
        text += f"  {cue.duration_ms/1000:.1f}s"
    if cue.cue_type in ("Text", "Image", "Video", "PDF", "Link"):
        text += f"  L{cue.layer}"
    if cue.cue_type in ("Audio", "Video") and cue.volume < 0.995:
        text += f"  Vol {int(round(cue.volume*100))}%"
    if cue.cue_type == "Image" and not cue.image_persistent:
        text += "  [non-persist]"
    if cue.cue_type == "Link" and cue.link_use_system_browser:
        text += "  [system]"
    if cue.cue_type == "OSC":
        text += f"  → {cue.osc_ip}:{cue.osc_port}"
    if cue.cue_type == "Wait":
        text += f"  ⏱ {cue.duration_ms/1000:.1f}s"
    if status:
        text = f"{status}  {text}"
    return text


# =====================================================================
# SECTION: Cue data model
# =====================================================================
class Cue:
    """One row in the cue list: media, overlay, automation, wait, or group."""
    def __init__(self, number, name, cue_type="Audio", follow_mode="Auto-Ready"):
        self.id = str(uuid.uuid4())
        self.number = float(number)
        self.name = name
        self.cue_type = cue_type
        self.follow_mode = follow_mode
        self.is_group = False
        self.group_mode = "organizational"  # "organizational" | "timeline"
        self.group_children = []            # list of child cue IDs
        self.parent_id = None               # if this cue belongs to a group
        self.timeline_offset_ms = 0         # offset from timeline group start
        self.media_path = ""
        self.duration_ms = 0
        self.audio_device_id = None
        self.volume = 1.0

        # Overlay shared
        self.screen_name = None
        self.size_mode = "percent"
        self.width_px = 1280
        self.height_px = 720
        self.width_percent = 80.0
        self.height_percent = 60.0
        self.pos_x = None
        self.pos_y = None
        self.layer = 50
        self.opacity = 1.0
        self.user_moved = False

        # Text
        self.text = ""
        self.font_size = 64
        self.text_color = "#FFFFFF"
        self.bg_color = "rgba(0,0,0,160)"

        # Image
        self.image_path = ""
        self.scale_mode = "Fit"
        self.image_persistent = True

        # Video
        self.video_path = ""
        self.video_loop = False
        self.video_muted = False

        # PDF
        self.pdf_path = ""
        self.pdf_page = 0
        self.pdf_zoom_mode = "Fit"
        self.pdf_multipage = False          # True = scroll all pages

        # Link
        self.link_url = ""
        self.link_use_system_browser = False

        # OSC
        self.osc_ip = "127.0.0.1"
        self.osc_port = 8000
        self.osc_address = ""
        self.osc_args = ""
        self.osc_preset = "ETC EOS"


# =====================================================================
# SECTION: Serialization
# =====================================================================
def _safe_num(data, key, default, cast=float):
    """Pull a numeric field out of loaded JSON without trusting its type.

    A truncated write (e.g. USB stick pulled mid-save) or a hand-edited
    .ccs can leave a numeric field as null, a string, or missing entirely.
    Without this, the bad value doesn't fail at load time -- it fails
    later, live, the first time the cue fires (e.g. TypeError comparing
    a float and a str inside the 300ms UI timer tick).
    """
    try:
        v = data.get(key, default)
        if v is None:
            return default
        return cast(v)
    except (TypeError, ValueError):
        return default


def _app_dir():
    """Folder that holds Main.py (or the exe). Crash log and .ccs live here on a stick."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _atomic_write_json(path, data):
    """Write JSON so yanking a USB stick cannot leave a half-written .ccs.

    Bytes go to a temp file in the same folder, are flushed to disk, then
    os.replace() swaps the name. On NTFS that swap is atomic: the previous
    show file stays intact until the new one is fully written.
    """
    path = os.path.abspath(path)
    folder = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".ccs-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass


def cue_to_dict(cue):
    """Serialize one Cue to a JSON-safe dict."""
    return {
        "id": cue.id,
        "number": cue.number,
        "name": cue.name,
        "cue_type": cue.cue_type,
        "follow_mode": cue.follow_mode,
        "is_group": cue.is_group,
        "group_mode": cue.group_mode,
        "group_children": cue.group_children,
        "parent_id": cue.parent_id,
        "timeline_offset_ms": getattr(cue, "timeline_offset_ms", 0),
        "media_path": cue.media_path,
        "duration_ms": cue.duration_ms,
        "audio_device_id": cue.audio_device_id,
        "volume": cue.volume,
        "screen_name": cue.screen_name,
        "size_mode": cue.size_mode,
        "width_px": cue.width_px,
        "height_px": cue.height_px,
        "width_percent": cue.width_percent,
        "height_percent": cue.height_percent,
        "pos_x": cue.pos_x,
        "pos_y": cue.pos_y,
        "layer": cue.layer,
        "opacity": cue.opacity,
        "user_moved": cue.user_moved,
        "text": cue.text,
        "font_size": cue.font_size,
        "text_color": cue.text_color,
        "bg_color": cue.bg_color,
        "image_path": cue.image_path,
        "scale_mode": cue.scale_mode,
        "image_persistent": cue.image_persistent,
        "video_path": cue.video_path,
        "video_loop": cue.video_loop,
        "video_muted": cue.video_muted,
        "pdf_path": cue.pdf_path,
        "pdf_page": cue.pdf_page,
        "pdf_zoom_mode": cue.pdf_zoom_mode,
        "pdf_multipage": getattr(cue, "pdf_multipage", False),
        "link_url": cue.link_url,
        "link_use_system_browser": cue.link_use_system_browser,
        "osc_ip": cue.osc_ip,
        "osc_port": cue.osc_port,
        "osc_address": cue.osc_address,
        "osc_args": cue.osc_args,
        "osc_preset": cue.osc_preset,
    }


def cue_from_dict(data):
    """Rebuild a Cue from saved JSON. Numeric fields go through _safe_num()."""
    safe_number = _safe_num(data, "number", 1, float)
    cue = Cue(safe_number, data.get("name", "Untitled"), data.get("cue_type", "Audio"))
    cue.id = data.get("id", str(uuid.uuid4()))
    cue.follow_mode = data.get("follow_mode", "Auto-Ready")
    cue.is_group = data.get("is_group", False)
    raw_mode = data.get("group_mode", "organizational")
    if raw_mode in ("simultaneous", "sequence"):
        raw_mode = "organizational"
    cue.group_mode = raw_mode if raw_mode in ("organizational", "timeline") else "organizational"
    cue.group_children = data.get("group_children", [])
    cue.parent_id = data.get("parent_id")
    cue.timeline_offset_ms = _safe_num(data, "timeline_offset_ms", 0, int)
    cue.media_path = data.get("media_path", "")
    cue.duration_ms = _safe_num(data, "duration_ms", 0, int)
    cue.audio_device_id = data.get("audio_device_id")
    cue.volume = _safe_num(data, "volume", 1.0, float)
    cue.screen_name = data.get("screen_name")
    cue.size_mode = data.get("size_mode", "percent")
    cue.width_px = _safe_num(data, "width_px", 1280, int)
    cue.height_px = _safe_num(data, "height_px", 720, int)
    cue.width_percent = _safe_num(data, "width_percent", 80.0, float)
    cue.height_percent = _safe_num(data, "height_percent", 60.0, float)
    cue.pos_x = _safe_num(data, "pos_x", None, int) if data.get("pos_x") is not None else None
    cue.pos_y = _safe_num(data, "pos_y", None, int) if data.get("pos_y") is not None else None
    cue.layer = _safe_num(data, "layer", 50, int)
    cue.opacity = _safe_num(data, "opacity", 1.0, float)
    cue.user_moved = data.get("user_moved", False)
    cue.text = data.get("text", "")
    cue.font_size = _safe_num(data, "font_size", 64, int)
    cue.text_color = data.get("text_color", "#FFFFFF")
    cue.bg_color = data.get("bg_color", "rgba(0,0,0,160)")
    cue.image_path = data.get("image_path", "")
    cue.scale_mode = data.get("scale_mode", "Fit")
    cue.image_persistent = data.get("image_persistent", True)
    cue.video_path = data.get("video_path", "")
    cue.video_loop = data.get("video_loop", False)
    cue.video_muted = data.get("video_muted", False)
    cue.pdf_path = data.get("pdf_path", "")
    cue.pdf_page = _safe_num(data, "pdf_page", 0, int)
    cue.pdf_zoom_mode = data.get("pdf_zoom_mode", "Fit")
    cue.pdf_multipage = bool(data.get("pdf_multipage", False))
    cue.link_url = data.get("link_url", "")
    cue.link_use_system_browser = data.get("link_use_system_browser", False)
    cue.osc_ip = data.get("osc_ip", "127.0.0.1")
    cue.osc_port = _safe_num(data, "osc_port", 8000, int)
    cue.osc_address = data.get("osc_address", "")
    cue.osc_args = data.get("osc_args", "")
    cue.osc_preset = data.get("osc_preset", "ETC EOS")
    return cue


# =====================================================================
# SECTION: Cue list row widget
# =====================================================================
class CueRowWidget(QWidget):
    """One cue-list row. Accessible name matches the visible STANDBY/RUNNING line."""
    delete_clicked = Signal(str)

    def __init__(self, cue, indent=0, status="", row_h=36, parent=None):
        super().__init__(parent)
        self.cue_id = cue.id
        self._indent = indent
        self.setFixedHeight(row_h)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8 + indent * 28, 4, 8, 4)
        layout.setSpacing(10)

        num_str = str(int(cue.number)) if cue.number == int(cue.number) else f"{cue.number:.1f}"
        text = format_cue_row_text(cue, indent, status)

        self.label = QLabel(text)
        layout.addWidget(self.label, 1)

        self.btn = QPushButton("✕")
        self.btn.setFixedSize(max(24, row_h - 12), max(24, row_h - 12))
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn.setToolTip(f"Delete cue {num_str} {cue.name}")
        self.btn.setAccessibleName(f"Delete cue {num_str} {cue.name}")
        self.btn.setAccessibleDescription("Removes this cue from the show")
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: #5a1a1a; color: #ffb0b0;
                border: 1px solid #8a3030; border-radius: 4px;
                font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #a03030; color: white; }
            QPushButton:focus { border: 2px solid #FFE14D; }
        """)
        self.btn.clicked.connect(lambda: self.delete_clicked.emit(self.cue_id))
        layout.addWidget(self.btn)
        self.apply_status(text, status)

    def apply_status(self, text, status):
        self.label.setText(text)
        if status == "RUNNING":
            self.label.setStyleSheet("background: transparent; color: #7CFF9A; font-weight: bold;")
        elif status == "STANDBY":
            self.label.setStyleSheet("background: transparent; color: #FFE14D; font-weight: bold;")
        else:
            self.label.setStyleSheet("background: transparent; color: #ddd; font-weight: normal;")
        self.setAccessibleName(text)


# =====================================================================
# SECTION: Blackout + Overlay base
# =====================================================================
class BlackoutWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setStyleSheet("background-color: black;")
        self.hide()

    def show_on_screen(self, screen):
        if screen is None:
            try:
                screen = QGuiApplication.primaryScreen()
            except RuntimeError:
                return
        if screen is None:
            return
        try:
            self.setGeometry(screen.geometry())
            handle = self.windowHandle()
            if handle:
                handle.setScreen(screen)
            self.show()
            self.raise_()
        except RuntimeError:
            pass

    def hide_blackout(self):
        self.hide()


class OverlayWindow(QWidget):
    """Frameless always-on-top output window with edit-mode drag/resize.

    Live GO must not steal keyboard focus (Space/Esc stay on the console).
    Edit / Test mode may activate the window so the operator can grab edges.
    """
    EDGE = 12

    def __init__(self, title="Overlay", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMinimumSize(200, 80)

        self.current_cue = None
        self._drag_pos = None
        self._resize_edge = None
        self.edit_mode = False
        self._layer = 50

    def set_edit_mode(self, enabled: bool):
        self.edit_mode = enabled
        if enabled:
            self.setStyleSheet(
                "background-color: rgba(0,0,0,200); border: 3px solid #00AAFF; border-radius: 6px;"
            )
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            self.raise_()
            self.activateWindow()
        else:
            self._restore_style()
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def _restore_style(self):
        self.setStyleSheet("background-color: rgba(0,0,0,160); border-radius: 10px;")

    def set_layer(self, layer: int):
        self._layer = max(0, min(100, layer))
        if not self.edit_mode:
            self.raise_()

    def set_opacity(self, value: float):
        self.setWindowOpacity(max(0.05, min(1.0, value)))

    def _hit_edge(self, pos: QPoint):
        r = self.rect()
        x, y = pos.x(), pos.y()
        e = self.EDGE
        left  = x < e
        right = x > r.width() - e
        top   = y < e
        bottom= y > r.height() - e
        if top and left:     return "top-left"
        if top and right:    return "top-right"
        if bottom and left:  return "bottom-left"
        if bottom and right: return "bottom-right"
        if left:   return "left"
        if right:  return "right"
        if top:    return "top"
        if bottom: return "bottom"
        return None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.edit_mode:
            edge = self._hit_edge(event.position().toPoint())
            if edge:
                self._resize_edge = edge
                self._drag_pos = event.globalPosition().toPoint()
                event.accept()
                return
        self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        self._resize_edge = None
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        global_pos = event.globalPosition().toPoint()

        if self.edit_mode and self._resize_edge is None:
            edge = self._hit_edge(event.position().toPoint())
            cursors = {
                "left": Qt.CursorShape.SizeHorCursor, "right": Qt.CursorShape.SizeHorCursor,
                "top": Qt.CursorShape.SizeVerCursor, "bottom": Qt.CursorShape.SizeVerCursor,
                "top-left": Qt.CursorShape.SizeFDiagCursor, "bottom-right": Qt.CursorShape.SizeFDiagCursor,
                "top-right": Qt.CursorShape.SizeBDiagCursor, "bottom-left": Qt.CursorShape.SizeBDiagCursor,
            }
            self.setCursor(cursors.get(edge, Qt.CursorShape.SizeAllCursor))

        if self._resize_edge and self.edit_mode:
            delta = global_pos - self._drag_pos
            geo = self.geometry()
            new_geo = QRect(geo)
            if "left" in self._resize_edge:   new_geo.setLeft(geo.left() + delta.x())
            if "right" in self._resize_edge:  new_geo.setRight(geo.right() + delta.x())
            if "top" in self._resize_edge:    new_geo.setTop(geo.top() + delta.y())
            if "bottom" in self._resize_edge: new_geo.setBottom(geo.bottom() + delta.y())
            if new_geo.width() >= 200 and new_geo.height() >= 80:
                self.setGeometry(new_geo)
                if self.current_cue:
                    self.current_cue.user_moved = True
                self._on_resized()
            self._drag_pos = global_pos
            event.accept()
            return

        if self._drag_pos is not None and self._resize_edge is None:
            self.move(global_pos - self._drag_pos)
            if self.current_cue:
                self.current_cue.user_moved = True
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        self._resize_edge = None
        # Persist geometry after every drag / resize in edit mode
        if self.edit_mode and self.current_cue is not None:
            geo = self.geometry()
            self.current_cue.pos_x = geo.x()
            self.current_cue.pos_y = geo.y()
            self.current_cue.width_px = geo.width()
            self.current_cue.height_px = geo.height()
            self.current_cue.user_moved = True
        event.accept()

    def _on_resized(self):
        pass

    def apply_geometry(self, cue, screen, defaults):
        if screen is None:
            try:
                screen = QGuiApplication.primaryScreen()
            except RuntimeError:
                return
        if screen is None:
            return

        try:
            sgeo = screen.availableGeometry()
        except RuntimeError:
            return

        if cue.user_moved or cue.size_mode == "pixels":
            w = max(200, cue.width_px)
            h = max(80, cue.height_px)
        else:
            w = max(200, int(sgeo.width()  * (cue.width_percent  / 100.0)))
            h = max(80,  int(sgeo.height() * (cue.height_percent / 100.0)))

        if cue.user_moved and cue.pos_x is not None and cue.pos_y is not None:
            self.setGeometry(int(cue.pos_x), int(cue.pos_y), w, h)
        else:
            key = {
                "Text": "text", "Image": "image", "Video": "video",
                "PDF": "pdf", "Link": "link"
            }.get(cue.cue_type, "text")
            default_rect = defaults.get(screen.name(), {}).get(key) if screen else None
            if default_rect and default_rect.isValid():
                self.setGeometry(default_rect)
            else:
                x = sgeo.x() + (sgeo.width()  - w) // 2
                y = sgeo.y() + (sgeo.height() - h) // 2
                self.setGeometry(x, y, w, h)

        try:
            handle = self.windowHandle()
            if handle and screen:
                handle.setScreen(screen)
        except RuntimeError:
            pass
        self._on_resized()

    def center_on_screen(self, screen=None):
        if screen is None:
            try:
                screen = QGuiApplication.primaryScreen()
            except RuntimeError:
                return
        if screen is None:
            return
        try:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width()  - self.width())  // 2,
                geo.y() + (geo.height() - self.height()) // 2
            )
            if self.current_cue:
                self.current_cue.user_moved = True
        except RuntimeError:
            pass

    def snap(self, edge: str, screen=None):
        if screen is None:
            try:
                screen = QGuiApplication.primaryScreen()
            except RuntimeError:
                return
        if screen is None:
            return
        try:
            geo = screen.availableGeometry()
            g = self.geometry()
            if edge == "top":
                self.move(g.x(), geo.y() + 20)
            elif edge == "bottom":
                self.move(g.x(), geo.y() + geo.height() - g.height() - 20)
            elif edge == "left":
                self.move(geo.x() + 20, g.y())
            elif edge == "right":
                self.move(geo.x() + geo.width() - g.width() - 20, g.y())
            if self.current_cue:
                self.current_cue.user_moved = True
        except RuntimeError:
            pass

    def clear_content(self):
        self.current_cue = None

    def close_window(self):
        self.hide()
        self.current_cue = None
        self.deleteLater()


# =====================================================================
# SECTION: Display windows (Text / Image / Video / PDF / Web)
# =====================================================================
class TextDisplayWindow(OverlayWindow):
    def __init__(self, parent=None):
        super().__init__("Text Output", parent)
        self.resize(900, 220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)          # tight 4-5 px inside blue frame
        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.label)

    def _restore_style(self):
        if self.current_cue:
            self.setStyleSheet(f"background-color: {self.current_cue.bg_color}; border-radius: 10px;")
        else:
            self.setStyleSheet("background-color: rgba(0,0,0,160); border-radius: 10px;")

    def show_text(self, cue, screen, defaults, steal_focus=True):
        self.current_cue = cue
        self.label.setText(cue.text or "")
        self.label.setStyleSheet(f"""
            color: {cue.text_color};
            font-size: {cue.font_size}px;
            font-family: "Segoe UI", Arial, sans-serif;
            font-weight: 500;
            background: transparent;
        """)
        if self.edit_mode:
            self.setStyleSheet("background-color: rgba(0,0,0,200); border: 3px solid #00AAFF; border-radius: 6px;")
        else:
            self._restore_style()
        self.set_opacity(cue.opacity)
        self.set_layer(cue.layer)
        self.apply_geometry(cue, screen, defaults)
        self.show()
        self.raise_()
        if steal_focus:
            self.activateWindow()


class ImageDisplayWindow(OverlayWindow):
    def __init__(self, parent=None):
        super().__init__("Image Output", parent)
        self.resize(800, 450)
        self.original_pixmap = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)          # tight 4 px inside blue frame
        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.label)

    def _restore_style(self):
        self.setStyleSheet("background-color: rgba(0,0,0,200); border-radius: 6px;")

    def show_image(self, cue, screen, defaults, steal_focus=True):
        self.current_cue = cue
        path = cue.image_path
        if not path or not os.path.exists(path):
            self.label.setText("(image not found)")
            self.original_pixmap = None
        else:
            self.original_pixmap = QPixmap(path)
            if self.original_pixmap.isNull():
                self.label.setText("(failed to load image)")
                self.original_pixmap = None
            else:
                self.label.setText("")
                self._apply_scaling(cue.scale_mode)

        if self.edit_mode:
            self.setStyleSheet("background-color: rgba(0,0,0,200); border: 3px solid #00AAFF; border-radius: 6px;")
        else:
            self._restore_style()

        self.set_opacity(cue.opacity)
        self.set_layer(cue.layer)
        self.apply_geometry(cue, screen, defaults)
        self.show()
        self.raise_()
        if steal_focus:
            self.activateWindow()

    def _on_resized(self):
        if self.current_cue and self.original_pixmap:
            self._apply_scaling(self.current_cue.scale_mode)

    def _apply_scaling(self, mode: str):
        if self.original_pixmap is None:
            return
        target = self.label.size()
        if target.width() < 10 or target.height() < 10:
            return
        pm = self.original_pixmap
        if mode == "Stretch":
            scaled = pm.scaled(target, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        elif mode == "Fill":
            scaled = pm.scaled(target, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        elif mode == "Center":
            scaled = pm
        else:
            scaled = pm.scaled(target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.label.setPixmap(scaled)


class VideoDisplayWindow(OverlayWindow):
    def __init__(self, parent=None):
        super().__init__("Video Output", parent)
        self.resize(1280, 720)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        self.video_widget = QVideoWidget()
        self.video_widget.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.player.setVideoOutput(self.video_widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        layout.addWidget(self.video_widget)

        self.current_cue = None

    def _restore_style(self):
        self.setStyleSheet("background-color: black;")

    def show_video(self, cue, screen, defaults, audio_device=None, steal_focus=True):
        self.current_cue = cue

        if not cue.video_path or not os.path.exists(cue.video_path):
            return

        if audio_device and not audio_device.isNull():
            self.audio_output.setDevice(audio_device)

        self.audio_output.setVolume(0.0 if cue.video_muted else cue.volume)
        self.audio_output.setMuted(cue.video_muted)

        self.player.setSource(QUrl.fromLocalFile(cue.video_path))
        self.player.setLoops(QMediaPlayer.Loops.Infinite if cue.video_loop else 1)

        self.set_opacity(cue.opacity)
        self.set_layer(cue.layer)
        self.apply_geometry(cue, screen, defaults)

        self.show()
        self.raise_()
        if steal_focus:
            self.activateWindow()

        def on_status(status):
            if status == QMediaPlayer.MediaStatus.LoadedMedia:
                self.player.play()
            elif status == QMediaPlayer.MediaStatus.InvalidMedia:
                print("Invalid video media")

        try:
            self.player.mediaStatusChanged.disconnect()
        except Exception:
            pass
        self.player.mediaStatusChanged.connect(on_status)

    def stop_video(self):
        self.player.stop()
        self.hide()
        self.current_cue = None

    def close_window(self):
        self.stop_video()
        super().close_window()


class PdfDisplayWindow(OverlayWindow):
    def __init__(self, parent=None):
        super().__init__("PDF Output", parent)
        self.resize(1000, 800)

        if not HAS_PDF:
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("PDF support requires QtPdf"))
            self.doc = None
            self.view = None
            return

        self.doc = QPdfDocument(self)
        self.view = QPdfView(self)
        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.SinglePage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitInView)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.current_cue = None

    def _restore_style(self):
        self.setStyleSheet("background-color: #222;")

    def show_pdf(self, cue, screen, defaults, steal_focus=True):
        if not HAS_PDF or self.doc is None:
            return
        self.current_cue = cue
        if not cue.pdf_path or not os.path.exists(cue.pdf_path):
            return
        self.doc.load(cue.pdf_path)
        count = self.doc.pageCount()
        if count <= 0:
            return

        # Multi-page scroll mode vs single page
        if getattr(cue, "pdf_multipage", False):
            self.view.setPageMode(QPdfView.PageMode.MultiPage)
        else:
            self.view.setPageMode(QPdfView.PageMode.SinglePage)

        page = max(0, min(int(cue.pdf_page), count - 1))
        self.view.pageNavigator().jump(page, QPoint(0, 0))

        if cue.pdf_zoom_mode == "FitWidth":
            self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        elif cue.pdf_zoom_mode == "Actual":
            self.view.setZoomMode(QPdfView.ZoomMode.Custom)
            self.view.setZoomFactor(1.0)
        else:
            self.view.setZoomMode(QPdfView.ZoomMode.FitInView)

        self.set_opacity(cue.opacity)
        self.set_layer(cue.layer)
        self.apply_geometry(cue, screen, defaults)
        self.show()
        self.raise_()
        if steal_focus:
            self.activateWindow()

    def goto_page(self, page: int):
        """Jump to zero-based page index (used by prev/next buttons)."""
        if not self.view or not self.doc:
            return
        count = self.doc.pageCount()
        page = max(0, min(page, count - 1))
        self.view.pageNavigator().jump(page, QPoint(0, 0))
        if self.current_cue is not None:
            self.current_cue.pdf_page = page

    def close_window(self):
        if self.doc:
            self.doc.close()
        super().close_window()


class WebDisplayWindow(OverlayWindow):
    def __init__(self, parent=None):
        super().__init__("Web Output", parent)
        self.resize(1280, 800)

        if not HAS_WEBENGINE:
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("QtWebEngine not available"))
            self.view = None
            return

        self.view = QWebEngineView(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.current_cue = None

    def _restore_style(self):
        self.setStyleSheet("background-color: #111;")

    def show_url(self, cue, screen, defaults, steal_focus=True):
        if not HAS_WEBENGINE or self.view is None:
            return
        self.current_cue = cue
        url = (cue.link_url or "").strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        self.view.setUrl(QUrl(url))
        self.set_opacity(cue.opacity)
        self.set_layer(cue.layer)
        self.apply_geometry(cue, screen, defaults)
        self.show()
        self.raise_()
        if steal_focus:
            self.activateWindow()

    def close_window(self):
        if self.view:
            self.view.setUrl(QUrl("about:blank"))
        super().close_window()


# =====================================================================
# SECTION: Waveform + Defaults dialog
# =====================================================================
class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(100)
        self.setStyleSheet("background-color:#1e1e1e; border:1px solid #555;")
        self.peaks = None
        self.filename = ""

    def set_file(self, path):
        self.filename = os.path.basename(path) if path else ""
        self.peaks = None
        if path and os.path.exists(path):
            try:
                data, _ = sf.read(path, dtype="float32")
                if data.ndim > 1:
                    data = data.mean(axis=1)
                target = 400
                block = max(1, len(data) // target)
                peaks = [np.max(np.abs(data[i:i+block])) for i in range(0, len(data), block)]
                self.peaks = np.array(peaks)
                self.peaks /= (self.peaks.max() + 1e-9)
            except Exception as e:
                print("Waveform error:", e)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1e1e1e"))
        if self.peaks is None or len(self.peaks) == 0:
            painter.setPen(QColor("#888"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No waveform")
            return
        w, h = self.width(), self.height()
        mid = h // 2
        pen = QPen(QColor("#4CAF50"))
        pen.setWidth(1)
        painter.setPen(pen)
        step = w / len(self.peaks)
        for i, peak in enumerate(self.peaks):
            x = int(i * step)
            amp = int(peak * (h * 0.42))
            painter.drawLine(x, mid - amp, x, mid + amp)
        painter.setPen(QColor("#ccc"))
        painter.drawText(8, 16, self.filename)


class DefaultPositionsDialog(QDialog):
    def __init__(self, screens, defaults, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Default Overlay Positions")
        self.setMinimumWidth(480)
        self.screens = screens
        self.defaults = deepcopy(defaults)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.screen_combo = QComboBox()
        for s in screens:
            try:
                self.screen_combo.addItem(
                    f"{s.name()}  {s.geometry().width()}×{s.geometry().height()}", s.name()
                )
            except RuntimeError:
                continue
        self.screen_combo.currentIndexChanged.connect(self.on_screen_changed)
        form.addRow("Display:", self.screen_combo)

        self.text_label = QLabel("-")
        form.addRow("Text default:", self.text_label)
        self.image_label = QLabel("-")
        form.addRow("Image default:", self.image_label)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        set_text_btn = QPushButton("Set Text default from current Edit window")
        set_text_btn.clicked.connect(lambda: self.capture("text"))
        btn_row.addWidget(set_text_btn)
        set_image_btn = QPushButton("Set Image default from current Edit window")
        set_image_btn.clicked.connect(lambda: self.capture("image"))
        btn_row.addWidget(set_image_btn)
        layout.addLayout(btn_row)

        note = QLabel("Tip: Put a Text or Image cue into Edit Mode, position it, then set the default.")
        note.setStyleSheet("color:#aaa; font-size:11px;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if self.screen_combo.count() > 0:
            self.on_screen_changed(0)

    def on_screen_changed(self, idx):
        name = self.screen_combo.itemData(idx)
        d = self.defaults.get(name, {})
        t = d.get("text")
        i = d.get("image")
        self.text_label.setText(
            f"{t.width()}×{t.height()} @ ({t.x()},{t.y()})" if t and t.isValid() else "(not set)"
        )
        self.image_label.setText(
            f"{i.width()}×{i.height()} @ ({i.x()},{i.y()})" if i and i.isValid() else "(not set)"
        )

    def capture(self, kind):
        self.pending_kind = kind
        self.accept()


# =====================================================================
# SECTION: Main Window
# =====================================================================
class MainWindow(QMainWindow):
    """Console: cue list, properties, GO/STOP transport, and playback engine."""
    AUTO_FIRE_MAX = 8

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CueControl Windows")
        self.setGeometry(80, 60, 1550, 920)
        self.setAcceptDrops(True)

        self.cues = []
        self.active_cues = {}
        self.current_cue_id = None
        self.fade_duration_ms = 2000
        self.current_show_path = None
        self._debounce_timers = {}
        self._drag_source_id = None
        self.active_timelines = {}   # group_id -> {start, fired, group}

        self.global_output_device = None
        self.available_devices = []
        self.available_screen_names = []

        self.refresh_audio_devices()
        self.refresh_screens()

        self.text_windows = {}
        self.image_windows = {}
        self.video_windows = {}
        self.pdf_windows = {}
        self.web_windows = {}
        self.display_defaults = {}
        self.blackout_window = BlackoutWindow()
        self.ui_scale = 100
        self._base_font_pt = QApplication.instance().font().pointSizeF() or 9.0

        self.device_check_timer = QTimer(self)
        self.device_check_timer.timeout.connect(self.check_audio_devices)
        self.device_check_timer.start(3000)

        self.screen_check_timer = QTimer(self)
        self.screen_check_timer.timeout.connect(self.check_screens)
        self.screen_check_timer.start(4000)

        self.build_ui()
        try:
            saved_scale = int(QSettings("CueControl", "CueControl").value("ui_scale", 100))
        except (TypeError, ValueError):
            saved_scale = 100
        self.apply_ui_scale(saved_scale, save=False, refresh=False)
        self.refresh_cue_list()
        self.update_running_list()
        self.update_window_title()
        self.cue_list.setFocus(Qt.FocusReason.OtherFocusReason)

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.update_running_list)
        self.ui_timer.start(300)

    def debounced(self, key, fn, ms=150):
        timer = self._debounce_timers.get(key)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            self._debounce_timers[key] = timer
        try:
            timer.timeout.disconnect()
        except Exception:
            pass
        timer.timeout.connect(fn)
        timer.start(ms)

    def update_window_title(self):
        name = os.path.basename(self.current_show_path) if self.current_show_path else "Untitled"
        self.setWindowTitle(f"CueControl Windows  –  {name}")

    # ------------------------------------------------------------------
    # Screen handling – never cache live QScreen objects
    # ------------------------------------------------------------------
    def refresh_screens(self):
        try:
            self.available_screen_names = [s.name() for s in QGuiApplication.screens()]
        except RuntimeError:
            self.available_screen_names = []

    def check_screens(self):
        try:
            current_names = {s.name() for s in QGuiApplication.screens()}
        except RuntimeError:
            self.refresh_screens()
            return

        old_names = set(getattr(self, "available_screen_names", []))
        if old_names == current_names:
            return

        self.available_screen_names = list(current_names)
        self.statusBar.showMessage("Display configuration changed")

        for window_dict in (self.text_windows, self.image_windows,
                            self.video_windows, self.pdf_windows, self.web_windows):
            to_remove = []
            for cue_id, win in list(window_dict.items()):
                cue = self.get_cue_by_id(cue_id)
                if cue and cue.screen_name and cue.screen_name not in current_names:
                    try:
                        win.close_window()
                    except RuntimeError:
                        pass
                    to_remove.append(cue_id)
                    if cue_id in self.active_cues:
                        del self.active_cues[cue_id]
            for cid in to_remove:
                if cid in window_dict:
                    del window_dict[cid]

        self.update_running_list()

        cue = self.get_current_cue()
        if cue and cue.cue_type in ("Text", "Image", "Video", "PDF", "Link"):
            self.populate_screen_combo(cue)

    def get_screen_by_name(self, name):
        try:
            screens = QGuiApplication.screens()
            if name:
                for s in screens:
                    if s.name() == name:
                        return s
            return QGuiApplication.primaryScreen()
        except RuntimeError:
            return None

    def screen_display_name(self, screen):
        if screen is None:
            return "Primary (Work Screen)"
        try:
            geo = screen.geometry()
            primary = " ★ Primary" if screen == QGuiApplication.primaryScreen() else ""
            nice = screen.name().replace("\\\\.\\", "").replace("\\", "")
            return f"{nice}  {geo.width()}×{geo.height()}{primary}"
        except RuntimeError:
            return "Unknown Screen"

    def populate_screen_combo(self, cue=None):
        self.screen_combo.blockSignals(True)
        self.screen_combo.clear()

        try:
            primary = QGuiApplication.primaryScreen()
            screens = QGuiApplication.screens()
        except RuntimeError:
            self.screen_combo.blockSignals(False)
            return

        if primary:
            self.screen_combo.addItem(self.screen_display_name(primary), primary.name())

        for s in screens:
            if s is primary:
                continue
            try:
                self.screen_combo.addItem(self.screen_display_name(s), s.name())
            except RuntimeError:
                continue

        if cue and cue.screen_name:
            idx = self.screen_combo.findData(cue.screen_name)
            self.screen_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.screen_combo.setCurrentIndex(0)

        self.screen_combo.blockSignals(False)

    def save_window_size_to_cue(self, cue, win):
        if not win or not cue:
            return

        try:
            geo = win.geometry()
        except RuntimeError:
            return

        screen = self.get_screen_by_name(cue.screen_name)
        if screen is None:
            return

        try:
            sgeo = screen.availableGeometry()
        except RuntimeError:
            return

        cue.width_px = geo.width()
        cue.height_px = geo.height()
        cue.width_percent = round(geo.width() / max(1, sgeo.width()) * 100, 1)
        cue.height_percent = round(geo.height() / max(1, sgeo.height()) * 100, 1)

        cue.pos_x = geo.x()
        cue.pos_y = geo.y()
        cue.user_moved = True

        try:
            handle = win.windowHandle()
            if handle is not None and handle.screen() is not None:
                cue.screen_name = handle.screen().name()
                self.populate_screen_combo(cue)
        except RuntimeError:
            pass

        self.width_px_spin.blockSignals(True)
        self.width_px_spin.setValue(cue.width_px)
        self.width_px_spin.blockSignals(False)

        self.height_px_spin.blockSignals(True)
        self.height_px_spin.setValue(cue.height_px)
        self.height_px_spin.blockSignals(False)

        self.width_percent_spin.blockSignals(True)
        self.width_percent_spin.setValue(cue.width_percent)
        self.width_percent_spin.blockSignals(False)

        self.height_percent_spin.blockSignals(True)
        self.height_percent_spin.setValue(cue.height_percent)
        self.height_percent_spin.blockSignals(False)

        self.statusBar.showMessage(
            f"Position locked: {cue.width_px}×{cue.height_px} @ ({cue.pos_x},{cue.pos_y}) on {cue.screen_name or 'primary'}"
        )

      # ------------------------------------------------------------------
    # Drag & Drop
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.handle_external_file_drop(event.mimeData().urls())
            event.acceptProposedAction()

    def cue_list_drag_enter(self, event):
        if event.mimeData().hasUrls() or event.source() is self.cue_list:
            event.acceptProposedAction()
        else:
            event.ignore()

    def cue_list_drag_move(self, event):
        if event.mimeData().hasUrls() or event.source() is self.cue_list:
            event.acceptProposedAction()
        else:
            event.ignore()

    def cue_list_drop_event(self, event):
        # External files from Explorer
        if event.mimeData().hasUrls():
            self.handle_external_file_drop(event.mimeData().urls())
            event.acceptProposedAction()
            return

        # Internal reorder / group only
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
    def handle_external_file_drop(self, urls):
        created = 0
        last_id = None
        for url in urls:
            path = url.toLocalFile()
            if not path or not os.path.isfile(path):
                continue

            ext = os.path.splitext(path)[1].lower()
            name = os.path.splitext(os.path.basename(path))[0]
            next_num = max((c.number for c in self.cues), default=0) + 1

            if ext in (".mp3", ".wav", ".ogg", ".flac", ".m4a"):
                cue = Cue(next_num, name, "Audio", "Auto-Ready")
                cue.media_path = path
                cue.duration_ms = self.get_audio_duration_ms(path)
                self.cues.append(cue)
                last_id = cue.id
                created += 1

            elif ext in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"):
                cue = Cue(next_num, name, "Video", "Auto-Ready")
                cue.video_path = path
                primary = QGuiApplication.primaryScreen()
                if primary:
                    cue.screen_name = primary.name()
                self.cues.append(cue)
                last_id = cue.id
                created += 1

            elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"):
                cue = Cue(next_num, name, "Image", "Auto-Ready")
                cue.image_path = path
                cue.duration_ms = 5000
                primary = QGuiApplication.primaryScreen()
                if primary:
                    cue.screen_name = primary.name()
                self.cues.append(cue)
                last_id = cue.id
                created += 1

            elif ext == ".pdf":
                if not HAS_PDF:
                    self.statusBar.showMessage("PDF support not available")
                    continue
                cue = Cue(next_num, name, "PDF", "Auto-Ready")
                cue.pdf_path = path
                primary = QGuiApplication.primaryScreen()
                if primary:
                    cue.screen_name = primary.name()
                self.cues.append(cue)
                last_id = cue.id
                created += 1

        if created:
            self.refresh_cue_list()
            self.statusBar.showMessage(f"Added {created} cue(s) from dropped files")
            if last_id:
                self.select_cue_by_id(last_id)

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
            self.statusBar.showMessage(f'Moved "{source_cue.name}"')
            return

        if target_cue is None:
            source_cue.number = others[-1].number + 1.0
        else:
            idx = next(
                (i for i, c in enumerate(others) if c.id == target_cue.id),
                len(others),
            )
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
            f'Moved "{source_cue.name}" → cue {source_cue.number}'
        )
    def add_cue_to_group(self, child_cue, group_cue):
        if child_cue.id == group_cue.id:
            return
        if child_cue.cue_type == "Group" or child_cue.is_group:
            self.statusBar.showMessage("Nesting groups is not supported in this version")
            return

        # Remove from previous group if any
        if child_cue.parent_id:
            old_group = self.get_cue_by_id(child_cue.parent_id)
            if old_group and child_cue.id in old_group.group_children:
                old_group.group_children.remove(child_cue.id)

        child_cue.parent_id = group_cue.id
        if child_cue.id not in group_cue.group_children:
            group_cue.group_children.append(child_cue.id)
        if not hasattr(child_cue, "timeline_offset_ms"):
            child_cue.timeline_offset_ms = 0

        self.refresh_cue_list()
        self.statusBar.showMessage(f'Added "{child_cue.name}" to group "{group_cue.name}"')
    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------
    def new_show(self):
        """Clear the cue list after an optional confirm."""
        if self.cues:
            reply = QMessageBox.question(
                self, "New Show",
                "Create a new show? Unsaved changes will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.stop_all()
        self.cues.clear()
        self.current_cue_id = None
        self.current_show_path = None
        self.display_defaults.clear()
        self.refresh_cue_list()
        self.update_window_title()
        self.statusBar.showMessage("New show created")

    def save_show(self, force_dialog=False):
        """Write the current show to a .ccs file (atomic replace)."""
        if self.current_show_path and not force_dialog:
            path = self.current_show_path
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Show", "", "CueControl Show (*.ccs);;All Files (*)"
            )
            if not path:
                return
            if not path.lower().endswith(".ccs"):
                path += ".ccs"

        data = {
            "version": 1,
            "fade_duration_ms": self.fade_duration_ms,
            "display_defaults": {
                k: {kk: [v.x(), v.y(), v.width(), v.height()]
                    for kk, v in d.items() if isinstance(v, QRect)}
                for k, d in self.display_defaults.items()
            },
            "cues": [cue_to_dict(c) for c in self.cues]
        }

        try:
            _atomic_write_json(path, data)
            self.current_show_path = path
            self.update_window_title()
            self.statusBar.showMessage(f"Saved: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save show:\n{e}")

    def load_show(self):
        """Open a .ccs show. Corrupt cues are skipped; the rest still load."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Show", "", "CueControl Show (*.ccs);;All Files (*)"
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not open show:\n{e}")
            return

        if not isinstance(data, dict):
            QMessageBox.critical(self, "Load Error", "This file is not a CueControl show.")
            return

        self.stop_all()
        self.cues.clear()
        self.current_cue_id = None

        skipped = 0
        for cdata in data.get("cues", []):
            try:
                if not isinstance(cdata, dict):
                    skipped += 1
                    continue
                self.cues.append(cue_from_dict(cdata))
            except Exception as e:
                skipped += 1
                name = cdata.get("name", "?") if isinstance(cdata, dict) else "?"
                print(f"Skipped a corrupt cue while loading ({name!r}): {e}")

        self.repair_cue_links()

        if skipped:
            QMessageBox.warning(
                self, "Show Partially Loaded",
                f"{skipped} cue(s) in this file were corrupted and had to be skipped.\n"
                "Check the remaining cue list before the show, and consider re-saving "
                "a clean copy once you've confirmed everything is intact."
            )

        self.fade_duration_ms = _safe_num(data, "fade_duration_ms", 2000, int)
        if self.fade_duration_ms < 1:
            self.fade_duration_ms = 2000

        self.display_defaults.clear()
        defaults = data.get("display_defaults") or {}
        if isinstance(defaults, dict):
            for screen_name, kinds in defaults.items():
                if not isinstance(kinds, dict):
                    continue
                self.display_defaults[screen_name] = {}
                for kind, rect_list in kinds.items():
                    if isinstance(rect_list, list) and len(rect_list) == 4:
                        try:
                            self.display_defaults[screen_name][kind] = QRect(*rect_list)
                        except (TypeError, ValueError):
                            pass

        self.current_show_path = path
        self.refresh_cue_list()
        self.update_window_title()
        self.statusBar.showMessage(f"Loaded: {os.path.basename(path)}  ({len(self.cues)} cues)")

        if self.cues:
            first = sorted(self.cues, key=lambda c: c.number)[0]
            self.select_cue_by_id(first.id)

    # ------------------------------------------------------------------
    def get_cue_by_id(self, cue_id):
        return next((c for c in self.cues if c.id == cue_id), None)

    def get_current_cue(self):
        return self.get_cue_by_id(self.current_cue_id)

    def select_cue_by_id(self, cue_id):
        self.current_cue_id = cue_id
        self.refresh_cue_list()
        for i in range(self.cue_list.count()):
            item = self.cue_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == cue_id:
                self.cue_list.setCurrentItem(item)
                self.on_cue_selected(item)
                break

    def refresh_audio_devices(self):
        self.available_devices = QMediaDevices.audioOutputs()
        if not self.global_output_device and self.available_devices:
            default = QMediaDevices.defaultAudioOutput()
            self.global_output_device = default if not default.isNull() else self.available_devices[0]

    def check_audio_devices(self):
        old_ids = {device_id_to_str(d.id()) for d in self.available_devices}
        self.refresh_audio_devices()
        new_ids = {device_id_to_str(d.id()) for d in self.available_devices}
        if old_ids != new_ids:
            self.statusBar.showMessage("Audio devices changed")
            if self.global_output_device and device_id_to_str(self.global_output_device.id()) not in new_ids:
                self.global_output_device = QMediaDevices.defaultAudioOutput()
            cue = self.get_current_cue()
            if cue:
                self.populate_device_combo(cue)

    def get_device_by_id(self, device_id):
        if device_id is None:
            return self.global_output_device
        for d in self.available_devices:
            if device_id_to_str(d.id()) == device_id:
                return d
        return self.global_output_device

    def create_player(self, cue):
        player = QMediaPlayer(self)
        output = QAudioOutput(self)
        device = self.get_device_by_id(cue.audio_device_id)
        if device and not device.isNull():
            output.setDevice(device)
        output.setVolume(cue.volume)
        player.setAudioOutput(output)
        return player, output

    def get_or_create_window(self, cue):
        if cue.cue_type == "Text":
            if cue.id not in self.text_windows:
                self.text_windows[cue.id] = TextDisplayWindow()
            return self.text_windows[cue.id]
        elif cue.cue_type == "Image":
            if cue.id not in self.image_windows:
                self.image_windows[cue.id] = ImageDisplayWindow()
            return self.image_windows[cue.id]
        elif cue.cue_type == "Video":
            if cue.id not in self.video_windows:
                self.video_windows[cue.id] = VideoDisplayWindow()
            return self.video_windows[cue.id]
        elif cue.cue_type == "PDF":
            if cue.id not in self.pdf_windows:
                self.pdf_windows[cue.id] = PdfDisplayWindow()
            return self.pdf_windows[cue.id]
        elif cue.cue_type == "Link":
            if cue.id not in self.web_windows:
                self.web_windows[cue.id] = WebDisplayWindow()
            return self.web_windows[cue.id]
        return None

    def destroy_window(self, cue):
        mapping = {
            "Text": self.text_windows,
            "Image": self.image_windows,
            "Video": self.video_windows,
            "PDF": self.pdf_windows,
            "Link": self.web_windows,
        }
        windows = mapping.get(cue.cue_type)
        if windows and cue.id in windows:
            windows[cue.id].close_window()
            del windows[cue.id]

    # ------------------------------------------------------------------
    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        toolbar = QToolBar("Cue Types")
        toolbar.setOrientation(Qt.Vertical)
        toolbar.setFixedWidth(160)
        toolbar.setAccessibleName("Add cues")
        toolbar.setMovable(False)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)

        toolbar.addWidget(QLabel("  Add Cues"))
        toolbar.addSeparator()
        for text, slot in [
            ("Audio", self.add_audio_cue),
            ("Video", self.add_video_cue),
            ("Image", self.add_image_cue),
            ("PDF", self.add_pdf_cue),
            ("Link", self.add_link_cue),
            ("Text", self.add_text_cue),
            ("OSC", self.add_osc_cue),
        ]:
            a = QAction(text, self)
            a.triggered.connect(slot)
            toolbar.addAction(a)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel("  Automation"))
        toolbar.addSeparator()
        for text, slot in [
            ("Stop & Fade", self.add_stop_fade_cue),
            ("Stop", self.add_stop_cue),
            ("Crossfade", self.add_crossfade_cue),
            ("Wait", self.add_wait_cue),
            ("Group", self.add_group_cue),
            ("Start", self.add_start_cue),
        ]:
            a = QAction(text, self)
            a.triggered.connect(slot)
            toolbar.addAction(a)

        content = QVBoxLayout()
        split = QHBoxLayout()

        self.cue_list = QListWidget()
        self.cue_list.setAccessibleName("Cue list")
        self.cue_list.setAccessibleDescription(
            "Standby cue is selected. Space or GO fires it. Status is spoken as STANDBY or RUNNING."
        )
        self.cue_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cue_list.itemClicked.connect(self.on_cue_selected)

        # Drag & Drop
        self.cue_list.setDragEnabled(True)
        self.cue_list.setAcceptDrops(True)
        self.cue_list.setDropIndicatorShown(True)
        self.cue_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.cue_list.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.cue_list.viewport().setAcceptDrops(True)
        self.cue_list.dropEvent = self.cue_list_drop_event
        self.cue_list.dragEnterEvent = self.cue_list_drag_enter
        self.cue_list.dragMoveEvent = self.cue_list_drag_move
        self.cue_list.mousePressEvent = self.cue_list_mouse_press

        split.addWidget(self.cue_list, stretch=2)

        right_tabs = QTabWidget()
        right_tabs.setMinimumWidth(520)
        right_tabs.setAccessibleName("Cue properties and running cues")

        # ---------- Properties tab ----------
        prop_tab = QWidget()
        prop_layout = QVBoxLayout(prop_tab)
        form = QFormLayout()

        self.number_spin = QDoubleSpinBox()
        self.number_spin.setRange(0.1, 9999.9)
        self.number_spin.setDecimals(1)
        self.number_spin.setSingleStep(1.0)
        self.number_spin.editingFinished.connect(self.apply_cue_number)
        self.number_spin.setAccessibleName("Cue number")
        form.addRow("Cue Number:", self.number_spin)

        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.apply_name_change)
        self.name_edit.setAccessibleName("Cue name")
        form.addRow("Name:", self.name_edit)

        self.type_label = QLabel("-")
        form.addRow("Type:", self.type_label)

        self.follow_combo = QComboBox()
        self.follow_combo.addItems(["Off", "Auto-Ready", "Auto-Follow", "Auto-Fire"])
        self.follow_combo.currentTextChanged.connect(self.apply_follow_mode)
        form.addRow("Follow Mode:", self.follow_combo)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 36000)
        self.duration_spin.setSuffix(" sec")
        self.duration_spin.setSpecialValueText("Infinite (0)")
        self.duration_spin.valueChanged.connect(self.apply_duration)
        form.addRow("Duration:", self.duration_spin)

        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self.apply_device)
        form.addRow("Audio Output:", self.device_combo)

        self.file_label = QLabel("-")
        self.file_label.setWordWrap(True)
        form.addRow("File / URL:", self.file_label)

        prop_layout.addLayout(form)

        # Volume group
        self.volume_group = QGroupBox("Volume")
        vol_layout = QHBoxLayout(self.volume_group)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.volume_slider.setTickInterval(10)
        self.volume_slider.setAccessibleName("Volume")
        self.volume_slider.setAccessibleDescription("Cue volume, 0 to 100 percent")
        self.volume_slider.valueChanged.connect(self.apply_volume)

        self.volume_spin = QSpinBox()
        self.volume_spin.setRange(0, 100)
        self.volume_spin.setSuffix("%")
        self.volume_spin.setValue(100)
        self.volume_spin.valueChanged.connect(self.on_volume_spin_changed)

        vol_layout.addWidget(QLabel("Level:"))
        vol_layout.addWidget(self.volume_slider, 1)
        vol_layout.addWidget(self.volume_spin)

        prop_layout.addWidget(self.volume_group)
        self.volume_group.hide()

        # Overlay group
        self.overlay_group = QGroupBox("Display / Layer / Opacity / Size")
        ol = QVBoxLayout(self.overlay_group)

        screen_row = QHBoxLayout()
        screen_row.addWidget(QLabel("Display:"))
        self.screen_combo = QComboBox()
        self.screen_combo.currentIndexChanged.connect(self.apply_screen)
        screen_row.addWidget(self.screen_combo, 1)
        self.blackout_btn = QPushButton("Blackout")
        self.blackout_btn.setCheckable(True)
        self.blackout_btn.setAccessibleName("Blackout")
        self.blackout_btn.setAccessibleDescription("Hide all projector output until turned off")
        self.blackout_btn.toggled.connect(self.toggle_blackout)
        screen_row.addWidget(self.blackout_btn)
        ol.addLayout(screen_row)

        lo_row = QHBoxLayout()
        lo_row.addWidget(QLabel("Layer:"))
        self.layer_spin = QSpinBox()
        self.layer_spin.setRange(0, 100)
        self.layer_spin.setValue(50)
        self.layer_spin.valueChanged.connect(self.apply_layer)
        lo_row.addWidget(self.layer_spin)
        lo_row.addSpacing(15)
        lo_row.addWidget(QLabel("Opacity:"))
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(5, 100)
        self.opacity_spin.setValue(100)
        self.opacity_spin.setSuffix("%")
        self.opacity_spin.valueChanged.connect(self.apply_opacity)
        lo_row.addWidget(self.opacity_spin)
        lo_row.addStretch()
        ol.addLayout(lo_row)

        self.test_cb = QCheckBox("Test / Preview this cue")
        self.test_cb.toggled.connect(self.on_test_toggled)
        ol.addWidget(self.test_cb)

        self.edit_mode_cb = QCheckBox("Edit Mode  (blue border + drag edges to resize)")
        self.edit_mode_cb.toggled.connect(self.on_edit_mode_toggled)
        ol.addWidget(self.edit_mode_cb)

        align_row = QHBoxLayout()
        for label, slot in [
            ("Center", self.align_center),
            ("Top", lambda: self.align_snap("top")),
            ("Bottom", lambda: self.align_snap("bottom")),
            ("Left", lambda: self.align_snap("left")),
            ("Right", lambda: self.align_snap("right")),
        ]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            align_row.addWidget(b)
        ol.addLayout(align_row)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Size mode:"))
        self.size_mode_combo = QComboBox()
        self.size_mode_combo.addItems(["% of Display", "Custom (pixels)"])
        self.size_mode_combo.currentIndexChanged.connect(self.on_size_mode_changed)
        mode_row.addWidget(self.size_mode_combo, 1)
        ol.addLayout(mode_row)

        self.percent_widget = QWidget()
        pl = QHBoxLayout(self.percent_widget)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.addWidget(QLabel("W %:"))
        self.width_percent_spin = QDoubleSpinBox()
        self.width_percent_spin.setRange(5, 100)
        self.width_percent_spin.setDecimals(1)
        self.width_percent_spin.setValue(80)
        self.width_percent_spin.setSuffix("%")
        self.width_percent_spin.valueChanged.connect(self.apply_size_settings)
        pl.addWidget(self.width_percent_spin)
        pl.addWidget(QLabel("H %:"))
        self.height_percent_spin = QDoubleSpinBox()
        self.height_percent_spin.setRange(5, 100)
        self.height_percent_spin.setDecimals(1)
        self.height_percent_spin.setValue(60)
        self.height_percent_spin.setSuffix("%")
        self.height_percent_spin.valueChanged.connect(self.apply_size_settings)
        pl.addWidget(self.height_percent_spin)
        ol.addWidget(self.percent_widget)

        self.pixel_widget = QWidget()
        px = QHBoxLayout(self.pixel_widget)
        px.setContentsMargins(0, 0, 0, 0)
        px.addWidget(QLabel("W:"))
        self.width_px_spin = QSpinBox()
        self.width_px_spin.setRange(200, 4000)
        self.width_px_spin.setValue(1280)
        self.width_px_spin.setSuffix("px")
        self.width_px_spin.valueChanged.connect(self.apply_size_settings)
        px.addWidget(self.width_px_spin)
        px.addWidget(QLabel("H:"))
        self.height_px_spin = QSpinBox()
        self.height_px_spin.setRange(80, 2000)
        self.height_px_spin.setValue(720)
        self.height_px_spin.setSuffix("px")
        self.height_px_spin.valueChanged.connect(self.apply_size_settings)
        px.addWidget(self.height_px_spin)
        ol.addWidget(self.pixel_widget)
        self.pixel_widget.hide()

        prop_layout.addWidget(self.overlay_group)
        self.overlay_group.hide()

        # Text group
        self.text_group = QGroupBox("Text Content")
        tl = QVBoxLayout(self.text_group)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Type the text…")
        self.text_edit.setMinimumHeight(70)
        self.text_edit.textChanged.connect(self.apply_text_content)
        tl.addWidget(self.text_edit)
        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("Font size:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 200)
        self.font_size_spin.setValue(64)
        self.font_size_spin.valueChanged.connect(self.apply_font_size)
        style_row.addWidget(self.font_size_spin)
        style_row.addSpacing(10)
        style_row.addWidget(QLabel("Color:"))
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(42, 26)
        self.color_btn.setStyleSheet("background-color:#FFFFFF; border:1px solid #888;")
        self.color_btn.clicked.connect(self.pick_text_color)
        style_row.addWidget(self.color_btn)
        style_row.addStretch()
        tl.addLayout(style_row)
        prop_layout.addWidget(self.text_group)
        self.text_group.hide()

        # Image group
        self.image_group = QGroupBox("Image Content")
        il = QVBoxLayout(self.image_group)
        file_row = QHBoxLayout()
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setReadOnly(True)
        file_row.addWidget(self.image_path_edit, 1)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self.browse_image)
        file_row.addWidget(browse_btn)
        il.addLayout(file_row)
        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Scale mode:"))
        self.scale_mode_combo = QComboBox()
        self.scale_mode_combo.addItems(["Fit", "Fill", "Stretch", "Center"])
        self.scale_mode_combo.currentTextChanged.connect(self.apply_scale_mode)
        scale_row.addWidget(self.scale_mode_combo, 1)
        il.addLayout(scale_row)
        self.image_persistent_cb = QCheckBox("Persistent (replaces previous persistent image)")
        self.image_persistent_cb.setChecked(True)
        self.image_persistent_cb.toggled.connect(self.apply_image_persistent)
        il.addWidget(self.image_persistent_cb)
        prop_layout.addWidget(self.image_group)
        self.image_group.hide()

        # Video group
        self.video_group = QGroupBox("Video Content")
        vl = QVBoxLayout(self.video_group)
        vfile_row = QHBoxLayout()
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setReadOnly(True)
        vfile_row.addWidget(self.video_path_edit, 1)
        vbrowse_btn = QPushButton("Browse…")
        vbrowse_btn.clicked.connect(self.browse_video)
        vfile_row.addWidget(vbrowse_btn)
        vl.addLayout(vfile_row)
        vopts = QHBoxLayout()
        self.video_loop_cb = QCheckBox("Loop")
        self.video_loop_cb.toggled.connect(self.apply_video_loop)
        vopts.addWidget(self.video_loop_cb)
        self.video_mute_cb = QCheckBox("Mute")
        self.video_mute_cb.toggled.connect(self.apply_video_mute)
        vopts.addWidget(self.video_mute_cb)
        vopts.addStretch()
        vl.addLayout(vopts)
        prop_layout.addWidget(self.video_group)
        self.video_group.hide()

        # PDF group
        self.pdf_group = QGroupBox("PDF Content")
        playout = QVBoxLayout(self.pdf_group)
        pfile_row = QHBoxLayout()
        self.pdf_path_edit = QLineEdit()
        self.pdf_path_edit.setReadOnly(True)
        pfile_row.addWidget(self.pdf_path_edit, 1)
        pbrowse = QPushButton("Browse…")
        pbrowse.clicked.connect(self.browse_pdf)
        pfile_row.addWidget(pbrowse)
        playout.addLayout(pfile_row)
        page_row = QHBoxLayout()
        page_row.addWidget(QLabel("Start page:"))
        self.pdf_page_spin = QSpinBox()
        self.pdf_page_spin.setRange(1, 9999)
        self.pdf_page_spin.setValue(1)
        self.pdf_page_spin.valueChanged.connect(self.apply_pdf_page)
        page_row.addWidget(self.pdf_page_spin)
        page_row.addWidget(QLabel("Zoom:"))
        self.pdf_zoom_combo = QComboBox()
        self.pdf_zoom_combo.addItems(["Fit", "FitWidth", "Actual"])
        self.pdf_zoom_combo.currentTextChanged.connect(self.apply_pdf_zoom)
        page_row.addWidget(self.pdf_zoom_combo)
        page_row.addStretch()
        playout.addLayout(page_row)

        # Multipage / navigation
        multi_row = QHBoxLayout()
        self.pdf_multipage_cb = QCheckBox("Show all pages (scroll)")
        self.pdf_multipage_cb.toggled.connect(self.apply_pdf_multipage)
        multi_row.addWidget(self.pdf_multipage_cb)
        self.pdf_prev_btn = QPushButton("◀ Prev")
        self.pdf_prev_btn.clicked.connect(self.pdf_prev_page)
        multi_row.addWidget(self.pdf_prev_btn)
        self.pdf_next_btn = QPushButton("Next ▶")
        self.pdf_next_btn.clicked.connect(self.pdf_next_page)
        multi_row.addWidget(self.pdf_next_btn)
        multi_row.addStretch()
        playout.addLayout(multi_row)

        if not HAS_PDF:
            warn = QLabel("⚠ QtPdf not available – PDF cues disabled")
            warn.setStyleSheet("color: #ff8888;")
            playout.addWidget(warn)
        prop_layout.addWidget(self.pdf_group)
        self.pdf_group.hide()

        # Link group
        self.link_group = QGroupBox("Link / Web Content")
        llayout = QVBoxLayout(self.link_group)
        self.link_url_edit = QLineEdit()
        self.link_url_edit.setPlaceholderText("https://…")
        self.link_url_edit.editingFinished.connect(self.apply_link_url)
        llayout.addWidget(self.link_url_edit)

        self.link_system_cb = QCheckBox("Open in system browser instead of embedded window")
        self.link_system_cb.toggled.connect(self.apply_link_system)
        llayout.addWidget(self.link_system_cb)

        note = QLabel(
            "Unchecked = opens inside CueControl on the selected display\n"
            "Checked = opens in the computer’s default browser"
        )
        note.setStyleSheet("color:#aaa; font-size:11px;")
        llayout.addWidget(note)

        if not HAS_WEBENGINE:
            warn = QLabel("⚠ QtWebEngine not available – only system browser mode works")
            warn.setStyleSheet("color: #ff8888;")
            llayout.addWidget(warn)

        prop_layout.addWidget(self.link_group)
        self.link_group.hide()

        # OSC group
        self.osc_group = QGroupBox("OSC / Network")
        olayout = QVBoxLayout(self.osc_group)

        if not HAS_OSC:
            warn = QLabel("⚠ python-osc not installed. Run: pip install python-osc")
            warn.setStyleSheet("color: #ff8888;")
            olayout.addWidget(warn)

        form_osc = QFormLayout()

        self.osc_preset_combo = QComboBox()
        self.osc_preset_combo.addItems(list(OSC_PRESETS.keys()))
        self.osc_preset_combo.currentTextChanged.connect(self.on_osc_preset_changed)
        form_osc.addRow("Console Preset:", self.osc_preset_combo)

        self.osc_common_combo = QComboBox()
        self.osc_common_combo.currentIndexChanged.connect(self.on_osc_common_changed)
        form_osc.addRow("Common Command:", self.osc_common_combo)

        self.osc_ip_edit = QLineEdit("127.0.0.1")
        self.osc_ip_edit.editingFinished.connect(self.apply_osc_settings)
        form_osc.addRow("Target IP:", self.osc_ip_edit)

        self.osc_port_spin = QSpinBox()
        self.osc_port_spin.setRange(1, 65535)
        self.osc_port_spin.setValue(8000)
        self.osc_port_spin.valueChanged.connect(self.apply_osc_settings)
        form_osc.addRow("Port:", self.osc_port_spin)

        self.osc_address_edit = QLineEdit()
        self.osc_address_edit.setPlaceholderText("/eos/cue/fire")
        self.osc_address_edit.editingFinished.connect(self.apply_osc_settings)
        form_osc.addRow("OSC Address:", self.osc_address_edit)

        self.osc_args_edit = QLineEdit()
        self.osc_args_edit.setPlaceholderText("1.5   or   Go+   or   leave empty")
        self.osc_args_edit.editingFinished.connect(self.apply_osc_settings)
        form_osc.addRow("Arguments:", self.osc_args_edit)

        olayout.addLayout(form_osc)

        hint = QLabel("Arguments are comma-separated. Numbers are sent as float/int automatically.")
        hint.setStyleSheet("color:#aaa; font-size:11px;")
        olayout.addWidget(hint)

        prop_layout.addWidget(self.osc_group)
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

        # Waveform
        self.wave_group = QGroupBox("Waveform")
        wl = QVBoxLayout(self.wave_group)
        self.waveform = WaveformWidget()
        wl.addWidget(self.waveform)
        prop_layout.addWidget(self.wave_group)

        prop_layout.addStretch()
        right_tabs.addTab(prop_tab, "Properties")

        # Running tab
        run_tab = QWidget()
        rl = QVBoxLayout(run_tab)
        rl.addWidget(QLabel("Cues Currently Running"))
        self.running_list = QListWidget()
        self.running_list.setAccessibleName("Cues currently running")
        rl.addWidget(self.running_list)
        right_tabs.addTab(run_tab, "Cues Running")

        split.addWidget(right_tabs, stretch=1)
        content.addLayout(split)

        # GO / STOP bar – equal-width rounded controls
        bar = QFrame()
        bar.setObjectName("transportBar")
        self.transport_bar = bar
        bar.setFixedHeight(88)
        bar.setStyleSheet("""
            QFrame#transportBar {
                background-color: #1a1a1a;
                border-top: 1px solid #444;
            }
        """)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(12)

        btn_base = """
            QPushButton {
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: 3px solid transparent;
                border-radius: 12px;
                padding: 14px 20px;
                min-height: 56px;
            }
            QPushButton:pressed {
                padding-top: 16px;
                padding-bottom: 12px;
            }
            QPushButton:focus {
                border: 3px solid #FFE14D;
            }
        """

        self.go_btn = QPushButton("GO")
        self.go_btn.setAccessibleName("GO")
        self.go_btn.setAccessibleDescription("Fire the standby cue. Keyboard shortcut: Space")
        self.go_btn.setToolTip("GO  (Space)")
        self.go_btn.setStyleSheet(btn_base + """
            QPushButton {
                background-color: #00AA00;
            }
            QPushButton:hover {
                background-color: #00CC22;
            }
            QPushButton:pressed {
                background-color: #008800;
            }
        """)
        self.go_btn.clicked.connect(self.go_pressed)

        self.stop_btn = QPushButton("STOP ALL")
        self.stop_btn.setAccessibleName("STOP ALL")
        self.stop_btn.setAccessibleDescription("Hard-stop every running cue")
        self.stop_btn.setToolTip("STOP ALL")
        self.stop_btn.setStyleSheet(btn_base + """
            QPushButton {
                background-color: #CC0000;
            }
            QPushButton:hover {
                background-color: #EE2222;
            }
            QPushButton:pressed {
                background-color: #990000;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_all)

        self.fade_btn = QPushButton("Fade & Stop")
        self.fade_btn.setAccessibleName("Fade and Stop")
        self.fade_btn.setAccessibleDescription("Fade out then stop. Keyboard shortcut: Escape")
        self.fade_btn.setToolTip("Fade & Stop  (Esc)")
        self.fade_btn.setStyleSheet(btn_base + """
            QPushButton {
                background-color: #CC7700;
            }
            QPushButton:hover {
                background-color: #EE9900;
            }
            QPushButton:pressed {
                background-color: #AA5500;
            }
        """)
        self.fade_btn.clicked.connect(self.fade_and_stop)

        bl.addWidget(self.go_btn, 1)
        bl.addWidget(self.stop_btn, 1)
        bl.addWidget(self.fade_btn, 1)
        content.addWidget(bar)
        main_layout.addLayout(content)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready – drag files or cues to reorder / group")

        # Space / Esc: WindowShortcut so QLineEdit still types spaces,
        # auto-repeat off so a held key cannot GO-walk or stack fades.
        space_sc = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space_sc.setAutoRepeat(False)
        space_sc.setContext(Qt.ShortcutContext.WindowShortcut)
        space_sc.activated.connect(self.go_pressed)
        esc_sc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_sc.setAutoRepeat(False)
        esc_sc.setContext(Qt.ShortcutContext.WindowShortcut)
        esc_sc.activated.connect(self.fade_and_stop)

        delete_action = QAction("Delete Cue", self)
        delete_action.setShortcut(QKeySequence("Ctrl+Delete"))
        delete_action.triggered.connect(self.delete_selected_cue)
        self.addAction(delete_action)

        # Menu
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        new_act = QAction("New Show", self)
        new_act.setShortcut(QKeySequence.StandardKey.New)
        new_act.triggered.connect(self.new_show)
        file_menu.addAction(new_act)

        open_act = QAction("Open Show…", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self.load_show)
        file_menu.addAction(open_act)

        save_act = QAction("Save", self)
        save_act.setShortcut(QKeySequence.StandardKey.Save)
        save_act.triggered.connect(lambda: self.save_show(False))
        file_menu.addAction(save_act)

        save_as_act = QAction("Save As…", self)
        save_as_act.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_act.triggered.connect(lambda: self.save_show(True))
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        settings = menubar.addMenu("Settings")
        fade_act = QAction("Set Global Fade Duration...", self)
        fade_act.triggered.connect(self.set_fade_duration)
        settings.addAction(fade_act)
        global_dev_act = QAction("Set Global Default Audio Device...", self)
        global_dev_act.triggered.connect(self.set_global_device)
        settings.addAction(global_dev_act)
        defaults_act = QAction("Default Overlay Positions...", self)
        defaults_act.triggered.connect(self.edit_default_positions)
        settings.addAction(defaults_act)

        view_menu = menubar.addMenu("View")
        scale_group = QActionGroup(self)
        scale_group.setExclusive(True)
        self._scale_actions = {}
        for pct, label in ((100, "UI size 100%"), (125, "UI size 125%"), (150, "UI size 150%")):
            act = QAction(label, self)
            act.setCheckable(True)
            act.setData(pct)
            scale_group.addAction(act)
            view_menu.addAction(act)
            self._scale_actions[pct] = act
            act.triggered.connect(lambda checked, p=pct: checked and self.apply_ui_scale(p))

        help_menu = menubar.addMenu("Help")
        keys_act = QAction("Keyboard shortcuts", self)
        keys_act.setShortcut(QKeySequence.StandardKey.HelpContents)
        keys_act.triggered.connect(self.show_keyboard_help)
        help_menu.addAction(keys_act)

    # ------------------------------------------------------------------
    # Core list / selection (hierarchical)
    # ------------------------------------------------------------------
    def cue_status(self, cue):
        if cue.id in self.active_cues:
            return "RUNNING"
        if cue.id == self.current_cue_id:
            return "STANDBY"
        return ""

    def refresh_cue_list(self):
        current_id = self.current_cue_id
        self.cue_list.clear()
        row_h = max(36, int(36 * getattr(self, "ui_scale", 100) / 100))

        top_level = [c for c in self.cues if not c.parent_id]
        top_level.sort(key=lambda c: c.number)

        def add_row(cue, indent=0):
            status = self.cue_status(cue)
            text = format_cue_row_text(cue, indent=indent, status=status)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, cue.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, indent)
            item.setText(text)  # Narrator / UIA; hidden once the widget is attached
            item.setToolTip(text)
            item.setSizeHint(QSize(0, row_h))
            self.cue_list.addItem(item)

            row = CueRowWidget(cue, indent=indent, status=status, row_h=row_h)
            row.delete_clicked.connect(self.delete_cue_by_id)
            self.cue_list.setItemWidget(item, row)

            if cue.id == current_id:
                item.setSelected(True)

            if cue.is_group or cue.cue_type == "Group":
                children = [self.get_cue_by_id(cid) for cid in cue.group_children]
                children = [c for c in children if c]
                children.sort(key=lambda c: c.number)
                for child in children:
                    add_row(child, indent=1)

        for cue in top_level:
            add_row(cue)

    def update_cue_row_status(self):
        """Refresh STANDBY/RUNNING labels without rebuilding the list."""
        for i in range(self.cue_list.count()):
            item = self.cue_list.item(i)
            cue = self.get_cue_by_id(item.data(Qt.ItemDataRole.UserRole))
            if not cue:
                continue
            indent = item.data(Qt.ItemDataRole.UserRole + 1) or 0
            status = self.cue_status(cue)
            text = format_cue_row_text(cue, indent=indent, status=status)
            if item.text() != text:
                item.setText(text)
                item.setToolTip(text)
            row = self.cue_list.itemWidget(item)
            if row is not None:
                row.apply_status(text, status)

    def apply_ui_scale(self, percent, save=True, refresh=True):
        """Scale console type. 100 / 125 / 150. Windows Magnifier still works on top."""
        try:
            percent = int(percent)
        except (TypeError, ValueError):
            percent = 100
        if percent not in (100, 125, 150):
            percent = 100
        self.ui_scale = percent
        app = QApplication.instance()
        font = QFont(app.font())
        font.setPointSizeF(self._base_font_pt * percent / 100.0)
        app.setFont(font)
        if hasattr(self, "transport_bar"):
            self.transport_bar.setFixedHeight(max(72, int(88 * percent / 100)))
        acts = getattr(self, "_scale_actions", {})
        if percent in acts:
            acts[percent].setChecked(True)
        if save:
            QSettings("CueControl", "CueControl").setValue("ui_scale", percent)
        if refresh:
            self.refresh_cue_list()

    def show_keyboard_help(self):
        QMessageBox.information(
            self, "Keyboard shortcuts",
            "Booth\n"
            "  Space              GO (fire the STANDBY cue)\n"
            "  Esc                Fade & Stop\n"
            "  Ctrl+Delete        Delete selected cue\n"
            "  Ctrl+S / O / N     Save / Open / New\n"
            "  F1                 This list\n"
            "\n"
            "Cue list\n"
            "  Click or arrow keys choose STANDBY\n"
            "  Status is written as STANDBY or RUNNING\n"
            "    (not color-only — Narrator reads the same words)\n"
            "\n"
            "View → UI size → 100% / 125% / 150%\n"
            "Windows Magnifier, Narrator, and Sticky Keys still work.\n"
        )

    def apply_cue_number(self):
        cue = self.get_current_cue()
        if not cue:
            return
        new_number = self.number_spin.value()
        for other in self.cues:
            if other.id != cue.id and abs(other.number - new_number) < 0.001:
                self.statusBar.showMessage(f"Number {new_number} is already used")
                self.number_spin.setValue(cue.number)
                return
        cue.number = new_number
        self.refresh_cue_list()
        self.statusBar.showMessage(f"Cue number set to {new_number}")

    def delete_cue_by_id(self, cue_id: str):
        cue = self.get_cue_by_id(cue_id)
        if not cue:
            return
        reply = QMessageBox.question(
            self, "Delete Cue",
            f"Are you sure you want to delete cue {cue.number} – “{cue.name}”?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if cue.id in self.active_cues:
            self.stop_single_cue(cue.id)

        # Clean parent/child links
        if cue.parent_id:
            parent = self.get_cue_by_id(cue.parent_id)
            if parent and cue.id in parent.group_children:
                parent.group_children.remove(cue.id)

        if cue.is_group or cue.cue_type == "Group":
            for cid in list(cue.group_children):
                child = self.get_cue_by_id(cid)
                if child:
                    child.parent_id = None
            cue.group_children.clear()

        self.cues = [c for c in self.cues if c.id != cue_id]
        self.destroy_window(cue)

        self.repair_cue_links()

        if self.current_cue_id == cue_id:
            self.current_cue_id = None

        self.refresh_cue_list()

        if self.cues:
            first = sorted(self.cues, key=lambda c: c.number)[0]
            self.select_cue_by_id(first.id)
        else:
            self.type_label.setText("-")
            for g in (self.overlay_group, self.volume_group, self.text_group,
                      self.image_group, self.video_group, self.pdf_group,
                      self.link_group, self.osc_group, self.wave_group,
                      self.group_settings_group):
                g.hide()

        self.statusBar.showMessage(f"Deleted cue {cue.number}")

    def delete_selected_cue(self):
        if self.current_cue_id:
            self.delete_cue_by_id(self.current_cue_id)

    def on_cue_selected(self, item):
        if item is None:
            return
        cue_id = item.data(Qt.ItemDataRole.UserRole)
        cue = self.get_cue_by_id(cue_id)
        if not cue:
            return
        prev_id = self.current_cue_id
        self.current_cue_id = cue.id
        # Test / Edit previews of the previous cue leak if we uncheck
        # the box with blockSignals. Destroy idle windows only.
        if prev_id and prev_id != cue.id and prev_id not in self.active_cues:
            prev = self.get_cue_by_id(prev_id)
            if prev is not None:
                self.destroy_window(prev)

        self.number_spin.blockSignals(True)
        self.number_spin.setValue(cue.number)
        self.number_spin.blockSignals(False)

        self.name_edit.setText(cue.name)
        self.type_label.setText(cue.cue_type)
        self.follow_combo.setCurrentText(cue.follow_mode)
        self.duration_spin.setValue(int(cue.duration_ms / 1000))
        self.populate_device_combo(cue)

        is_text  = cue.cue_type == "Text"
        is_image = cue.cue_type == "Image"
        is_video = cue.cue_type == "Video"
        is_pdf   = cue.cue_type == "PDF"
        is_link  = cue.cue_type == "Link"
        is_audio = cue.cue_type == "Audio"
        is_osc   = cue.cue_type == "OSC"

        is_overlay = is_text or is_image or is_video or is_pdf or (is_link and not cue.link_use_system_browser)

        self.volume_group.setVisible(is_audio or is_video)
        self.overlay_group.setVisible(is_overlay)
        self.text_group.setVisible(is_text)
        self.image_group.setVisible(is_image)
        self.video_group.setVisible(is_video)
        self.pdf_group.setVisible(is_pdf)
        self.link_group.setVisible(is_link)
        self.osc_group.setVisible(is_osc)
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
            self.timeline_offset_spin.setEnabled(True)
        self.file_label.setVisible(True)

        self.test_cb.blockSignals(True)
        self.test_cb.setChecked(False)
        self.test_cb.blockSignals(False)

        if is_overlay and self.edit_mode_cb.isChecked():
            self.on_edit_mode_toggled(True)

        if is_audio or is_video:
            vol_pct = int(round(cue.volume * 100))
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(vol_pct)
            self.volume_slider.blockSignals(False)
            self.volume_spin.blockSignals(True)
            self.volume_spin.setValue(vol_pct)
            self.volume_spin.blockSignals(False)

        if is_overlay:
            self.populate_screen_combo(cue)
            self.layer_spin.blockSignals(True)
            self.layer_spin.setValue(cue.layer)
            self.layer_spin.blockSignals(False)
            self.opacity_spin.blockSignals(True)
            self.opacity_spin.setValue(int(cue.opacity * 100))
            self.opacity_spin.blockSignals(False)

            self.size_mode_combo.blockSignals(True)
            if cue.size_mode == "percent":
                self.size_mode_combo.setCurrentIndex(0)
                self.percent_widget.show()
                self.pixel_widget.hide()
            else:
                self.size_mode_combo.setCurrentIndex(1)
                self.percent_widget.hide()
                self.pixel_widget.show()
            self.size_mode_combo.blockSignals(False)

            self.width_percent_spin.blockSignals(True)
            self.width_percent_spin.setValue(cue.width_percent)
            self.width_percent_spin.blockSignals(False)
            self.height_percent_spin.blockSignals(True)
            self.height_percent_spin.setValue(cue.height_percent)
            self.height_percent_spin.blockSignals(False)
            self.width_px_spin.blockSignals(True)
            self.width_px_spin.setValue(cue.width_px)
            self.width_px_spin.blockSignals(False)
            self.height_px_spin.blockSignals(True)
            self.height_px_spin.setValue(cue.height_px)
            self.height_px_spin.blockSignals(False)

        if is_text:
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(cue.text)
            self.text_edit.blockSignals(False)
            self.font_size_spin.blockSignals(True)
            self.font_size_spin.setValue(cue.font_size)
            self.font_size_spin.blockSignals(False)
            self.color_btn.setStyleSheet(f"background-color:{cue.text_color}; border:1px solid #888;")
            self.file_label.setText("-")

        if is_image:
            self.image_path_edit.setText(cue.image_path or "")
            self.scale_mode_combo.blockSignals(True)
            self.scale_mode_combo.setCurrentText(cue.scale_mode)
            self.scale_mode_combo.blockSignals(False)
            self.image_persistent_cb.blockSignals(True)
            self.image_persistent_cb.setChecked(cue.image_persistent)
            self.image_persistent_cb.blockSignals(False)
            self.file_label.setText(cue.image_path or "-")

        if is_video:
            self.video_path_edit.setText(cue.video_path or "")
            self.video_loop_cb.blockSignals(True)
            self.video_loop_cb.setChecked(cue.video_loop)
            self.video_loop_cb.blockSignals(False)
            self.video_mute_cb.blockSignals(True)
            self.video_mute_cb.setChecked(cue.video_muted)
            self.video_mute_cb.blockSignals(False)
            self.file_label.setText(cue.video_path or "-")

        if is_pdf:
            self.pdf_path_edit.setText(cue.pdf_path or "")
            self.pdf_page_spin.blockSignals(True)
            self.pdf_page_spin.setValue(cue.pdf_page + 1)
            self.pdf_page_spin.blockSignals(False)
            self.pdf_zoom_combo.blockSignals(True)
            self.pdf_zoom_combo.setCurrentText(cue.pdf_zoom_mode)
            self.pdf_zoom_combo.blockSignals(False)
            if hasattr(self, "pdf_multipage_cb"):
                self.pdf_multipage_cb.blockSignals(True)
                self.pdf_multipage_cb.setChecked(getattr(cue, "pdf_multipage", False))
                self.pdf_multipage_cb.blockSignals(False)
            self.file_label.setText(cue.pdf_path or "-")

        if is_link:
            self.link_url_edit.setText(cue.link_url or "")
            self.link_system_cb.blockSignals(True)
            self.link_system_cb.setChecked(cue.link_use_system_browser)
            self.link_system_cb.blockSignals(False)
            self.file_label.setText(cue.link_url or "-")

        if is_osc:
            self.osc_preset_combo.blockSignals(True)
            self.osc_preset_combo.setCurrentText(cue.osc_preset)
            self.osc_preset_combo.blockSignals(False)
            self.on_osc_preset_changed(cue.osc_preset)
            self.osc_ip_edit.setText(cue.osc_ip)
            self.osc_port_spin.setValue(cue.osc_port)
            self.osc_address_edit.setText(cue.osc_address)
            self.osc_args_edit.setText(cue.osc_args)
            self.file_label.setText(f"{cue.osc_ip}:{cue.osc_port}  {cue.osc_address}")

        if is_audio and cue.media_path:
            self.file_label.setText(cue.media_path)
            self.waveform.set_file(cue.media_path)
        elif not is_overlay and not is_link and not is_osc:
            self.file_label.setText("-")
            self.waveform.set_file("")

    # ------------------------------------------------------------------
    # OSC specific
    # ------------------------------------------------------------------
    def on_osc_preset_changed(self, preset_name):
        self.osc_common_combo.blockSignals(True)
        self.osc_common_combo.clear()
        self.osc_common_combo.addItem("(manual)", None)

        preset = OSC_PRESETS.get(preset_name, {})
        for cmd in preset.get("common", []):
            self.osc_common_combo.addItem(cmd["name"], cmd)

        port = preset.get("default_port", 8000)
        self.osc_port_spin.blockSignals(True)
        self.osc_port_spin.setValue(port)
        self.osc_port_spin.blockSignals(False)

        self.osc_common_combo.blockSignals(False)
        self.apply_osc_settings()

    def on_osc_common_changed(self, index):
        data = self.osc_common_combo.itemData(index)
        if data:
            self.osc_address_edit.setText(data["address"])
            if data.get("arg_hint"):
                self.osc_args_edit.setPlaceholderText(data["arg_hint"])
            else:
                self.osc_args_edit.setPlaceholderText("leave empty if no arguments")
        self.apply_osc_settings()

    def apply_osc_settings(self):
        cue = self.get_current_cue()
        if not cue or cue.cue_type != "OSC":
            return
        cue.osc_preset = self.osc_preset_combo.currentText()
        cue.osc_ip = self.osc_ip_edit.text().strip() or "127.0.0.1"
        cue.osc_port = self.osc_port_spin.value()
        cue.osc_address = self.osc_address_edit.text().strip()
        cue.osc_args = self.osc_args_edit.text().strip()
        self.refresh_cue_list()
        self.file_label.setText(f"{cue.osc_ip}:{cue.osc_port}  {cue.osc_address}")

    def send_osc(self, cue):
        if not HAS_OSC:
            self.statusBar.showMessage("python-osc not installed – cannot send OSC")
            return False

        if not cue.osc_address:
            self.statusBar.showMessage("OSC Address is empty")
            return False

        try:
            client = udp_client.SimpleUDPClient(cue.osc_ip, cue.osc_port)

            args = []
            if cue.osc_args.strip():
                for part in cue.osc_args.split(","):
                    part = part.strip()
                    if not part:
                        continue
                    try:
                        if "." in part:
                            args.append(float(part))
                        else:
                            args.append(int(part))
                    except ValueError:
                        args.append(part)

            if args:
                client.send_message(cue.osc_address, args)
            else:
                client.send_message(cue.osc_address, [])

            return True
        except Exception as e:
            self.statusBar.showMessage(f"OSC send failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Property apply methods
    # ------------------------------------------------------------------
    def apply_name_change(self):
        cue = self.get_current_cue()
        if cue:
            cue.name = self.name_edit.text()
            self.refresh_cue_list()

    def apply_follow_mode(self, text):
        cue = self.get_current_cue()
        if cue:
            cue.follow_mode = text
            self.refresh_cue_list()

    def apply_duration(self, value):
        cue = self.get_current_cue()
        if cue:
            cue.duration_ms = value * 1000

    def apply_device(self, index):
        cue = self.get_current_cue()
        if cue:
            cue.audio_device_id = self.device_combo.itemData(index)

    def on_volume_spin_changed(self, value):
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(value)
        self.volume_slider.blockSignals(False)
        self.apply_volume(value)

    def apply_volume(self, value):
        cue = self.get_current_cue()
        if not cue or cue.cue_type not in ("Audio", "Video"):
            return
        cue.volume = max(0.0, min(1.0, value / 100.0))
        if cue.id in self.active_cues:
            info = self.active_cues[cue.id]
            if cue.cue_type == "Audio" and info.get("output"):
                info["output"].setVolume(cue.volume)
            elif cue.cue_type == "Video":
                win = self.video_windows.get(cue.id)
                if win and hasattr(win, "audio_output"):
                    win.audio_output.setVolume(0.0 if cue.video_muted else cue.volume)
        self.refresh_cue_list()

    def apply_text_content(self):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "Text":
            cue.text = self.text_edit.toPlainText()
            self.debounced("text_window_refresh", self._refresh_text_window)

    def apply_font_size(self, value):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "Text":
            cue.font_size = value
            self.debounced("text_window_refresh", self._refresh_text_window)

    def _refresh_text_window(self):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "Text":
            win = self.text_windows.get(cue.id)
            if win and win.current_cue is cue:
                win.show_text(cue, self.get_screen_by_name(cue.screen_name),
                             self.display_defaults, steal_focus=False)

    def pick_text_color(self):
        cue = self.get_current_cue()
        if not cue or cue.cue_type != "Text":
            return
        color = QColorDialog.getColor(QColor(cue.text_color), self, "Text Color")
        if color.isValid():
            cue.text_color = color.name()
            self.color_btn.setStyleSheet(f"background-color:{cue.text_color}; border:1px solid #888;")
            self._refresh_text_window()

    def apply_screen(self, index):
        cue = self.get_current_cue()
        if cue and cue.cue_type in ("Text", "Image", "Video", "PDF", "Link"):
            cue.screen_name = self.screen_combo.itemData(index)

    def apply_layer(self, value):
        cue = self.get_current_cue()
        if cue and cue.cue_type in ("Text", "Image", "Video", "PDF", "Link"):
            cue.layer = value
            win = (self.text_windows.get(cue.id) or self.image_windows.get(cue.id) or
                   self.video_windows.get(cue.id) or self.pdf_windows.get(cue.id) or
                   self.web_windows.get(cue.id))
            if win:
                win.set_layer(value)

    def apply_opacity(self, value):
        cue = self.get_current_cue()
        if cue and cue.cue_type in ("Text", "Image", "Video", "PDF", "Link"):
            cue.opacity = value / 100.0
            self.debounced("opacity_window_refresh", self._refresh_opacity_window)

    def _refresh_opacity_window(self):
        cue = self.get_current_cue()
        if cue and cue.cue_type in ("Text", "Image", "Video", "PDF", "Link"):
            win = (self.text_windows.get(cue.id) or self.image_windows.get(cue.id) or
                   self.video_windows.get(cue.id) or self.pdf_windows.get(cue.id) or
                   self.web_windows.get(cue.id))
            if win:
                win.set_opacity(cue.opacity)

    def on_size_mode_changed(self, index):
        is_percent = (index == 0)
        self.percent_widget.setVisible(is_percent)
        self.pixel_widget.setVisible(not is_percent)
        self.apply_size_settings()

    def apply_size_settings(self):
        cue = self.get_current_cue()
        if not cue or cue.cue_type not in ("Text", "Image", "Video", "PDF", "Link"):
            return
        if self.size_mode_combo.currentIndex() == 0:
            cue.size_mode = "percent"
            cue.width_percent = self.width_percent_spin.value()
            cue.height_percent = self.height_percent_spin.value()
        else:
            cue.size_mode = "pixels"
            cue.width_px = self.width_px_spin.value()
            cue.height_px = self.height_px_spin.value()
        self.debounced("size_window_refresh", self._refresh_size_window)

    def _refresh_size_window(self):
        cue = self.get_current_cue()
        if not cue or cue.cue_type not in ("Text", "Image", "Video", "PDF", "Link"):
            return
        win = (self.text_windows.get(cue.id) or self.image_windows.get(cue.id) or
               self.video_windows.get(cue.id) or self.pdf_windows.get(cue.id) or
               self.web_windows.get(cue.id))
        if win and win.current_cue is cue:
            screen = self.get_screen_by_name(cue.screen_name)
            win.apply_geometry(cue, screen, self.display_defaults)

    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff)"
        )
        cue = self.get_current_cue()
        if path and cue and cue.cue_type == "Image":
            cue.image_path = path
            cue.name = os.path.splitext(os.path.basename(path))[0]
            self.image_path_edit.setText(path)
            self.name_edit.setText(cue.name)
            self.refresh_cue_list()
            win = self.image_windows.get(cue.id)
            if win and win.current_cue is cue:
                win.show_image(cue, self.get_screen_by_name(cue.screen_name), self.display_defaults)

    def apply_scale_mode(self, mode: str):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "Image":
            cue.scale_mode = mode
            win = self.image_windows.get(cue.id)
            if win and win.current_cue is cue:
                win._apply_scaling(mode)

    def apply_image_persistent(self, checked):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "Image":
            cue.image_persistent = checked
            self.refresh_cue_list()

    def browse_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "",
            "Video (*.mp4 *.mov *.mkv *.avi *.webm *.m4v)"
        )
        cue = self.get_current_cue()
        if path and cue and cue.cue_type == "Video":
            cue.video_path = path
            cue.name = os.path.splitext(os.path.basename(path))[0]
            self.video_path_edit.setText(path)
            self.name_edit.setText(cue.name)
            self.file_label.setText(path)
            self.refresh_cue_list()

    def apply_video_loop(self, checked):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "Video":
            cue.video_loop = checked

    def apply_video_mute(self, checked):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "Video":
            cue.video_muted = checked
            if cue.id in self.active_cues:
                win = self.video_windows.get(cue.id)
                if win and hasattr(win, "audio_output"):
                    win.audio_output.setMuted(checked)
                    win.audio_output.setVolume(0.0 if checked else cue.volume)

    def browse_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        cue = self.get_current_cue()
        if path and cue and cue.cue_type == "PDF":
            cue.pdf_path = path
            cue.name = os.path.splitext(os.path.basename(path))[0]
            self.pdf_path_edit.setText(path)
            self.name_edit.setText(cue.name)
            self.file_label.setText(path)
            self.refresh_cue_list()

    def apply_pdf_page(self, value):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "PDF":
            cue.pdf_page = max(0, value - 1)

    def apply_pdf_zoom(self, mode):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "PDF":
            cue.pdf_zoom_mode = mode

    def apply_pdf_multipage(self, checked: bool):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "PDF":
            cue.pdf_multipage = checked
            win = self.pdf_windows.get(cue.id)
            if win and win.current_cue is cue:
                win.show_pdf(cue, self.get_screen_by_name(cue.screen_name),
                             self.display_defaults, steal_focus=False)

    def pdf_prev_page(self):
        cue = self.get_current_cue()
        if not cue or cue.cue_type != "PDF":
            return
        cue.pdf_page = max(0, cue.pdf_page - 1)
        self.pdf_page_spin.blockSignals(True)
        self.pdf_page_spin.setValue(cue.pdf_page + 1)
        self.pdf_page_spin.blockSignals(False)
        win = self.pdf_windows.get(cue.id)
        if win:
            win.goto_page(cue.pdf_page)

    def pdf_next_page(self):
        cue = self.get_current_cue()
        if not cue or cue.cue_type != "PDF":
            return
        nxt = cue.pdf_page + 1
        win = self.pdf_windows.get(cue.id)
        if win and getattr(win, "doc", None) is not None:
            count = win.doc.pageCount()
            if count > 0:
                nxt = min(nxt, count - 1)
        cue.pdf_page = max(0, nxt)
        self.pdf_page_spin.blockSignals(True)
        self.pdf_page_spin.setValue(cue.pdf_page + 1)
        self.pdf_page_spin.blockSignals(False)
        if win:
            win.goto_page(cue.pdf_page)

    def apply_link_url(self):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "Link":
            cue.link_url = self.link_url_edit.text().strip()
            self.file_label.setText(cue.link_url or "-")

    def apply_link_system(self, checked):
        cue = self.get_current_cue()
        if cue and cue.cue_type == "Link":
            cue.link_use_system_browser = checked
            self.refresh_cue_list()
            self.overlay_group.setVisible(not checked)

    # ------------------------------------------------------------------
    # Edit / Test Mode
    # ------------------------------------------------------------------
    def on_test_toggled(self, checked: bool):
        cue = self.get_current_cue()
        if not cue:
            return
        if cue.cue_type == "Link" and cue.link_use_system_browser:
            return
        if cue.cue_type not in ("Text", "Image", "Video", "PDF", "Link"):
            return

        screen = self.get_screen_by_name(cue.screen_name)
        if checked:
            win = self.get_or_create_window(cue)
            if cue.cue_type == "Text":
                win.show_text(cue, screen, self.display_defaults)
            elif cue.cue_type == "Image":
                win.show_image(cue, screen, self.display_defaults)
            elif cue.cue_type == "Video":
                device = self.get_device_by_id(cue.audio_device_id)
                win.show_video(cue, screen, self.display_defaults, device)
            elif cue.cue_type == "PDF":
                win.show_pdf(cue, screen, self.display_defaults)
            elif cue.cue_type == "Link":
                win.show_url(cue, screen, self.display_defaults)
            self.statusBar.showMessage("Test / Preview ON")
        else:
            if cue.id not in self.active_cues and not self.edit_mode_cb.isChecked():
                self.destroy_window(cue)
            self.statusBar.showMessage("Test / Preview OFF")

    def on_edit_mode_toggled(self, checked: bool):
        cue = self.get_current_cue()
        if not cue or cue.cue_type not in ("Text", "Image", "Video", "PDF", "Link"):
            return
        if cue.cue_type == "Link" and cue.link_use_system_browser:
            return

        screen = self.get_screen_by_name(cue.screen_name)
        win = self.get_or_create_window(cue)

        if checked:
            if cue.cue_type == "Text":
                win.show_text(cue, screen, self.display_defaults)
            elif cue.cue_type == "Image":
                win.show_image(cue, screen, self.display_defaults)
            elif cue.cue_type == "Video":
                device = self.get_device_by_id(cue.audio_device_id)
                win.show_video(cue, screen, self.display_defaults, device)
            elif cue.cue_type == "PDF":
                win.show_pdf(cue, screen, self.display_defaults)
            elif cue.cue_type == "Link":
                win.show_url(cue, screen, self.display_defaults)
            win.set_edit_mode(True)
            win.raise_()
            win.activateWindow()
            self.statusBar.showMessage("Edit Mode ON – resize/move, then uncheck to lock")
        else:
            self.save_window_size_to_cue(cue, win)
            win.set_edit_mode(False)
            if cue.id not in self.active_cues and not self.test_cb.isChecked():
                self.destroy_window(cue)
            self.statusBar.showMessage("Edit Mode OFF – size & position locked")

    def align_center(self):
        cue = self.get_current_cue()
        if not cue or cue.cue_type not in ("Text", "Image", "Video", "PDF", "Link"):
            return
        win = self.get_or_create_window(cue)
        screen = self.get_screen_by_name(cue.screen_name)
        win.center_on_screen(screen)

    def align_snap(self, edge: str):
        cue = self.get_current_cue()
        if not cue or cue.cue_type not in ("Text", "Image", "Video", "PDF", "Link"):
            return
        win = self.get_or_create_window(cue)
        screen = self.get_screen_by_name(cue.screen_name)
        win.snap(edge, screen)

       # ------------------------------------------------------------------
       # ------------------------------------------------------------------
    # Playback + Crossfade + Group + Wait
    # ------------------------------------------------------------------
    def start_cue(self, cue):
        if cue is None:
            return False

        # Retrigger: stop this cue if it is already running, then start again.
        if cue.id in self.active_cues:
            self.stop_single_cue(cue.id)

        IMPLEMENTED = (
            "Audio", "Video", "Image", "Text", "PDF", "Link", "OSC",
            "Automation", "Wait", "Group"
        )
        if cue.cue_type not in IMPLEMENTED:
            self.statusBar.showMessage(f"{cue.cue_type} cues aren't implemented yet")
            return False

        # One bed at a time: a new Audio/Video cuts the previous same type.
        if cue.cue_type in ("Audio", "Video"):
            for cid, other in list(self.active_cues.items()):
                if other["cue"].cue_type == cue.cue_type and cid != cue.id:
                    self.stop_single_cue(cid)

        info = {"cue": cue, "start": time.time(), "player": None, "output": None}
        started = False

        if cue.cue_type == "Audio":
            if not cue.media_path or not os.path.exists(cue.media_path):
                self.statusBar.showMessage(
                    f"Audio file missing: {cue.media_path or '(none)'}"
                )
                return False
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
            win.show_text(cue, screen, self.display_defaults, steal_focus=False)
            started = True

        elif cue.cue_type == "Image":
            if not cue.image_path or not os.path.exists(cue.image_path):
                self.statusBar.showMessage(
                    f"Image file missing: {cue.image_path or '(none)'}"
                )
                return False
            if cue.image_persistent:
                for other_id, other_info in list(self.active_cues.items()):
                    other_cue = other_info["cue"]
                    if (
                        other_cue.cue_type == "Image"
                        and other_cue.image_persistent
                        and other_id != cue.id
                    ):
                        self.stop_single_cue(other_id)
            screen = self.get_screen_by_name(cue.screen_name)
            win = self.get_or_create_window(cue)
            win.show_image(cue, screen, self.display_defaults, steal_focus=False)
            started = True

        elif cue.cue_type == "Video":
            if not cue.video_path or not os.path.exists(cue.video_path):
                self.statusBar.showMessage(
                    f"Video file missing: {cue.video_path or '(none)'}"
                )
                return False
            screen = self.get_screen_by_name(cue.screen_name)
            win = self.get_or_create_window(cue)
            device = self.get_device_by_id(cue.audio_device_id)
            win.show_video(cue, screen, self.display_defaults, device, steal_focus=False)
            started = True

        elif cue.cue_type == "PDF":
            if not cue.pdf_path or not os.path.exists(cue.pdf_path):
                self.statusBar.showMessage(
                    f"PDF file missing: {cue.pdf_path or '(none)'}"
                )
                return False
            screen = self.get_screen_by_name(cue.screen_name)
            win = self.get_or_create_window(cue)
            win.show_pdf(cue, screen, self.display_defaults, steal_focus=False)
            started = True

        elif cue.cue_type == "Link":
            url = (cue.link_url or "").strip()
            if not url:
                self.statusBar.showMessage("No URL set for Link cue")
                return False
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            if cue.link_use_system_browser or not HAS_WEBENGINE:
                webbrowser.open(url)
                self.statusBar.showMessage(f"Opened in system browser: {url}")
                started = True
            else:
                screen = self.get_screen_by_name(cue.screen_name)
                win = self.get_or_create_window(cue)
                win.show_url(cue, screen, self.display_defaults, steal_focus=False)
                started = True

        elif cue.cue_type == "OSC":
            if not self.send_osc(cue):
                return False
            started = True

        elif cue.cue_type == "Wait":
            if cue.duration_ms <= 0:
                cue.duration_ms = 100
                self.statusBar.showMessage("Wait duration was 0 – using 0.1 s")
            started = True

        elif cue.cue_type == "Group":
            return bool(self.start_group_cue(cue))

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
            return False

        self.active_cues[cue.id] = info
        self.update_running_list()
        self.statusBar.showMessage(f"Started {cue.number} – {cue.name}")
        self._maybe_auto_fire(cue)
        return True

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

    def start_group_cue(self, cue):
        """Organizational = first child only. Timeline = fire by timeline_offset_ms.

        Guards against a self-referencing or mutually-referencing group
        (e.g. a hand-edited .ccs where a group lists itself, or lists
        another group, as a child). The UI blocks nesting groups when
        dragging, but a loaded file could still contain a cycle -- without
        this check, firing it recurses into start_cue -> start_group_cue
        forever and crashes with a RecursionError. Auto-Fire already has
        an equivalent loop guard; groups didn't.
        """
        stack = getattr(self, "_group_start_stack", None)
        if stack is None:
            stack = self._group_start_stack = set()
        if cue.id in stack:
            self.statusBar.showMessage(
                f"Group loop detected in \"{cue.name}\" – refusing to start it again"
            )
            return False
        stack.add(cue.id)
        try:
            self._start_group_cue_inner(cue)
        finally:
            stack.discard(cue.id)
        return True

    def _start_group_cue_inner(self, cue):
        """Fire children: organizational = first child; timeline = offset clock."""
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

    def cue_list_mouse_press(self, event):
        """Capture which cue is being dragged before selection can change."""
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        item = self.cue_list.itemAt(pos)
        if item is not None:
            self._drag_source_id = item.data(Qt.ItemDataRole.UserRole)
        QListWidget.mousePressEvent(self.cue_list, event)

    def _maybe_auto_fire(self, cue):
        """Fire the next Auto-Fire cue, iteratively.

        Nested start_cue -> _maybe_auto_fire calls are ignored while a chain
        is walking so we cannot recurse / overflow. Stops on loopback
        (same cue id seen twice) or after AUTO_FIRE_MAX hops.
        """
        if cue is None or getattr(cue, "follow_mode", "") != "Auto-Fire":
            return
        if getattr(self, "_auto_fire_busy", False):
            return
        self._auto_fire_busy = True
        try:
            seen = {cue.id}
            current = cue
            hops = 0
            while hops < self.AUTO_FIRE_MAX:
                nxt = self._next_cue_after(current)
                if nxt is None:
                    break
                if nxt.id in seen:
                    self.statusBar.showMessage(
                        "Auto-Fire loop detected – chain stopped"
                    )
                    break
                seen.add(nxt.id)
                hops += 1
                self.select_cue_by_id(nxt.id)
                self.start_cue(nxt)
                if nxt.follow_mode != "Auto-Fire":
                    break
                current = nxt
            else:
                self.statusBar.showMessage(
                    f"Auto-Fire capped at {self.AUTO_FIRE_MAX} cues"
                )
        finally:
            self._auto_fire_busy = False

    def _next_cue_after(self, cue):
        ordered = sorted(self.cues, key=lambda c: c.number)
        try:
            idx = ordered.index(cue)
        except ValueError:
            return None
        if idx + 1 < len(ordered):
            return ordered[idx + 1]
        return None
    def do_crossfade(self):
        duration = self.fade_duration_ms
        steps = max(8, duration // 50)
        interval = max(10, duration // steps)

        targets = []

        for cid, info in list(self.active_cues.items()):
            c = info["cue"]
            if c.cue_type == "Audio" and info.get("output"):
                try:
                    targets.append((info["output"], info["output"].volume()))
                except RuntimeError:
                    pass
            elif c.cue_type == "Video":
                win = self.video_windows.get(cid)
                if win and hasattr(win, "audio_output"):
                    try:
                        targets.append((win.audio_output, win.audio_output.volume()))
                    except RuntimeError:
                        pass
        if not targets:
            self.statusBar.showMessage("Nothing to crossfade")
            return

        fading_ids = [cid for cid, info in self.active_cues.items()
                      if info["cue"].cue_type in ("Audio", "Video")]

        step = 0

        def tick():
            nonlocal step
            step += 1
            factor = max(0.0, 1.0 - (step / steps))
            for out, start_v in targets:
                try:
                    out.setVolume(start_v * factor)
                except RuntimeError:
                    pass

            if step >= steps:
                for cid in fading_ids:
                    if cid in self.active_cues:
                        self.stop_single_cue(cid)
                self.statusBar.showMessage("Crossfade complete")
                return

            QTimer.singleShot(interval, tick)

        self.statusBar.showMessage(f"Crossfading over {duration // 1000}s…")
        QTimer.singleShot(interval, tick)

    def stop_single_cue(self, cue_id):
        if cue_id not in self.active_cues:
            return
        info = self.active_cues[cue_id]
        player = info.get("player")
        if player:
            player.stop()
        cue = info["cue"]
        self.destroy_window(cue)
        del self.active_cues[cue_id]
        self.update_running_list()

    def go_pressed(self):
        # 180 ms debounce – protects against rapid Space / mouse clicks
        now = time.time()
        last = getattr(self, "_last_go_time", 0.0)
        if now - last < 0.18:
            return
        self._last_go_time = now

        if not self.current_cue_id and self.cues:
            first = sorted(self.cues, key=lambda c: c.number)[0]
            self.select_cue_by_id(first.id)

        cue = self.get_current_cue()
        if not cue:
            return

        started = self.start_cue(cue)
        if not started:
            return

        if cue.follow_mode == "Auto-Ready":
            # Organizational group: start_group_cue already armed the first child.
            is_org_group = (
                (cue.cue_type == "Group" or getattr(cue, "is_group", False))
                and getattr(cue, "group_mode", "organizational") != "timeline"
            )
            if is_org_group:
                return
            sorted_cues = sorted(self.cues, key=lambda c: c.number)
            try:
                idx = sorted_cues.index(cue)
                if idx + 1 < len(sorted_cues):
                    self.select_cue_by_id(sorted_cues[idx + 1].id)
            except ValueError:
                pass

    def stop_all(self):
        self.clear_timelines()
        for cid in list(self.active_cues.keys()):
            self.stop_single_cue(cid)

        for d in (self.text_windows, self.image_windows, self.video_windows,
                  self.pdf_windows, self.web_windows):
            for win in list(d.values()):
                win.close_window()
            d.clear()

        self.blackout_window.hide_blackout()
        self.blackout_btn.setChecked(False)
        self.edit_mode_cb.setChecked(False)
        self.test_cb.setChecked(False)
        # Intentionally keep current_cue_id so the stand-by cue remains selected
        self.refresh_cue_list()
        self.update_running_list()
        self._fade_pending = False
        try:
            self.activateWindow()
        except RuntimeError:
            pass
        self.statusBar.showMessage("All stopped – stand-by preserved")

    def fade_and_stop(self):
        if getattr(self, "_fade_pending", False):
            return
        self._fade_pending = True
        self.statusBar.showMessage(f"Fading {self.fade_duration_ms//1000}s...")

        def _finish_fade():
            self._fade_pending = False
            self.stop_all()

        QTimer.singleShot(self.fade_duration_ms, _finish_fade)

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
                t = (
                    f"{int(remaining // 60000):02d}:"
                    f"{int((remaining % 60000) // 1000):02d}"
                )
            else:
                t = "∞"
            self.running_list.addItem(f"RUNNING  {cue.number} - {cue.name}   [{t}]")

        for cid in finished:
            cue = self.active_cues[cid]["cue"] if cid in self.active_cues else None
            self.stop_single_cue(cid)
            # Auto-Follow: when a timed cue finishes, start the next one
            if cue is not None and cue.follow_mode == "Auto-Follow":
                nxt = self._next_cue_after(cue)
                if nxt is not None:
                    self.select_cue_by_id(nxt.id)
                    self.start_cue(nxt)

        self.tick_timelines()
        self.update_cue_row_status()

    def _add_and_select(self, cue):
        self.cues.append(cue)
        self.select_cue_by_id(cue.id)
        self.statusBar.showMessage(f"Added {cue.cue_type}: {cue.name}")

    def add_audio_cue(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio", "", "Audio (*.mp3 *.wav *.ogg *.flac *.m4a)"
        )
        if path:
            self.create_audio_cue_from_path(path)

    def create_audio_cue_from_path(self, path):
        name = os.path.splitext(os.path.basename(path))[0]
        next_num = max((c.number for c in self.cues), default=0) + 1
        cue = Cue(next_num, name, "Audio", "Auto-Ready")
        cue.media_path = path
        cue.duration_ms = self.get_audio_duration_ms(path)
        self._add_and_select(cue)

    def get_audio_duration_ms(self, path):
        try:
            info = sf.info(path)
            return int(info.frames / info.samplerate * 1000)
        except Exception:
            return 0

    def add_video_cue(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "", "Video (*.mp4 *.mov *.mkv *.avi *.webm *.m4v)"
        )
        if path:
            name = os.path.splitext(os.path.basename(path))[0]
            next_num = max((c.number for c in self.cues), default=0) + 1
            cue = Cue(next_num, name, "Video", "Auto-Ready")
            cue.video_path = path
            primary = QGuiApplication.primaryScreen()
            if primary:
                cue.screen_name = primary.name()
            self._add_and_select(cue)

    def add_image_cue(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff)"
        )
        if path:
            self.create_image_cue_from_path(path)

    def create_image_cue_from_path(self, path):
        name = os.path.splitext(os.path.basename(path))[0]
        next_num = max((c.number for c in self.cues), default=0) + 1
        cue = Cue(next_num, name, "Image", "Auto-Ready")
        cue.image_path = path
        cue.duration_ms = 5000
        primary = QGuiApplication.primaryScreen()
        if primary:
            cue.screen_name = primary.name()
        self._add_and_select(cue)

    def add_pdf_cue(self):
        if not HAS_PDF:
            QMessageBox.warning(
                self, "PDF Support",
                "QtPdf is not available in this PySide6 installation.\nPDF cues cannot be displayed."
            )
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if path:
            name = os.path.splitext(os.path.basename(path))[0]
            next_num = max((c.number for c in self.cues), default=0) + 1
            cue = Cue(next_num, name, "PDF", "Auto-Ready")
            cue.pdf_path = path
            primary = QGuiApplication.primaryScreen()
            if primary:
                cue.screen_name = primary.name()
            self._add_and_select(cue)

    def add_link_cue(self):
        next_num = max((c.number for c in self.cues), default=0) + 1
        cue = Cue(next_num, "New Link", "Link", "Auto-Ready")
        cue.link_url = "https://"
        cue.link_use_system_browser = False
        primary = QGuiApplication.primaryScreen()
        if primary:
            cue.screen_name = primary.name()
        self._add_and_select(cue)

    def add_text_cue(self):
        next_num = max((c.number for c in self.cues), default=0) + 1
        cue = Cue(next_num, "New Supertitle", "Text", "Auto-Ready")
        cue.text = "Hello from the booth"
        cue.duration_ms = 5000
        primary = QGuiApplication.primaryScreen()
        if primary:
            cue.screen_name = primary.name()
        self._add_and_select(cue)

    def add_osc_cue(self):
        next_num = max((c.number for c in self.cues), default=0) + 1
        cue = Cue(next_num, "New OSC", "OSC", "Auto-Ready")
        cue.osc_preset = "ETC EOS"
        cue.osc_ip = "127.0.0.1"
        cue.osc_port = 8000
        cue.osc_address = "/eos/key/go"
        self._add_and_select(cue)

    def add_stop_fade_cue(self):
        next_num = max((c.number for c in self.cues), default=0) + 1
        cue = Cue(next_num, "Stop & Fade", "Automation")
        self._add_and_select(cue)

    def add_stop_cue(self):
        next_num = max((c.number for c in self.cues), default=0) + 1
        cue = Cue(next_num, "Stop", "Automation")
        self._add_and_select(cue)

    def add_crossfade_cue(self):
        next_num = max((c.number for c in self.cues), default=0) + 1
        cue = Cue(next_num, "Crossfade", "Automation")
        self._add_and_select(cue)

    def add_wait_cue(self):
        next_num = max((c.number for c in self.cues), default=0) + 1
        cue = Cue(next_num, "Wait", "Wait", "Auto-Ready")
        cue.duration_ms = 3000
        self._add_and_select(cue)

    def add_group_cue(self):
        next_num = max((c.number for c in self.cues), default=0) + 1
        cue = Cue(next_num, "New Group", "Group", "Auto-Ready")
        cue.is_group = True
        cue.group_mode = "organizational"
        cue.group_children = []
        self._add_and_select(cue)

    def add_start_cue(self):
        next_num = max((c.number for c in self.cues), default=0) + 1
        cue = Cue(next_num, "Start", "Automation")
        self._add_and_select(cue)

    def set_fade_duration(self):
        d, ok = QInputDialog.getInt(
            self, "Fade Duration", "Seconds:", self.fade_duration_ms // 1000, 1, 30
        )
        if ok:
            self.fade_duration_ms = d * 1000
            self.statusBar.showMessage(f"Fade = {d}s")

    def set_global_device(self):
        if not self.available_devices:
            self.statusBar.showMessage("No audio devices found")
            return
        names = [d.description() for d in self.available_devices]
        current = 0
        if self.global_output_device:
            for i, d in enumerate(self.available_devices):
                if d.id() == self.global_output_device.id():
                    current = i
                    break
        name, ok = QInputDialog.getItem(
            self, "Global Default Audio Device",
            "Select default output:", names, current, False
        )
        if ok and name:
            for d in self.available_devices:
                if d.description() == name:
                    self.global_output_device = d
                    self.statusBar.showMessage(f"Global default set to: {name}")
                    break

    def edit_default_positions(self):
        try:
            screens = QGuiApplication.screens()
        except RuntimeError:
            screens = []

        dlg = DefaultPositionsDialog(screens, self.display_defaults, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if hasattr(dlg, "pending_kind"):
                kind = dlg.pending_kind
                cue = self.get_current_cue()
                if cue and cue.cue_type in ("Text", "Image", "Video", "PDF", "Link"):
                    win = self.get_or_create_window(cue)
                    if win and win.isVisible():
                        screen_name = cue.screen_name or (
                            QGuiApplication.primaryScreen().name()
                            if QGuiApplication.primaryScreen() else None
                        )
                        if screen_name:
                            if screen_name not in self.display_defaults:
                                self.display_defaults[screen_name] = {}
                            self.display_defaults[screen_name][kind] = win.geometry()
                            self.statusBar.showMessage(f"Default {kind} position saved")
            else:
                self.display_defaults = dlg.defaults

    def toggle_blackout(self, checked: bool):
        if checked:
            cue = self.get_current_cue()
            screen = self.get_screen_by_name(cue.screen_name) if cue else QGuiApplication.primaryScreen()
            self.blackout_window.show_on_screen(screen)
            self.statusBar.showMessage("Blackout active")
        else:
            self.blackout_window.hide_blackout()
            self.statusBar.showMessage("Blackout cleared")

    def closeEvent(self, event):
        """Stop all playback so media cannot outlive the window."""
        self.stop_all()
        event.accept()

    def populate_device_combo(self, cue=None):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem("Global Default", None)
        for d in self.available_devices:
            self.device_combo.addItem(d.description(), device_id_to_str(d.id()))
        if cue and cue.audio_device_id:
            idx = self.device_combo.findData(cue.audio_device_id)
            self.device_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.device_combo.setCurrentIndex(0)
        self.device_combo.blockSignals(False)


# =====================================================================
# Application entry point
# =====================================================================
def install_excepthook():
    """Catch unhandled exceptions from Qt slots/timers.

    Without this, PySide6 tends to hard-abort the process on any uncaught
    exception inside a signal, slot, or timer — no dialog, no log, the
    window just disappears mid-show. Logs every hit to crash_log.txt next
    to the app. Shows at most one dialog per process so a hot 300 ms timer
    cannot bury the operator in message boxes.
    """
    state = {"shown": False}

    def _hook(exc_type, exc_value, exc_tb):
        if exc_type is KeyboardInterrupt:
            return sys.__excepthook__(exc_type, exc_value, exc_tb)

        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(text, file=sys.stderr)

        try:
            log_path = os.path.join(_app_dir(), "crash_log.txt")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n{text}")
        except Exception:
            pass

        if state["shown"]:
            return
        state["shown"] = True
        try:
            parent = QApplication.activeWindow()
            QMessageBox.critical(
                parent, "CueControl — Unexpected Error",
                f"{exc_type.__name__}: {exc_value}\n\n"
                "CueControl hit a bug. The cue list is probably still intact —\n"
                "use File → Save As now, then restart the app before continuing the show.\n\n"
                "(Details written to crash_log.txt)"
            )
        except Exception:
            pass

    sys.excepthook = _hook


if __name__ == "__main__":
    app = QApplication(sys.argv)
    install_excepthook()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
