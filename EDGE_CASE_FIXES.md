# Edge-case fixes applied 2026-08-15

## Critical
1. Drag source is captured at drag start (`_drag_source_id`) instead of trusting `currentItem()` at drop time.
2. Reorder no longer forces integer 1,2,3… numbering. Moved cue gets a number between its new neighbours (or max+1 at end).
3. `repair_cue_links()` runs after load and after delete: clears stale `parent_id`, prunes dead IDs from `group_children`.
4. `start_cue` only registers in `active_cues` on successful start; early returns on missing media no longer leave ghost entries.
5. Group cues are not kept as long-lived active entries; children are started and the group itself is treated as a container.

## Medium
6. Auto-Fire: when a cue with Auto-Fire starts, the next cue is also started immediately.
7. Auto-Follow: when a timed cue finishes, the next cue is selected and started.
8. Wait with duration 0 is coerced to 100 ms and a status message is shown.
9. Edit Mode / Test Mode interaction tightened so windows are not destroyed while still needed.
10. Clearer status messages on missing media files.

## Still intentional / later
- Nested groups remain unsupported.
- Full timeline (pre-wait per child inside a group) is future work.
