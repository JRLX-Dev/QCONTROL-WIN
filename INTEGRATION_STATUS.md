# Edge-case integration status

## Completed in repo

1. **Authoritative fixed methods** — `patches/edge_case_methods.py`
   - `repair_cue_links`
   - `cue_list_mouse_press`
   - `cue_list_drop_event` (drag-source safe)
   - `reorder_cue` (preserves fractional numbers)
   - `start_cue` (success-only active_cues, Groups as containers)
   - `_maybe_auto_fire` / `_next_cue_after`
   - `update_running_list` (Auto-Follow on finish)

2. **Integrator script** — `tools/apply_edge_case_fixes.py`
   Run once next to Main.py:
   ```
   python tools/apply_edge_case_fixes.py
   ```
   It will:
   - Add `self._drag_source_id = None` in `__init__`
   - Bind `mousePressEvent` on the cue list
   - Call `repair_cue_links()` after load and after delete
   - Replace the method bodies listed above with the hardened versions

3. **Design notes** — `EDGE_CASE_FIXES.md`

## What the fixes do

| Fix | Behaviour |
|-----|-----------|
| Drag source | Captured on mouse press, not at drop time |
| Reorder | Midpoint / shift-tail numbering; no forced 1,2,3… |
| Orphans | `repair_cue_links()` on load + delete |
| Ghost active cues | Only successful starts enter `active_cues` |
| Groups | Fire children; group itself is not kept active |
| Auto-Fire | Starts next cue immediately after this one starts |
| Auto-Follow | Starts next cue when a timed cue finishes |
| Wait 0 | Coerced to 100 ms |

## After you pull

```bash
git pull
python tools/apply_edge_case_fixes.py
# then run Main.py and exercise the test matrix
```

If the integrator reports that Main.py already contains the markers, it is a no-op.
