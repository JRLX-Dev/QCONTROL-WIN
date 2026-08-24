# =====================================================================
# CueControl Windows
# Lightweight QLab-style cue system
# Audio | Text | Image | Video | PDF | Link | OSC | Wait | Group
# + Volume + Save/Load + Drag & Drop
# =====================================================================

import sys
import os
import time
import uuid
import json
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
from PySide6.QtCore import Qt, QTimer, QUrl, QPoint, QRect, Signal, QSize
from PySide6.QtGui import (
    QColor, QAction, QPainter, QPen, QGuiApplication,
    QMouseEvent, QPixmap, QKeySequence
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
    if raw_id is None:
        return None
    if isinstance(raw_id, str):
        return raw_id
    try:
        return bytes(raw_id).hex()
    except TypeError:
        return str(raw_id)


# =====================================================================
# SECTION: Cue data model
# =====================================================================
class Cue:
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
        self.pdf_multipage = False

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
def cue_to_dict(cue):
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
    cue = Cue(data.get("number", 1), data.get("name", "Untitled"), data.get("cue_type", "Audio"))
    cue.id = data.get("id", str(uuid.uuid4()))
    cue.follow_mode = data.get("follow_mode", "Auto-Ready")
    cue.is_group = data.get("is_group", False)
    raw_mode = data.get("group_mode", "organizational")
    if raw_mode in ("simultaneous", "sequence"):
        raw_mode = "organizational"
    cue.group_mode = raw_mode if raw_mode in ("organizational", "timeline") else "organizational"
    cue.group_children = data.get("group_children", [])
    cue.parent_id = data.get("parent_id")
    cue.timeline_offset_ms = int(data.get("timeline_offset_ms", 0) or 0)
    cue.media_path = data.get("media_path", "")
    cue.duration_ms = data.get("duration_ms", 0)
    cue.audio_device_id = data.get("audio_device_id")
    cue.volume = float(data.get("volume", 1.0))
    cue.screen_name = data.get("screen_name")
    cue.size_mode = data.get("size_mode", "percent")
    cue.width_px = data.get("width_px", 1280)
    cue.height_px = data.get("height_px", 720)
    cue.width_percent = data.get("width_percent", 80.0)
    cue.height_percent = data.get("height_percent", 60.0)
    cue.pos_x = data.get("pos_x")
    cue.pos_y = data.get("pos_y")
    cue.layer = data.get("layer", 50)
    cue.opacity = data.get("opacity", 1.0)
    cue.user_moved = data.get("user_moved", False)
    cue.text = data.get("text", "")
    cue.font_size = data.get("font_size", 64)
    cue.text_color = data.get("text_color", "#FFFFFF")
    cue.bg_color = data.get("bg_color", "rgba(0,0,0,160)")
    cue.image_path = data.get("image_path", "")
    cue.scale_mode = data.get("scale_mode", "Fit")
    cue.image_persistent = data.get("image_persistent", True)
    cue.video_path = data.get("video_path", "")
    cue.video_loop = data.get("video_loop", False)
    cue.video_muted = data.get("video_muted", False)
    cue.pdf_path = data.get("pdf_path", "")
    cue.pdf_page = data.get("pdf_page", 0)
    cue.pdf_zoom_mode = data.get("pdf_zoom_mode", "Fit")
    cue.pdf_multipage = data.get("pdf_multipage", False)
    cue.link_url = data.get("link_url", "")
    cue.link_use_system_browser = data.get("link_use_system_browser", False)
    cue.osc_ip = data.get("osc_ip", "127.0.0.1")
    cue.osc_port = data.get("osc_port", 8000)
    cue.osc_address = data.get("osc_address", "")
    cue.osc_args = data.get("osc_args", "")
    cue.osc_preset = data.get("osc_preset", "ETC EOS")
    return cue
