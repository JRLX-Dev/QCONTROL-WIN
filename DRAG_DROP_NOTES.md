# Drag & Drop Design Notes – CueControl Windows

## Goals
1. Reorder cues by dragging (like QLab)
2. Drag a cue onto a Group to make it a child of that group
3. Drag files from Windows Explorer onto the cue list to create cues

## Supported external file types
- Audio: .mp3 .wav .ogg .flac .m4a
- Video: .mp4 .mov .mkv .avi .webm .m4v
- Image: .png .jpg .jpeg .bmp .gif .webp .tif .tiff
- PDF: .pdf

## Behaviour
### Internal reorder
- Drag a cue up/down in the list → numbers are automatically adjusted so the visual order matches the cue numbers.
- Dropping between two cues renumbers the moved cue (and shifts others if needed).

### Drop onto Group
- If the drop target is a Group cue, the dragged cue becomes a child (`parent_id` set, added to `group_children`).
- Children appear indented under their parent.
- Dropping a Group onto itself or creating cycles is blocked.

### External file drop
- Accepts `text/uri-list` / local file URLs.
- Creates the appropriate cue type and selects it.
- Multiple files can be dropped at once; each becomes its own cue.

## Implementation notes
- `QListWidget` is set to accept both internal moves and external drops.
- Custom `dropEvent` distinguishes between:
  - Reorder (drop indicator between items)
  - Parenting (drop indicator on a Group row)
  - External files (MIME has URLs)
- After any structural change the list is refreshed and the moved/created cue is selected.

## Future polish
- Multi-select drag
- Visual “folder” expand/collapse for groups
- Pre-wait / post-wait on children for true timeline groups
