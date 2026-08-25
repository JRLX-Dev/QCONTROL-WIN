CueControl Windows — portable kit (USB / SSD)
=============================================

What this is
  A QLab-style cue desk that runs from this folder. No installer,
  no admin rights, no Python. Plug the drive into a Windows 10/11
  PC and double-click CueControl.exe.

First launch
  Windows SmartScreen may say "Windows protected your PC".
  Click More info  →  Run anyway.

  If nothing appears, look in Logs\cuecontrol.log.

Folders
  CueControl.exe     the app (keep _internal\ next to it)
  Shows\             save your .ccs show files here
  Media\Audio\       wav / mp3 / flac / ogg / m4a
  Media\Video\       mp4 / mov / mkv / webm
  Media\Images\      png / jpg / bmp / webp
  Media\PDF\         pdf
  Logs\              crash / start log
  _internal\         Qt runtime — do not delete or move

Drive letter can change
  Shows saved from this kit store media as paths relative to
  this folder. E: today and F: tomorrow still play.

  Keep media ON THIS DRIVE, inside Media\. Files on C:\ will
  break when you move the kit to another PC.

Copying the kit
  Copy the WHOLE CueControl-Portable folder.
  SSD (USB 3 / USB-C) is strongly preferred. Cheap flash drives
  stutter on video. Format NTFS (not FAT32 — 4 GB file limit).

  Do not copy CueControl.exe by itself. It needs _internal\.

Booth checklist
  1. Plug in the SSD, wait for Windows to assign a letter.
  2. Open CueControl.exe.
  3. File → Open Show…  (starts in Shows\).
  4. Confirm the status bar shows  kit <this folder>.
  5. GO one audio cue and one overlay before doors.

Alpha
  Test the full stack before a live service. This is Alpha.

  Link cues open in the system browser in this portable build
  (embedded Chromium is left out to keep the kit small).
