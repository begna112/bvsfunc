#!/usr/bin/env python

import subprocess
import argparse
import os
import shutil
import datetime
from fractions import Fraction


def _extract_tracks_as_wav(infile, silent):
    try:
        from ffprobe import FFProbe
    except ModuleNotFoundError:
        raise ModuleNotFoundError("_extract_tracks_as_wav: missing dependency 'ffprobe'")
    try:
        import math
    except ModuleNotFoundError:
        raise

    out_path_prefix = os.path.splitext(infile)[0]
    infile_ext = os.path.splitext(infile)[1]
    metadata = FFProbe(infile)
    extracted_tracks = []

    for stream in metadata.streams:
        if stream.is_video():
            try:
                dur = metadata.metadata['Duration']
                date_time = datetime.datetime.strptime(dur, "%H:%M:%S.%f")
                a_timedelta = date_time - datetime.datetime(1900, 1, 1)
                seconds = a_timedelta.total_seconds()
                duration = seconds
            except:
                try:
                    duration = stream.duration
                except AttributeError:
                    duration = None
            try:
                framerate = stream.r_frame_rate
            except AttributeError:
                framerate = None
            try:
                framenum = math.ceil(float(duration) * Fraction(framerate))
            except:
                framenum = None
        if stream.is_audio():
            if infile_ext is not ".wav":
                index = str(int(stream.index) + 1)
                index_f = str(int(stream.index))
                extract_file = f"{out_path_prefix}_{index}.wav"
                if silent:
                    with open(os.devnull, "w") as f:
                        if stream.codec_name != "aac":
                            subprocess.call(["eac3to", infile, "-log=NUL", f"{index}:", extract_file], stdout=f ,creationflags=subprocess.CREATE_NO_WINDOW)
                        else:
                            subprocess.call(["ffmpeg", "-i", infile, "-map", f"0:{index_f}", extract_file], stdout=f ,creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    if stream.codec_name != "aac":
                        subprocess.call(["eac3to", infile, "-log=NUL", f"{index}:", extract_file])
                    else:
                        subprocess.call(["ffmpeg", "-i", infile, "-map", f"0:{index_f}", extract_file])
                extracted_tracks.append(extract_file)
            else:
                extracted_tracks.append(infile)
                framenum = None
                framerate = None

    return extracted_tracks, framerate, framenum

def _sox_trim(infile, outfile, trim, framenum, SPF, silent):
    try:
        import sox
    except ModuleNotFoundError:
        raise ModuleNotFoundError('AudioProcessor.VideoSource: missing sox dependency for trimming.')
    infile = os.path.normpath(infile)
    tfm = sox.Transformer()
    if silent:
        tfm.set_globals(verbosity=0)
    startframe,endframe = trim[0],trim[1]
    if startframe is None:
        startframe = 0
    elif startframe < 0:
        startframe = framenum + startframe
    if endframe is None:
        endframe = framenum
    elif endframe < 0:
        endframe = framenum + endframe
    start_time = SPF * float(startframe)
    end_time = SPF * float(endframe)
    tfm.trim(start_time, end_time)
    tfm.build(infile,outfile)

def _trim_tracks_as_wav(extracted_tracks, trimlist, framerate, framenum, silent):
    try:
        import sox
    except ModuleNotFoundError:
        raise ModuleNotFoundError('AudioProcessor.VideoSource: missing sox dependency for trimming.')
    framerate = Fraction(framerate)
    SPF = float(1.0 / framerate)
    trimfiles = []
    temp_outfiles = []
    for track in extracted_tracks:
        out_path_prefix = os.path.splitext(track)[0]
        outfile = f"{out_path_prefix}_cut.wav"
        trimfiles.append(outfile)
        if type(trimlist[0]) is list and len(trimlist) > 1:
            for index, trim in enumerate(trimlist, start=1):
                temp_outfile = f"{out_path_prefix}_temp{index}.wav"
                temp_outfiles.append(temp_outfile)
                _sox_trim(track, temp_outfile, trim, framenum, SPF, silent)
            cbn = sox.Combiner()
            if silent:
                cbn.set_globals(verbosity=0)
            formats = [ 'wav' for file in temp_outfiles ]
            cbn.set_input_format(file_type=formats)
            cbn.build(temp_outfiles, outfile, 'concatenate')
        elif type(trimlist[0]) is int or type(trimlist[0]) is type(None):
            _sox_trim(track, outfile, trimlist, framenum, SPF, silent)
    return trimfiles, temp_outfiles

def _cleanup_temp_files(files):
    if type(files) is not list:
        f = os.path.normpath(files)
        if os.path.exists(f):
            os.remove(f)
    else:
        for f in files:
            f = os.path.normpath(f)
            if os.path.exists(f):
                os.remove(f)

def _encode_flac(trimfiles, silent):
    dep = shutil.which("flac")
    if dep is None:
        raise SystemExit('flac encoder was not found in your PATH.')
    outfiles = []
    for file in trimfiles:
        outfile = f"{os.path.splitext(file)[0]}.flac"
        if silent:
            subprocess.run(["flac", file, "-8", '--silent', "--force", "-o", outfile],creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(["flac", file, "-8", "--force", "-o", outfile])
        outfiles.append(outfile)
    return outfiles
        

def _encode_aac(trimfiles, silent):
    dep = shutil.which("qaac")
    if dep is None:
        raise SystemExit('qaac encoder was not found in your PATH.')
    outfiles = []
    for file in trimfiles:
        outfile = f"{os.path.splitext(file)[0]}.aac"
        if silent:
            subprocess.run(["qaac", file, "--adts", "-V 127", "--no-delay", '--silent', "-o", outfile],creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(["qaac", file, "--adts", "-V 127", "--no-delay", "-o", outfile])
        outfiles.append(outfile)
    return outfiles    

def _mpls_audio(mplsdict, nocleanup, silent):
    cliplist = mplsdict['clip']
    infiles = []
    for clip in cliplist:
        if clip:
            infile = str(clip, 'utf-8')
            infile = os.path.normpath(infile)
            infiles.append(infile)

    out_path_prefix = os.path.splitext(str(cliplist[0], 'utf-8'))[0]
    outfiles = []
    concat_files = []
    if len(infiles) > 1:
        try:
            import sox
        except ModuleNotFoundError:
            raise ModuleNotFoundError('AudioProcessor.VideoSource: missing sox dependency for concatonating.')
        for infile in infiles:
            extracted_tracks, framerate, framenum = _extract_tracks_as_wav(infile, silent)
            concat_files.append(extracted_tracks)
        for i in range(len(concat_files[0])):
            combine_files = [ concat_files[j][i] for j in range(len(concat_files)) ]
            cbn = sox.Combiner()
            if silent:
                cbn.set_globals(verbosity=0)
            formats = [ 'wav' for file in extracted_tracks ]
            cbn.set_input_format(file_type=formats)
            outfile = f"{out_path_prefix}_{i+2}_concat.wav"
            outfiles.append(outfile)
            cbn.build(combine_files, outfile, 'concatenate')
        if not nocleanup:
            for item in concat_files:
                _cleanup_temp_files(item)
        return outfiles, framerate, framenum
    else:
        outfile = infiles
        return outfile, None, None

def mpls_source(mplsdict, trimlist=None, framenum=None, framerate=None, noflac=False, noaac=False, nocleanup=False, silent=True):
    """
    Processes audio from a given mpls file. Functions include trimming losslessly and encoding to flac and/or aac. 
    Will concatonate the aligned audio streams when mpls defines multiple video files.

    Notes on trimlist:
        Supports: single, multiple, empty ended, and negative trims.

        Format: [[inclusive,exclusive],...].

        Examples: 
            trimlist = [100,500]

            trimlist = [None,500]

            trimlist = [100,None]

            trimlist = [[None,500],[1000,2000],[100,None]]

            trimlist = [-1000,None]

            trimlist = [None,-24]

        Note: Trims are absolute references to the source, not relative to each other.

    :param mplsdict: The full filepath to the mpls file containing videos to process.
    :type mplsdict: [type]
    :param trimlist: A list or a list of lists of trims following python slice syntax, defaults to None.
    :type trimlist: list, optional
    :param framenum: Total number of frames in your clip. Overrides automatic detection.
        Some sources will not include duration information in their metadata. 
        In these cases, you will need to specify it. 
        Can be retrieved with core.num_frames().
        Defaults to None.
    :type framenum: int, optional
    :param framerate: Framerate of your source. Overrides automatic detection. 
        Some sources will not include framerate information in their metadata. 
        In these cases, you will need to specify it.
        Can be retrieved with core.fps().
        Defaults to None.
    :type framerate: Fraction, optional
    :param noflac: Disable FLAC encoding, defaults to False
    :type noflac: bool, optional
    :param noaac: Disable AAC encoding, defaults to False
    :type noaac: bool, optional
    :param nocleanup: Disable cleaning up temp wav files, defaults to False
    :type nocleanup: bool, optional
    :param silent: Silence eac3to, flac, and qaac, defaults to True
    :type silent: bool, optional
    :return: A list of filepaths to all of the final processed files.
    :rtype: list
    """
    infile, framerate, framenum = _mpls_audio(mplsdict, nocleanup, silent)

    outfiles = video_source(infile, trimlist, framenum, framerate, noflac, noaac, silent)
    
    return outfiles

def video_source(infile, trimlist=None, framenum=None, framerate=None, noflac=False, noaac=False, nocleanup=False, silent=True):
    """
    Processes audio from a given video file. Functions include trimming losslessly and encoding to flac and/or aac.

    Notes on trimlist:
        Supports: single, multiple, empty ended, and negative trims.

        Format: [[inclusive,exclusive],...].

        Examples: 
            trimlist = [100,500]

            trimlist = [None,500]

            trimlist = [100,None]

            trimlist = [[None,500],[1000,2000],[100,None]]

            trimlist = [-1000,None]

            trimlist = [None,-24]

        Note: Trims are absolute references to the source, not relative to each other.

    :param infile: The full filepath to the video file containing audio to process.
    :type infile: string
    :param trimlist: A list or a list of lists of trims following python slice syntax, defaults to None.
    :type trimlist: list, optional
    :param framenum: Total number of frames in your clip. Overrides automatic detection.
        Some sources will not include duration information in their metadata. 
        In these cases, you will need to specify it. 
        Can be retrieved with core.num_frames().
        Defaults to None.
    :type framenum: int, optional
    :param framerate: Framerate of your source. Overrides automatic detection. 
        Some sources will not include framerate information in their metadata. 
        In these cases, you will need to specify it.
        Can be retrieved with core.fps().
        Defaults to None.
    :type framerate: Fraction, optional
    :param noflac: Disable FLAC encoding, defaults to False
    :type noflac: bool, optional
    :param noaac: Disable AAC encoding, defaults to False
    :type noaac: bool, optional
    :param nocleanup: Disable cleaning up temp wav files, defaults to False
    :type nocleanup: bool, optional
    :param silent: Silence eac3to, flac, and qaac, defaults to True
    :type silent: bool, optional
    :raises SystemExit: Missing source metadata. Must supply your own.
    :return: A list of filepaths to all of the final processed files.
    :rtype: list
    """

    infile = os.path.abspath(infile)

    if type(infile) is list:
        extracted_tracks, framerate_temp, framenum_temp = _extract_tracks_as_wav(infile[0], silent)
    else:
        extracted_tracks, framerate_temp, framenum_temp = _extract_tracks_as_wav(infile, silent)

    if framenum is None and framenum_temp is None:
        raise SystemExit('Source does not contain duration information. Specify it with the "framenum" argument.')
    elif framenum is None:
        framenum = framenum_temp

    if framerate is None and framerate_temp is None:
        raise SystemExit('Source does not contain framerate information. Specify it with the "framerate" argument.')
    elif framerate is None:
        framerate = framerate_temp
    else:
        framerate = Fraction(framerate)

    if trimlist is not None:
        if type(trimlist[0]) is list and len(trimlist) == 1:
            trimlist = trimlist[0]
        trimfiles, temp_outfiles = _trim_tracks_as_wav(extracted_tracks, trimlist, framerate, framenum, silent)
    else:
        trimfiles = extracted_tracks
        temp_outfiles = None

    outfiles = []
    if not noflac:
        outfiles.append(_encode_flac(trimfiles, silent))
    if not noaac:
        outfiles.append(_encode_aac(trimfiles, silent))
    
    if not nocleanup:
        _cleanup_temp_files(extracted_tracks)
        _cleanup_temp_files(trimfiles)
        if temp_outfiles is not None:
            _cleanup_temp_files(temp_outfiles)
    
    return outfiles
    

def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-I", "--infile",
                        default = None,
                        help="The file which contains audio to process. Can be a video or audio file. Only one source type can be spcified, infile or mplsdict.",
                        action="store")
    parser.add_argument("-M", "--mplsdict",
                        default = None,
                        help="A dictionary constructed from an mpls, such as from VapourSynth-ReadMpls. Overrides the infile argument.",
                        action="store")
    parser.add_argument("-T", "--trimlist",
                        default = None,
                        help="List  or list of lists of trims",
                        action="store")
    parser.add_argument("-N", "--framenum",
                        default = None,
                        help="Total number of frames in the file",
                        action="store",
                        type=int)
    parser.add_argument("-F", "--framerate",
                        default = "24000/1001",
                        help="Frame rate (ie. 24000/1001)",
                        action="store")
    parser.add_argument("--noflac",
                        action="store_true", default=False,
                        help="Disable FLAC encoding (default: %(default)s)")
    parser.add_argument("--noaac",
                        action="store_true", default=False,
                        help="Disable AAC encoding (default: %(default)s)")
    parser.add_argument("--nocleanup",
                        action="store_true", default=False,
                        help="Disable cleaning up temp wav files (default: %(default)s)")
    parser.add_argument("--silent",
                        action="store_true", default=False,
                        help="Silence eac3to, flac, and qaac (default: %(default)s)")
    args = parser.parse_args()
    infile = args.infile
    mplsdict = args.mplsdict
    trimlist = args.trimlist
    framenum = args.framenum
    framerate = args.framerate
    noflac = args.noflac
    noaac = args.noaac
    silent = args.silent
    if infile and mplsdict:
        raise SystemExit('You must spcify only one input type, infile or mplsdict.')
    elif infile:
        ap_video_source(infile, trimlist, framenum, framerate, noflac, noaac, silent)
    elif mplsdict:
        ap_mpls_source(mplsdict, trimlist, framenum, framerate, noflac, noaac, silent)

if __name__ == "__main__":
    _main()