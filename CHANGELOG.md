# Changelog

## Alpha (2026-08-25) — local Python installer

### New
- **`Install Python.bat`** / **`Run CueControl.bat`** put official python.org 64-bit 3.12 **in `runtime\`** (this folder). Host Python and `.venv` are not used — so a USB/SSD can move between PCs
- No admin. Embeddable zip is the fallback if the full installer cannot run
- Later launches reuse `runtime\` and stay offline except for package updates

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
- No installer / packaged `.exe` yet
- Nested groups not supported
- Media paths still absolute by default
- Launch updater (`VERSION.txt`) not implemented yet
- Fade & Stop is a delayed hard stop (does not ramp volume)
