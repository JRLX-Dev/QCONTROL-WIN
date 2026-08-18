# CueControl Windows

Lightweight QLab-style cue system for Windows 10/11.
Built for churches, schools, and small productions that need reliable playback without QLab pricing.

**Status:** Alpha — test thoroughly before any live show.

## Features

- **Cue types:** Audio, Video, Image, Text (supertitles), PDF, Link/Web, OSC, Wait, Group, Automation (Stop / Fade / Crossfade)
- **Groups:** `organizational` (GO starts first child) and `timeline` (children fire at offsets)
- **Multi-display:** target text/image/video/PDF/link to any connected screen
- **Drag & drop:** reorder cues, drop into groups, drop media files from Explorer
- **OSC presets:** ETC EOS, GrandMA, HOG, Midas/Behringer, Allen & Heath, Yamaha
- **Save/Load:** `.ccs` show files
- **Portable-friendly:** designed for external SSD / no-admin workflows

## Requirements

- Windows 10 or 11
- Python 3.10+ recommended
- See `requirements.txt`

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional:
- `PySide6` with QtPdf / QtWebEngine for PDF and embedded browser cues
- `python-osc` for OSC cues

## Run

```powershell
& ".\.venv\Scripts\python.exe" ".\Main.py"
```

## Controls (Alpha)

| Action | Control |
|--------|---------|
| GO | Space or **GO** button |
| Fade & Stop | Esc or **Fade & Stop** |
| Stop All | **STOP ALL** |
| Delete cue | Ctrl+Delete or ✕ on row |

## Alpha testing notes

- Confirm drag-reorder and group nesting on your machine
- Test multi-monitor targeting if you have external displays
- OSC needs a reachable console/IP; use loopback only for dry runs
- Report crashes with steps + full traceback

## License

See `LICENSE`.
