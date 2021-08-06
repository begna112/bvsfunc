=========
Changelog
=========

Version 2.0.0
===========

BREAKING UPDATE
- I hate LightArrowsEXE.
- Rewrite and restructuring of AudioProcessor to handle checking for file existence so that it doesn't rerun core functions if the end output files already exist.
- Most parameters changed. 
- Honestly too lazy to check the mpls functionality. Hope it works.

Version 1.2.2
===========

- Workaround for zombie temp symlinks from interrupted audioprocessor runs.

Version 1.2.1
===========

- Fixed issue with unlinking file in case where symlink wasn't used.

Version 1.2.0
===========

- Added workaround for BDMV format (symlinking m2ts to temp directory) to prevent eac3to from detecting chapters.

Version 1.1.1
===========

- mediainfo considers "general info" to be a track, always the first. 
- offset in mediainfo is a negative value, so need to be absolute value when adding to start time.

Version 1.1.0
===========

- Changed ffprobe dependency to MediaInfo for better stream handling (fonts, chapters, etc)

Version 1.0.3
===========

- change output to single list of files, instead of list of lists.

Version 1.0.2
===========

- Added hacky fix for m2ts files in regards to start_time and audio/video track delays. Just set delay to 0.

Version 1.0.0
===========

- Added out_dir, and out_file parameters. 
- Changed default out_dir to be the location of the script file (current working directory), rather than video file location.
- Added support for automatically trimming in the case where the video has a metadata delay 
  - ie: -42/-83ms delay from a streaming source, which is an industray standard not always honored
  - mediainfo detects this as a negative delay relative to video
- Add type hinting
- Updated requirements.txt for installing pip dependencies

Version 0.0.2
===========

- updated function names globally

Version 0.0.1
===========

- added scaffolding
- restructured as a module with submodules
- added DescaleAAmod
- fixed: 
    #2 - Try to concatenate two files when there is a single cut
- added:
    #3 - Passing a relative path
