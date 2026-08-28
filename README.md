# CueControl Windows

**Handing this folder to a booth volunteer?** Open **`START HERE.txt`** — that is the only sheet they need.

Lightweight QLab-style cue system for **Windows 10 / 11**.
Built for churches, schools, and small productions that need reliable playback without QLab pricing.

**Status:** Alpha — test thoroughly before any live show. Do not use as sole playback on a critical performance until you have dry-run tested your full stack.

**Booth accessibility (Phase 1):** STANDBY/RUNNING is written in the cue list (not color-only). View → UI size 100/125/150%. Help → Keyboard shortcuts (F1). Works with Windows Narrator, Magnifier, and Sticky Keys. Captions on video (Phase 2) are not in this build.

---

## Download and run (testers)

You do **not** need to install Python on the PC.

1. On GitHub: **Code → Download ZIP**. Extract the folder to a fast drive.
2. Double-click **`Run CueControl.bat`**.
   - First run downloads official **[python.org](https://www.python.org/downloads/)** 64-bit Python **into this folder** (`runtime\`) — no admin, not Program Files — then installs packages. Needs internet.
   - Later runs just start the app.

Microsoft Store Python is ignored on purpose.

If the window flashes and closes, run the `.bat` from a Command Prompt so you can read the error.

---

## Flash drive / SSD (move between PCs)

Python lives **in the CueControl folder**, not on the host PC. After one successful first run, copy the **whole folder** (including `runtime\`) onto the stick.

1. Format the drive **NTFS** (factory FAT32 often breaks the Python installer).
2. Copy the CueControl folder onto it.
3. On a PC **with internet**, double-click `Run CueControl.bat` once and wait until the window opens.
4. Unplug. On the next Windows **10/11 64-bit** PC, double-click `Run CueControl.bat` again. That PC does not need Python installed.

Still true:

- 64-bit Windows 10 or 11 only (prepare the stick on an Intel/AMD PC).
- Cheap USB flash is fine for the **app**; **video** wants an SSD.
- First run on a new stick needs internet. After `runtime\` is populated, later PCs can be offline.
- Show files still store **absolute** media paths. Keep media on the same drive; if GO says a file is missing after the letter changes (`E:` → `F:`), Browse and pick it again.

Do **not** launch `Main.py` with a PC-installed Python. Always use the `.bat`.

---

## Features

- **Cue types:** Audio, Video, Image, Text (supertitles), PDF, Link/Web, OSC, Wait, Group, Automation (Stop / Fade / Crossfade)
- **PDF multipage:** optional “Show all pages (scroll)” mode + Prev / Next page buttons
- **Groups:** `organizational` (GO starts first child, stand-by stays there) and `timeline` (children fire at offsets)
- **Multi-display:** target text / image / video / PDF / link to any connected screen
- **Edit Mode:** blue frame with tight 4–5 px margins; drag to move, drag edges to resize; geometry locks on release
- **Show hardening:** 180 ms GO debounce, Space/Esc ignore auto-repeat, live GO does not steal console focus, retrigger + cut previous Audio/Video, Auto-Fire cap (8) with loop detection, stand-by preserved after STOP ALL, Test windows do not leak, video/text/image edge-drag
- **Drag & drop:** reorder cues, drop into groups, drop media files from Explorer
- **OSC presets:** ETC EOS, GrandMA, HOG, Midas/Behringer, Allen & Heath, Yamaha
- **Save / Load:** `.ccs` show files
- **Portable-friendly:** designed for external SSD / no-admin workflows

---

## Requirements

- Windows 10 or 11 (64-bit)
- Internet on **first** run (to fetch Python + PySide6 into `runtime\`)
- After that: this folder only (`runtime\` travels with the drive)

Optional (feature-dependent):
- QtPdf support in your PySide6 install → PDF cues (including multipage)
- QtWebEngine → embedded Link cues
- `python-osc` → OSC cues (listed in requirements)

---

## Install (manual)

Prefer **`Run CueControl.bat`**. That is the portable path.

If you already have python.org Python and only want a one-PC install:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& ".\.venv\Scripts\Activate.ps1"
pip install -r requirements.txt
```

A `.venv` does **not** travel with a flash drive. Use the `.bat` + `runtime\` for that.

---

## Run instructions

### Preferred

Double-click **`Run CueControl.bat`** in the project folder.

To only fetch Python (no app start), double-click **`Install Python.bat`**.

### Manual session

```powershell
& ".\runtime\python\python.exe" ".\Main.py"
```

### First launch checklist

1. Confirm the main window opens and the status bar shows Ready.
2. **Settings → Set Global Default Audio Device** if you are not using the system default.
3. Plug in any extra displays you will use; they should appear in the Display dropdown on overlay cues.
4. Create one Audio cue and press **GO** (or Space) to verify sound.
5. Create one Text cue, assign a display, enable **Test / Preview**, then **Edit Mode** if you need to position it.

---
## Operator brief (Alpha)

### Transport

| Action | Control |
|--------|---------|
| GO selected cue | **Space** or green **GO** |
| Fade & Stop (all) | **Esc** or amber **Fade & Stop** |
| Stop All (immediate) | red **STOP ALL** |
| Delete selected cue | **Ctrl+Delete** or row **✕** |

Global fade time: **Settings → Set Global Fade Duration**.

GO is debounced (~180 ms) so rapid Space / mouse clicks do not double-fire.
Held Space / Esc do not auto-repeat. Live GO does not pull keyboard focus onto the overlay.

### Building a cue list

1. Use the left toolbar to add cue types, **or** drag media files from Explorer into the cue list (audio / video / image / PDF).
2. Select a cue → edit **Properties** on the right (name, number, follow mode, duration, volume, display, etc.).
3. Cue numbers can be fractional (e.g. `1.5`). Changing the number reorders the stack.
4. **Follow modes:**
   - **Off** — stays on this cue after GO
   - **Auto-Ready** — after GO, selection advances to the next cue (does not auto-start it)
   - **Auto-Follow** — when this cue’s duration ends, the next cue starts
   - **Auto-Fire** — as soon as this cue starts, the next cue also starts (max 8 in a chain; loops are stopped)

### Drag and drop

- Drag a cue onto another cue → reorder (numbers adjust)
- Drag a cue onto a **Group** → become a child of that group
- Drop files from Explorer → create matching cues

### Groups

1. Add a **Group** cue.
2. In Properties set **Group mode**:
   - **organizational** — GO starts the **first** child and leaves stand-by on that child; continue with GO for the rest
   - **timeline** — GO starts the clock; each child fires at its **Timeline offset** (ms)
3. Drag cues onto the group to parent them.
4. For timeline children, select each child and set **Timeline offset**.

### Displays / overlays (Text, Image, Video, PDF, Link)

1. Select the cue → choose **Display** (primary or external).
2. **Test / Preview** shows the cue without committing a full GO run.
3. **Edit Mode** draws a blue border (tight 4–5 px margins); drag to move, drag edges to resize. Uncheck Edit Mode to lock position/size. Geometry is also saved on mouse release.
4. Layer (0–100) and Opacity control stacking and transparency.
5. **Blackout** puts a full black window on the selected (or primary) screen.

### PDF

- **Start page** and **Zoom** (Fit / FitWidth / Actual) work as before.
- Check **Show all pages (scroll)** for multipage continuous view.
- Use **◀ Prev** / **Next ▶** (or the page spin box) to change page while the cue is open.

### Audio / Video volume

Per-cue **Volume** slider normalizes levels across the stack. Video can also be muted or looped.
A new Audio or Video GO cuts the previous same-type bed (one bed at a time).

### OSC

1. Add an OSC cue.
2. Pick a **Console Preset** (EOS, GrandMA, etc.) or Custom.
3. Set IP, port, address, and optional arguments.
4. GO sends one UDP packet. Network must reach the console; firewall may block outbound UDP.

### Save / Load

- **File → Save** / **Save As** → `.ccs` show file (atomic write — a yanked USB stick will not truncate the previous save)
- **File → Open Show** loads cues, fade duration, and display defaults. Corrupt cues are skipped with a warning
- Overlay layouts are **percent of House/Stage/Confidence**, not a laptop's pixel grid. At the venue: **Settings → Map displays…**
- Media paths are stored as absolute paths in Alpha; keep media in a stable folder or re-link after moving drives

---

## Suggested Alpha test plan

1. Single audio GO / STOP / Fade
2. Text + Image on a second monitor (if available)
3. Video with volume and mute
4. PDF single-page and multipage scroll + Prev/Next
5. Drag reorder + Explorer file drop
6. Group organizational: GO group → first child runs, stand-by stays on that child
7. Group timeline: offsets 0 / 3000 / 6000 ms fire in order
8. Rapid GO clicks (debounce) and STOP ALL (stand-by preserved)
9. Edit Mode resize / move → uncheck → confirm geometry sticks
10. Save show → quit → reopen → confirm numbers, groups, positions, multipage flag
11. OSC to a known device or packet monitor (optional)
12. Hold Space on a short Auto-Ready stack — only one GO per press
13. Auto-Fire chain of 10+ cues — stops at 8, status bar reports the cap
14. GO a text/image/video overlay, then press Space — console still receives GO
15. GO audio A, then GO audio B — A stops, B plays (same for video)
16. Test preview on cue 1, click cue 2 — cue 1 window closes
17. Quit while a video is up — playback stops with the app

Report failures with: **steps**, **expected vs actual**, and **full traceback** from the console.

---

## Distribution workflow (Alpha)

| Tier | Device | What’s on it | Who |
|------|--------|--------------|-----|
| GitHub ZIP | Their PC | Source + `Run CueControl.bat` | Testers; first run fetches Python into `runtime\` |
| Software-only | USB flash (NTFS) | App + `runtime\` + `.bat` | First-look testers; media stays on the house PC |
| Basic kit | 250 GB NVMe in USB-C enclosure | App + `runtime\` + sample 1080p + `Shows\` | Batch-cloned via Sabrent dock |
| Super-test kit | USB-C SSD | Full stack + their media | Multi-display, groups, OSC, real dry runs |

**Clone process (basic kits)**

1. Build one master NVMe (NTFS): `CueControl\` with `Main.py`, `runtime\`, `Run CueControl.bat`, `Media\`, `Shows\`.
2. Smoke-test from that drive.
3. Offline-clone to same-size or larger 250 GB targets.
4. Spot-check one drive per batch.

**Future — launch updater (not built yet)**

- `Run CueControl.bat` will compare local `VERSION.txt` to GitHub `main`.
- If newer, download **only** `Main.py` (and `VERSION.txt`), then start.
- Offline / GitHub fail → start local copy. Never auto-update `runtime\`.

---

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| `No module named numpy` | You launched `Main.py` with the wrong Python. Use `Run CueControl.bat` |
| `python` / `py` not found | Ignore it — double-click `Run CueControl.bat`; Python is bundled into `runtime\` |
| Installer / download failed | Internet to python.org; format the stick **NTFS**; retry `Install Python.bat` |
| Works on PC A, not PC B | Copy the **whole** folder including `runtime\`. Stick must be NTFS. 64-bit Windows 10/11. |
| Execution policy error | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` |
| No sound | Check Global Default Audio Device; confirm file path exists |
| Overlay on wrong screen | Select Display in Properties; re-enable Test/Edit after changing |
| Hard to grab resize edges | Labels (and video) are mouse-transparent; grab near the blue border |
| Indentation / import errors | Re-download `Main.py` from this repo; do not mix partial pastes |
| OSC no effect | Verify IP/port, console OSC enable, Windows firewall |
| Slow scrubbing / stutters | Run from SSD, not USB flash |

---

## Known Alpha limits

- No full Show Mode (Windows key lock) yet
- No packaged `.exe` installer yet
- Nested groups not supported
- Media paths not yet relative/portable by default
- Launch updater (GitHub `VERSION.txt`) not implemented yet
- Fade & Stop is a delayed hard stop (does not ramp volume)

---

## License

See `LICENSE`.
