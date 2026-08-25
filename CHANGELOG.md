# Changelog

## Alpha (2026-08-25) — portable USB / SSD kit

### New
- **Portable `.exe` folder** for flash drives and external SSDs — no Python, no admin, no installer
- `CueControl_launch.py` wraps `Main.py` (unchanged) so the kit root is the folder with `CUECONTROL_PORTABLE.txt`
- Show files store media **relative to the kit**; old absolute paths are rewritten when the file still exists under `Media\` / `Shows\`
- File dialogs default to `Shows\` and `Media\Audio|Video|Images|PDF`
- `build_portable.bat` + `CueControl.spec` (PyInstaller **onedir**, not onefile)
- GitHub Actions workflow **Build portable kit** uploads `CueControl-Portable.zip`
- Windowed exe tees start/crash text to `Logs\cuecontrol.log`

### Docs
- `PORTABLE.md` (builder) and `README-USB.txt` (booth operator)

---

## Alpha (2026-08-25) — show-safety pass

### Fixed
- Held **Space** no longer GO-walks the list (auto-repeat ignored; 180 ms debounce kept)
- Held **Esc** no longer stacks multiple Fade & Stop timers
- **Auto-Fire** is capped at 8 cues and stops on a loop (same cue seen twice)
- Live **GO** no longer steals keyboard focus — Space/Esc stay on the console
- GO of an already-running cue **restarts** it (was a no-op)
- A new **Audio** or **Video** cue cuts the previous same-type bed instead of stacking
- Switching cues closes leaked **Test / Edit** preview windows
- Organizational **Group** GO keeps stand-by on the first child (no longer skips the rest of the folder)
- PDF **Next** stops at the last page
- **Video** Edit Mode: mouse-transparent widget + 4 px frame so you can grab the blue edges
- Closing the app stops all playback so media cannot outlive the window
- Duplicate Group / Timeline properties block removed

### Docs
- Module and class docstrings on Cue, OverlayWindow, and MainWindow

---

## Alpha (2026-08-25) — multipage PDF + first hardening

### New
- **PDF multipage** — optional continuous scroll mode + Prev / Next page controls
- **Show hardening**
  - 180 ms GO debounce (rapid Space / mouse clicks)
  - STOP ALL preserves stand-by cue selection
  - Transparent labels so edge-drag works reliably
  - Geometry saved on mouse release in Edit Mode
- **Tighter blue Edit Mode frame** (4–5 px margins around text / image content)

### Existing (unchanged)
- Cue types: Audio, Video, Image, Text, PDF, Link, OSC, Wait, Group, Automation
- Group modes: organizational + timeline offsets
- Multi-display overlays with edit mode / layer / opacity
- Drag-drop reorder, group parenting, external file drops
- Save/Load `.ccs` shows
- OSC preset library (EOS, GrandMA, HOG, Midas/Behringer, A&H, Yamaha)
- Equal-width rounded transport bar (GO / STOP ALL / Fade & Stop)

### Known Alpha limits
- No full Show Mode lock yet
- No Program Files installer (portable folder instead)
- Nested groups not supported
- Fade & Stop is a delayed hard stop (does not ramp volume)
- Launch updater (`VERSION.txt` GitHub compare) not implemented yet
