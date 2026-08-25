# Portable USB / SSD kit

CueControl as a **folder you copy to a drive**. No installer, no admin, no Python on the target PC.

`Main.py` is not replaced. `CueControl_launch.py` wraps it so shows and media stay relative to the kit when the drive letter changes.

## What you copy

```
CueControl-Portable\
  CueControl.exe          double-click this
  Start CueControl.bat    same thing, if you prefer a .bat
  _internal\              Qt / Python runtime (required)
  Shows\                  .ccs show files
  Media\Audio\
  Media\Video\
  Media\Images\
  Media\PDF\
  Logs\
  VERSION.txt
  CUECONTROL_PORTABLE.txt keep this file (marks the kit root)
  README-USB.txt
```

## Build on a Windows PC (no admin)

1. Use the Alpha source folder that already has `.venv` (run `Run CueControl.bat` once if needed).
2. Double-click **`build_portable.bat`**.
3. Wait several minutes. When it finishes, Explorer opens `dist\CueControl-Portable`.
4. Copy that folder onto an **NTFS SSD**.

GitHub Actions can also build it: **Actions → Build portable kit → Run workflow**. Download the zip from the run’s artifacts.

## Why not a single .exe / installer

| Approach | Why we don’t |
|----------|----------------|
| One-file PyInstaller | Extracts to `%TEMP%` every launch — slow and fragile on USB |
| Inno / MSI installer | Needs admin; writes to Program Files; wrong for a house-PC you don’t own |
| Portable **onedir** folder | Runs in place, writes only next to itself |

## SmartScreen

The exe is unsigned, so Windows may warn **More info → Run anyway**. That is expected for Alpha.

## Link cues

The portable build **does not** ship QtWebEngine (Chromium, ~150 MB). Link cues open in the system browser. Python source still has embedded web if QtWebEngine is installed.

## Do not

- Do not put `CueControl.exe` in the public git tree (too large; rebuild instead).
- Do not re-run old `patch_*.py` scripts on current `Main.py`.
- Do not format the show drive FAT32 if you have files over 4 GB.
