# CueControl Windows – Changelog

## 2026-08-15 – Group + Wait cues

### Added
- **Wait** cue type – timed pause that respects duration and works with Auto-Follow / Auto-Fire chains.
- **Group** cue type – container for other cues.
  - Two modes:
    - `simultaneous` (default) – fires all children at once (QLab "Timeline / Start all" style)
    - `sequence` – fires the first child and advances into the group
  - Children are stored with `parent_id` and appear indented in the cue list.
  - Simple management UI in Properties when a Group is selected.

### Notes
This is the foundation for the fuller timeline-group system. The first version is deliberately simple so it stays reliable for volunteers and small productions.
