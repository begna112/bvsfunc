# AudioProcessor

AudioProcessor extracts audio sources from a video, audio, or blu-ray mpls source and then optionall trims it and encodes it to flac and aac formats. It can be run either from the command line or from VapourSynth. 

## Dependencies 
* [pysox](https://github.com/rabitt/pysox)
* [ffprobe-python](https://github.com/gbstack/ffprobe-python)

### PATH Executable Dependencies
* [ffmpeg/ffprobe](https://www.ffmpeg.org/)
* [sox](http://sox.sourceforge.net/)
* [eac3to](https://forum.doom9.org/showthread.php?t=125966)
* [qaac](https://sites.google.com/site/qaacpage/)

## Arguments
* `-I, --infile` : `[string]` : The full filepath which contains audio to process. Can be a video or audio file. Only one source type can be spcified, infile or mplsdict. (default infile)
* `-M, --mplsdict` : `[dict]` : A dictionary constructed from an mpls, such as from VapourSynth-ReadMpls. Only one source type can be spcified, infile or mplsdict. (default infile)
* `-T, --trimlist` : `[string]` : A string of a list or a list of a list of trims following python slice syntax. 
    * Format: `"[[inclusive,exclusive],...]"`
    * Single trim: `-T "[100,500]"`
    * Empty ended trims: `-T "[None,500]"`, `-T "[100,None]"`
    * Multiple trims: `-T "[[None,500],[1000,2000],[100,None]]"`
        * Trims are absolute references to the source (infile or mplsdict). 
        * The above would result in an audio file like this:
            * `0 --> 500 + 1000 --> 2000 + 100 --> end of file`
    * Negative trims: 
        * Start frame : `-T "[-1000,500]"` : begins 1000 frames from the end of the file and has a duration of 500 frames.
        * End frame : `-T "[100,-24]"` : begins at frame 100 and continues until 24 frames from the end of the file.
* `-N, --framenum` : `[int] ` : Total number of frames in your clip. Overrides automatic detection. Some sources will not include duration information in their metadata. In these cases, you will need to spcify it. 
* `-F, --framerate` : `[string]` : Framerate of your source. one sources will not include framerate information in their metadata. In these cases, you will need to spcify it. 
    * Format : `"24000/1001"`
* `--noflac` : `[boolean]` : Disable FLAC encoding. Default is False.
* `--noaac` : `[boolean]` : Disable AAC encoding. Default is False.
* `--nocleanup` : `[boolean]` : Disable cleaning up temp wav files. Default is False.
* `--silent` : `[boolean]` : Silence eac3to, flac, and qaac. Default is False from command line and True from VapourSynth.

## Commandline

```cmd
# Video Source
py -3 AudioProcessor.py -I "C:\path\to\video.m2ts" -T "[0,764]" --silent

# Audio source example
# framerate, framenum are required if you want to trim
# audio sources are first extracted to wav before processing
py -3 AudioProcessor.py -I "C:\path\to\video.aac" -T "[0,764]" -N 30000 -F "24000/1001" --silent

```

## VapourSynth

```python
import AudioProcessor as ap

# m2ts example
# Source must be a full path
filepath = r"E:\0000.m2ts"
src = SourceFilter(filepath)
src = src[:500] + src[1000:2000]
audiotrims = "[[None,500],[1000,2000]]"
ap.VideoSource(infile=filepath, trimlist=autotrims, noflac=True, silent=True)

# mpls example
# Source must be a full path
filepath = r"E:\BD_VIDEO"
mpls = core.mpls.Read(filepath, 2)
src = core.std.Splice([core.lsmas.LWLibavSource(mpls['clip'][i]) for i in range(mpls['count'])])
src = src[:500] + src[1000:2000]
audiotrims = "[[None,500],[1000,2000]]"
ap.MPLSSource(mplsdict=mpls, trimlist=audiotrims, noflac=True, silent=False)
```

## Tips
* For a truly silent experience with eac3to, delete the `success.wav` and `error.wav` files in your install directory
* To only process audio one time from VapourSynth, comment out the AudioProcessor line until you're ready, then either run the script through vspipe or a GUI like VSEdit.