# CueControl Windows

Lightweight QLab-style cue system for Windows 10/11.
Built for churches, schools, and small productions that need reliable playback without QLab pricing.

**Status:** Alpha — test thoroughly before any live show. Do not use as sole playback on a critical performance until you have dry-run tested your stack.

---

## Download and run (testers)

1. Install **Python 3.10+** from [python.org](https://www.python.org/downloads/) (not the Microsoft Store). Check **Add python.exe to PATH**.
2. On GitHub: **Code → Download ZIP**. Extract the folder to a fast drive (SSD preferred).
3. Double-click **`Run CueControl.bat`**.
   - First run creates `.venv` and installs packages (needs internet; a few minutes).
   - Later runs just start the app.

If the window flashes and closes, run the `.bat` from a Command Prompt so you can read the error.

Do **not** launch `Main.py` with the Store Python under `WindowsApps`. Always use the `.bat` or `.venv\Scripts\python.exe`.

---

## Features

- **Cue types:** Audio, Video, Image, Text (supertitles), PDF, Link/Web, OSC, Wait, Group, Automation (Stop / Fade / Crossfade)
- **Groups:** `organizational` (GO starts first child) and `timeline` (children fire at offsets)
- **Multi-display:** target text/image/video/PDF/link to any connected screen
- **Drag & drop:** reorder cues, drop into groups, drop media files from Explorer
- **OSC presets:** ETC EOS, GrandMA, HOG, Midas/Behringer, Allen & Heath, Yamaha
- **Save/Load:** `.ccs` show files
- **Portable-friendly:** designed for external SSD / no-admin workflows

---

## Requirements

- Windows 10 or 11
- Python 3.10 or newer recommended
- Packages listed in `requirements.txt`

Optional (feature-dependent):
- QtPdf support in your PySide6 install → PDF cues
- QtWebEngine → embedded Link cues
- `python-osc` → OSC cues (listed in requirements)

---

## Install (manual)

1. Copy the project folder to a fast drive (internal disk or external **SSD** preferred; USB flash drives are often too slow for media).
2. Open **PowerShell** in that folder.
3. Create and activate a virtual environment:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& ".\.venv\Scripts\Activate.ps1"
pip install -r requirements.txt
```

4. Keep the `.venv` folder with the project if you move the folder to another machine (same Windows arch).

---

## Run instructions

### Preferred

Double-click **`Run CueControl.bat`** in the project folder.

### Manual session

```powershell
& ".\.venv\Scripts\python.exe" ".\Main.py"
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

### Building a cue list

1. Use the left toolbar to add cue types, **or** drag media files from Explorer into the cue list (audio / video / image / PDF).
2. Select a cue → edit **Properties** on the right (name, number, follow mode, duration, volume, display, etc.).
3. Cue numbers can be fractional (e.g. `1.5`). Changing the number reorders the stack.
4. **Follow modes:**
   - **Off** — stays on this cue after GO
   - **Auto-Ready** — after GO, selection advances to the next cue (does not auto-start it)
   - **Auto-Follow** — when this cue’s duration ends, the next cue starts
   - **Auto-Fire** — as soon as this cue starts, the next cue also starts

### Drag and drop

- Drag a cue onto another cue → reorder (numbers adjust)
- Drag a cue onto a **Group** → become a child of that group
- Drop files from Explorer → create matching cues

### Groups

1. Add a **Group** cue.
2. In Properties set **Group mode**:
   - **organizational** — GO starts the **first** child only; continue with GO / automation for the rest
   - **timeline** — GO starts the clock; each child fires at its **Timeline offset** (ms)
3. Drag cues onto the group to parent them.
4. For timeline children, select each child and set **Timeline offset**.

### Displays / overlays (Text, Image, Video, PDF, Link)

1. Select the cue → choose **Display** (primary or external).
2. **Test / Preview** shows the cue without committing a full GO run.
3. **Edit Mode** draws a blue border; drag to move, drag edges to resize. Uncheck Edit Mode to lock position/size.
4. Layer (0–100) and Opacity control stacking and transparency.
5. **Blackout** puts a full black window on the selected (or primary) screen.

### Audio / Video volume

Per-cue **Volume** slider normalizes levels across the stack. Video can also be muted or looped.

### OSC

1. Add an OSC cue.
2. Pick a **Console Preset** (EOS, GrandMA, etc.) or Custom.
3. Set IP, port, address, and optional arguments.
4. GO sends one UDP packet. Network must reach the console; firewall may block outbound UDP.

### Save / Load

- **File → Save** / **Save As** → `.ccs` show file
- **File → Open Show** loads cues, fade duration, and display defaults
- Media paths are stored as absolute paths in Alpha; keep media in a stable folder or re-link after moving drives

---

## Suggested Alpha test plan

1. Single audio GO / STOP / Fade
2. Text + Image on a second monitor (if available)
3. Video with volume and mute
4. Drag reorder + Explorer file drop
5. Group organizational: GO group → only first child runs
6. Group timeline: offsets 0 / 3000 / 6000 ms fire in order
7. Save show → quit → reopen → confirm numbers, groups, positions
8. OSC to a known device or packet monitor (optional)

Report failures with: **steps**, **expected vs actual**, and **full traceback** from the console.

---

## Distribution workflow (Alpha)

| Tier | Device | What’s on it | Who |
|------|--------|--------------|-----|
| GitHub ZIP | Their PC | Source + `Run CueControl.bat` | Testers with Python + internet |
| Software-only | USB flash | App + `.venv` + `.bat` | First-look testers; media stays on the house PC |
| Basic kit | 250 GB NVMe in USB-C enclosure | App + sample 1080p + `Shows\` | Batch-cloned via Sabrent dock |
| Super-test kit | USB-C SSD | Full stack + their media | Multi-display, groups, OSC, real dry runs |

**Clone process (basic kits)**

1. Build one master NVMe (NTFS): `CueControl\` with `Main.py`, `.venv`, `Run CueControl.bat`, `Media\`, `Shows\`.
2. Smoke-test from that drive.
3. Offline-clone to same-size or larger 250 GB targets.
4. Spot-check one drive per batch.

**Future — launch updater (not built yet)**

- `Run CueControl.bat` will compare local `VERSION.txt` to GitHub `main`.
- If newer, download **only** `Main.py` (and `VERSION.txt`), then start.
- Offline / GitHub fail → start local copy. Never auto-update `.venv`.

---

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| `No module named numpy` | You used Store Python. Use `Run CueControl.bat` or `.venv\Scripts\python.exe` |
| `python` / `git` not found | Install python.org Python with “Add to PATH” |
| Execution policy error | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` |
| No sound | Check Global Default Audio Device; confirm file path exists |
| Overlay on wrong screen | Select Display in Properties; re-enable Test/Edit after changing |
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

---

## License

See `LICENSE`.
