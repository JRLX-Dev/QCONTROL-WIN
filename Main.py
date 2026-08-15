# =====================================================================
# CueControl Windows
# Lightweight QLab-style cue system
# Audio | Text | Image | Video | PDF | Link | OSC + Volume + Save/Load
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

        # Link
        self.link_url = ""
        self.link_use_system_browser = False

        # OSC
        self.osc_ip = "127.0.0.1"
        self.osc_port = 8000
        self.osc_address = ""
        self.osc_args = ""          # comma-separated string for simplicity
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
    cue.link_url = data.get("link_url", "")
    cue.link_use_system_browser = data.get("link_use_system_browser", False)
    cue.osc_ip = data.get("osc_ip", "127.0.0.1")
    cue.osc_port = data.get("osc_port", 8000)
    cue.osc_address = data.get("osc_address", "")
    cue.osc_args = data.get("osc_args", "")
    cue.osc_preset = data.get("osc_preset", "ETC EOS")
    return cue


# =====================================================================
# SECTION: Cue list row widget
# =====================================================================
class CueRowWidget(QWidget):
    delete_clicked = Signal(str)

    def __init__(self, cue, parent=None):
        super().__init__(parent)
        self.cue_id = cue.id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        num_str = str(int(cue.number)) if cue.number == int(cue.number) else f"{cue.number:.1f}"
        text = f"{num_str}  –  {cue.name}  ({cue.cue_type})"

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

        self.label = QLabel(text)
        self.label.setStyleSheet("background: transparent; color: #ddd;")
        layout.addWidget(self.label, 1)

        self.btn = QPushButton("✕")
        self.btn.setFixedSize(24, 24)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: #5a1a1a; color: #ffb0b0;
                border: 1px solid #8a3030; border-radius: 4px;
                font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #a03030; color: white; }
        """)
        self.btn.setToolTip("Delete cue")
        self.btn.clicked.connect(lambda: self.delete_clicked.emit(self.cue_id))
        layout.addWidget(self.btn)


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
    EDGE = 14

    def __init__(self, title="Overlay", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
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

        if cue.user_moved:
            self.resize(w, h)
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
        layout.setContentsMargins(24, 16, 24, 16)
        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

    def _restore_style(self):
        if self.current_cue:
            self.setStyleSheet(f"background-color: {self.current_cue.bg_color}; border-radius: 10px;")
        else:
            self.setStyleSheet("background-color: rgba(0,0,0,160); border-radius: 10px;")

    def show_text(self, cue, screen, defaults):
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
        self.activateWindow()


class ImageDisplayWindow(OverlayWindow):
    def __init__(self, parent=None):
        super().__init__("Image Output", parent)
        self.resize(800, 450)
        self.original_pixmap = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.label)

    def _restore_style(self):
        self.setStyleSheet("background-color: rgba(0,0,0,200); border-radius: 6px;")

    def show_image(self, cue, screen, defaults):
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
        self.player.setVideoOutput(self.video_widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.video_widget)

        self.current_cue = None

    def _restore_style(self):
        self.setStyleSheet("background-color: black;")

    def show_video(self, cue, screen, defaults, audio_device=None):
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

    def show_pdf(self, cue, screen, defaults):
        if not HAS_PDF or self.doc is None:
            return
        self.current_cue = cue
        if not cue.pdf_path or not os.path.exists(cue.pdf_path):
            return

        self.doc.load(cue.pdf_path)
        page = max(0, min(cue.pdf_page, self.doc.pageCount() - 1))
        self.view.setPage(page)

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
        self.activateWindow()

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

    def show_url(self, cue, screen, defaults):
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CueControl Windows")
        self.setGeometry(80, 60, 1550, 920)

        self.cues = []
        self.active_cues = {}
        self.current_cue_id = None
        self.fade_duration_ms = 2000
        self.current_show_path = None
        self._debounce_timers = {}

        self.global_output_device = None
        self.available_devices = []
        self.available_screen_names = []          # only names – never QScreen objects

        self.refresh_audio_devices()
        self.refresh_screens()

        self.text_windows = {}
        self.image_windows = {}
        self.video_windows = {}
        self.pdf_windows = {}
        self.web_windows = {}
        self.display_defaults = {}
        self.blackout_window = BlackoutWindow()

        self.device_check_timer = QTimer(self)
        self.device_check_timer.timeout.connect(self.check_audio_devices)
        self.device_check_timer.start(3000)

        self.screen_check_timer = QTimer(self)
        self.screen_check_timer.timeout.connect(self.check_screens)
        self.screen_check_timer.start(4000)

        self.build_ui()
        self.refresh_cue_list()
        self.update_running_list()
        self.update_window_title()

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
    # Screen handling – completely safe (never cache QScreen objects)
    # ------------------------------------------------------------------
    def refresh_screens(self):
        """Only store screen names. Never keep live QScreen objects."""
        try:
            self.available_screen_names = [s.name() for s in QGuiApplication.screens()]
        except RuntimeError:
            self.available_screen_names = []

    def check_screens(self):
        """Safely detect display changes without holding deleted QScreen objects."""
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
        """Always return a live QScreen (or primary). Never cache the object."""
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
        """Called only when leaving Edit Mode – prevents feedback loops."""
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
            f"Size locked: {cue.width_px}×{cue.height_px}px on {cue.screen_name or 'primary'}"
        )

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------
    def new_show(self):
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
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.current_show_path = path
            self.update_window_title()
            self.statusBar.showMessage(f"Saved: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save show:\n{e}")

    def load_show(self):
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

        self.stop_all()
        self.cues.clear()
        self.current_cue_id = None

        for cdata in data.get("cues", []):
            self.cues.append(cue_from_dict(cdata))

        self.fade_duration_ms = data.get("fade_duration_ms", 2000)

        self.display_defaults.clear()
        for screen_name, kinds in data.get("display_defaults", {}).items():
            self.display_defaults[screen_name] = {}
            for kind, rect_list in kinds.items():
                if isinstance(rect_list, list) and len(rect_list) == 4:
                    self.display_defaults[screen_name][kind] = QRect(*rect_list)

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
            ("Start", self.add_start_cue),
        ]:
            a = QAction(text, self)
            a.triggered.connect(slot)
            toolbar.addAction(a)

        content = QVBoxLayout()
        split = QHBoxLayout()

        self.cue_list = QListWidget()
        self.cue_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cue_list.itemClicked.connect(self.on_cue_selected)
        split.addWidget(self.cue_list, stretch=2)

        right_tabs = QTabWidget()
        right_tabs.setMinimumWidth(520)

        # ---------- Properties tab ----------
        prop_tab = QWidget()
        prop_layout = QVBoxLayout(prop_tab)
        form = QFormLayout()

        self.number_spin = QDoubleSpinBox()
        self.number_spin.setRange(0.1, 9999.9)
        self.number_spin.setDecimals(1)
        self.number_spin.setSingleStep(1.0)
        self.number_spin.editingFinished.connect(self.apply_cue_number)
        form.addRow("Cue Number:", self.number_spin)

        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.apply_name_change)
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
        rl.addWidget(self.running_list)
        right_tabs.addTab(run_tab, "Cues Running")

        split.addWidget(right_tabs, stretch=1)
        content.addLayout(split)

        # GO / STOP bar
        bar = QFrame()
        bar.setFrameShape(QFrame.StyledPanel)
        bar.setFixedHeight(80)
        bl = QHBoxLayout(bar)
        self.go_btn = QPushButton("GO")
        self.go_btn.setStyleSheet(
            "background-color:#00AA00; color:white; font-size:24px; font-weight:bold; padding:15px;"
        )
        self.go_btn.clicked.connect(self.go_pressed)
        self.stop_btn = QPushButton("STOP ALL")
        self.stop_btn.setStyleSheet(
            "background-color:#CC0000; color:white; font-size:18px; padding:12px;"
        )
        self.stop_btn.clicked.connect(self.stop_all)
        self.fade_btn = QPushButton("Fade && Stop")
        self.fade_btn.clicked.connect(self.fade_and_stop)
        bl.addWidget(self.go_btn, 1)
        bl.addWidget(self.stop_btn, 1)
        bl.addWidget(self.fade_btn, 1)
        content.addWidget(bar)
        main_layout.addLayout(content)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")

        # Shortcuts
        for key, slot in [("Space", self.go_pressed), ("Esc", self.fade_and_stop)]:
            a = QAction(self)
            a.setShortcut(key)
            a.triggered.connect(slot)
            self.addAction(a)

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

    # ------------------------------------------------------------------
    # Core list / selection
    # ------------------------------------------------------------------
    def refresh_cue_list(self):
        current_id = self.current_cue_id
        self.cue_list.clear()
        for cue in sorted(self.cues, key=lambda c: c.number):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, cue.id)
            item.setSizeHint(QSize(0, 36))
            self.cue_list.addItem(item)
            row = CueRowWidget(cue)
            row.delete_clicked.connect(self.delete_cue_by_id)
            self.cue_list.setItemWidget(item, row)
            if cue.id == current_id:
                item.setSelected(True)

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
        self.cues = [c for c in self.cues if c.id != cue_id]
        self.destroy_window(cue)

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
                      self.link_group, self.osc_group, self.wave_group):
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
        self.current_cue_id = cue.id

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
            self.on_osc_preset_changed(cue.osc_preset)  # refresh common list
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

        # Set recommended port
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
                    # Try int, then float, else string
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
                win.show_text(cue, self.get_screen_by_name(cue.screen_name), self.display_defaults)

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
            self.statusBar.showMessage("Edit Mode OFF – size locked")

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
    # Playback
    # ------------------------------------------------------------------
    def start_cue(self, cue):
        if cue.id in self.active_cues:
            self.statusBar.showMessage(f"Cue {cue.number} is already running")
            return

        IMPLEMENTED_TYPES = ("Audio", "Video", "Image", "Text", "PDF", "Link", "OSC")
        if cue.cue_type not in IMPLEMENTED_TYPES:
            self.statusBar.showMessage(f"{cue.cue_type} cues aren't implemented yet")
            return

        info = {"cue": cue, "start": time.time(), "player": None, "output": None}

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

        elif cue.cue_type == "Text":
            screen = self.get_screen_by_name(cue.screen_name)
            win = self.get_or_create_window(cue)
            win.show_text(cue, screen, self.display_defaults)

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

        elif cue.cue_type == "Video":
            if not cue.video_path or not os.path.exists(cue.video_path):
                self.statusBar.showMessage(f"Video file missing: {cue.video_path or '(none)'}")
                return
            screen = self.get_screen_by_name(cue.screen_name)
            win = self.get_or_create_window(cue)
            device = self.get_device_by_id(cue.audio_device_id)
            win.show_video(cue, screen, self.display_defaults, device)

        elif cue.cue_type == "PDF":
            if not cue.pdf_path or not os.path.exists(cue.pdf_path):
                self.statusBar.showMessage(f"PDF file missing: {cue.pdf_path or '(none)'}")
                return
            screen = self.get_screen_by_name(cue.screen_name)
            win = self.get_or_create_window(cue)
            win.show_pdf(cue, screen, self.display_defaults)

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
            else:
                screen = self.get_screen_by_name(cue.screen_name)
                win = self.get_or_create_window(cue)
                win.show_url(cue, screen, self.display_defaults)

        elif cue.cue_type == "OSC":
            success = self.send_osc(cue)
            if not success:
                return
            # OSC cues are instantaneous – we still track them briefly so they appear in Running
            # but they auto-finish almost immediately unless duration is set.

        self.active_cues[cue.id] = info
        self.update_running_list()
        self.statusBar.showMessage(f"Started {cue.number} – {cue.name}")

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
        if not self.current_cue_id and self.cues:
            first = sorted(self.cues, key=lambda c: c.number)[0]
            self.select_cue_by_id(first.id)

        cue = self.get_current_cue()
        if not cue:
            return

        self.start_cue(cue)

        if cue.follow_mode == "Auto-Ready":
            sorted_cues = sorted(self.cues, key=lambda c: c.number)
            try:
                idx = sorted_cues.index(cue)
                if idx + 1 < len(sorted_cues):
                    self.select_cue_by_id(sorted_cues[idx + 1].id)
            except ValueError:
                pass

    def stop_all(self):
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
        self.current_cue_id = None
        self.refresh_cue_list()
        self.update_running_list()
        self.statusBar.showMessage("All stopped")

    def fade_and_stop(self):
        self.statusBar.showMessage(f"Fading {self.fade_duration_ms//1000}s...")
        QTimer.singleShot(self.fade_duration_ms, self.stop_all)

    def update_running_list(self):
        self.running_list.clear()
        now = time.time()
        finished = []
        for cid, info in list(self.active_cues.items()):
            cue = info["cue"]
            elapsed = (now - info["start"]) * 1000
            # OSC cues with no duration finish almost immediately
            if cue.cue_type == "OSC" and cue.duration_ms == 0:
                finished.append(cid)
                continue
            if cue.duration_ms > 0 and elapsed >= cue.duration_ms:
                finished.append(cid)
                continue
            if cue.duration_ms > 0:
                remaining = max(0, cue.duration_ms - elapsed)
                t = f"{int(remaining//60000):02d}:{int((remaining%60000)//1000):02d}"
            else:
                t = "∞"
            self.running_list.addItem(f"▶ {cue.number} - {cue.name}   [{t}]")
        for cid in finished:
            self.stop_single_cue(cid)

    # ------------------------------------------------------------------
    # Add cue helpers
    # ------------------------------------------------------------------
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
        """Fixed: correctly pass screens and defaults to the dialog."""
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
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
