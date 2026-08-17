# Organizational + Timeline Groups

## Modes

| Mode | Behavior |
|------|----------|
| **organizational** | GO starts the **first** child only. Further progress is manual GO or another automation cue (Crossfade, etc.). |
| **timeline** | GO starts a clock. Children fire at their **timeline_offset_ms** from group start. Ballet / music-synced OSC. |

## Apply

From the project root (venv active):

```powershell
python tools\apply_groups_timeline.py
```

This creates `Main.py.bak` and patches `Main.py` in place.

## Test

1. Add **Group** → Properties → Group mode = `organizational`
2. Drag 2–3 Audio/Text cues onto the group
3. GO the group → only first child starts
4. Set mode = `timeline`
5. Select each child → set **Timeline offset** (e.g. 0, 3000, 6000 ms)
6. GO the group → children fire on the clock
7. STOP ALL cancels pending timeline fires
8. Save / reload show → offsets and mode persist

## Notes

- Nesting groups is not supported
- Legacy `simultaneous` / `sequence` values load as `organizational`
- Also fixes `create_audio_cue_from_path` (was missing `_add_and_select`) and adds `get_audio_duration_ms` if absent
