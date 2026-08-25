# Changelog

## Alpha (2026-08-25)

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
