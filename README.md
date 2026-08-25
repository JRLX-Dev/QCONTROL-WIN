# CueControl Windows

Lightweight QLab-style cue system for **Windows 10 / 11**.
Built for churches, schools, and small productions that need reliable playback without QLab pricing.

**Status:** Alpha — test thoroughly before any live show. Do not use as sole playback on a critical performance until you have dry-run tested your full stack.

---

## Download and run

### Portable kit (USB / SSD — no Python, no admin)

This is the show-computer path.

1. Get **CueControl-Portable.zip** from [Releases](https://github.com/JRLX-Dev/QCONTROL-WIN/releases) **or** build it (below).
2. Copy the unzipped folder onto an **SSD** (USB-C / NVMe enclosure preferred; cheap flash drives stutter on video).
3. Double-click **`CueControl.exe`**.
4. Put media in `Media\Audio`, `Media\Video`, `Media\Images`, `Media\PDF`.
5. Save shows into `Shows\`.

No installer. Nothing written to Program Files. Drive letter can change (`E:` today, `F:` tomorrow) as long as media stays inside this folder.

First launch: Windows SmartScreen may say *Windows protected your PC* → **More info** → **Run anyway**.

If the window never appears, open `Logs\cuecontrol.log`.

Full operator sheet lives on the drive as `README-USB.txt`. Builder notes: [PORTABLE.md](PORTABLE.md).

**Build the zip yourself (Windows PC, no admin):**

1. Use the source folder (this repo) that already has `.venv` — or run `Run CueControl.bat` once first.
2. Double-click **`build_portable.bat`**.
3. Copy `dist\CueControl-Portable` onto the drive.

GitHub Actions: **Actions → Build portable kit → Run workflow**, then download the artifact.

### Python testers (source)

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
- **PDF multipage:** optional “Show all pages (scroll)” mode + Prev / Next page buttons
- **Groups:** `organizational` (GO starts first child, stand-by stays there) and `timeline` (children fire at offsets)
- **Multi-display:** target text / image / video / PDF / link to any connected screen
- **Edit Mode:** blue frame with tight 4–5 px margins; drag to move, drag edges to resize; geometry locks on release
- **Show hardening:** 180 ms GO debounce, Space/Esc ignore auto-repeat, live GO does not steal console focus, retrigger + cut previous Audio/Video, Auto-Fire cap (8) with loop detection, stand-by preserved after STOP ALL, Test windows do not leak, video/text/image edge-drag
- **Drag & drop:** reorder cues, drop into groups, drop media files from Explorer
- **OSC presets:** ETC EOS, GrandMA, HOG, Midas/Behringer, Allen & Heath, Yamaha
- **Save / Load:** `.ccs` show files
- **Portable kit:** `CueControl.exe` folder for USB/SSD; show files store media **relative to the kit** so drive letters can change

---

## Requirements

- Windows 10 or 11
- **Portable kit:** nothing else
- **Source / rebuild:** Python 3.10+ and packages in `requirements.txt`

Optional (feature-dependent):

- QtPdf support in your PySide6 install → PDF cues (including multipage)
- QtWebEngine → embedded Link cues (portable `.exe` opens Links in the system browser instead, to keep the kit small)
- `python-osc` → OSC cues (listed in requirements)

---

## Install (manual, Python)

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

### Preferred (show computer)

Double-click **`CueControl.exe`** in the portable kit folder.

### Preferred (source testers)

Double-click **`Run CueControl.bat`** in the project folder. If `CueControl_launch.py` is present it starts through the portable path layer (relative media + kit folders).

### Manual session

```powershell
& ".\.venv\Scripts\python.exe" ".\CueControl_launch.py"
```

### First launch checklist

1. Confirm the main window opens and the status bar shows Ready (portable kit also shows `kit <folder>`).
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

- **File → Save** / **Save As** → `.ccs` show file
- **File → Open Show** loads cues, fade duration, and display defaults
- Portable kit / `CueControl_launch.py`: media inside the kit is stored **relative** to the kit folder. Keep media in `Media\` so moving the drive does not break the show. Paths outside the kit stay absolute.

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
18. Portable: save a show with media in `Media\`, copy the kit folder to another drive letter, open the show — cues still find their files

Report failures with: **steps**, **expected vs actual**, and **full traceback** from the console (or `Logs\cuecontrol.log` on the portable kit).

---

## Distribution workflow (Alpha)

| Tier | Device | What’s on it | Who |
|------|--------|--------------|-----|
| Portable zip | SSD | `CueControl.exe` + `_internal\` + `Shows\` + `Media\` | Show computers, no Python |
| GitHub ZIP | Their PC | Source + `Run CueControl.bat` | Testers with Python + internet |
| Software-only | USB flash | App + `.venv` + `.bat` | First-look testers; media stays on the house PC |
| Basic kit | 250 GB NVMe in USB-C enclosure | Portable folder + sample 1080p + `Shows\` | Batch-cloned via Sabrent dock |
| Super-test kit | USB-C SSD | Full stack + their media | Multi-display, groups, OSC, real dry runs |

**Clone process (basic kits)**

1. Build one master NVMe (NTFS): copy `dist\CueControl-Portable` (or clone a known-good kit).
2. Put house media in `Media\` and the show in `Shows\`.
3. Smoke-test **from that drive** (not from `C:\`).
4. Offline-clone to same-size or larger targets.
5. Spot-check one drive per batch. Confirm the status bar `kit` path is on the new letter.

**Future — launch updater (not built yet)**

- Compare local `VERSION.txt` to GitHub `main`.
- If newer, download **only** `Main.py` (and `VERSION.txt`), then start.
- Offline / GitHub fail → start local copy. Never auto-update `_internal\` or `.venv`.

---

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| SmartScreen warning on `.exe` | **More info → Run anyway**. Unsigned Alpha build. |
| `.exe` does nothing | Read `Logs\cuecontrol.log`. Confirm `_internal\` is next to the exe. |
| Media missing after moving the drive | Keep files in `Media\` and re-save the show once from the kit so paths become relative |
| `No module named numpy` | You used Store Python. Use `Run CueControl.bat` or `.venv\Scripts\python.exe` |
| `python` / `git` not found | Install python.org Python with “Add to PATH” |
| `py` is not recognized | Use `python` (venv already active) or `.venv\Scripts\python.exe` |
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
- No Program Files installer (by design — portable folder instead)
- Portable `.exe` has no embedded web view (Link cues use the system browser)
- Nested groups not supported
- Fade & Stop is a delayed hard stop (does not ramp volume)
- Launch updater (GitHub `VERSION.txt` compare) not implemented yet
- Unsigned exe — SmartScreen warning on first run

---

## License

See `LICENSE`.
