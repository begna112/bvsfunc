#!/usr/bin/env python

import subprocess
import argparse
import os
from ast import literal_eval
from fractions import Fraction
from ffprobe import FFProbe
import sox
import math


def extract_tracks_as_wav(infile, silent):
    out_path_prefix = os.path.splitext(infile)[0]
    metadata = FFProbe(infile)
    extracted_tracks = []

    for stream in metadata.streams:
        if stream.is_video():
            try:
                duration = stream.duration
            except:
                duration = None
            try:
                framerate = stream.r_frame_rate
            except:
                framerate = None
            try:
                framenum = math.ceil(float(duration) * Fraction(framerate))
            except:
                framenum = None
        if stream.is_audio():
            index = str(int(stream.index) + 1)
            # not used currently
            # codec = stream.codec_name 
            # channels = stream.channels
            extract_file = f"{out_path_prefix}_{index}.wav"
            if silent:
                with open(os.devnull, "w") as f:
                    subprocess.call(["eac3to", infile, "-log=NUL", f"{index}:", extract_file], stdout=f)
            else:
                subprocess.call(["eac3to", infile, "-log=NUL", f"{index}:", extract_file])
            extracted_tracks.append(extract_file)

    return extracted_tracks, framerate, framenum

def sox_trim(infile, outfile, trim, framenum, SPF):
    infile = os.path.normpath(infile)
    tfm = sox.Transformer()
    startframe,endframe = trim[0],trim[1]
    if startframe is None:
        startframe = 0
    elif startframe < 0:
        startframe = framenum + startframe
    if endframe is None:
        endframe = framenum
    elif endframe < 0:
        endframe = framenum + endframe
    else:
        endframe -= 1
    start_time = SPF * float(startframe)
    end_time = SPF * float(endframe)
    tfm.trim(start_time, end_time)
    tfm.build(infile,outfile)

def trim_tracks_as_wav(extracted_tracks, trimlist, framerate, framenum):
    framerate = Fraction(framerate)
    SPF = float(1.0 / framerate)
    trimfiles = []
    temp_outfiles = []
    for track in extracted_tracks:
        out_path_prefix = os.path.splitext(track)[0]
        outfile = f"{out_path_prefix}_cut.wav"
        trimfiles.append(outfile)
        if type(trimlist[0]) is list:
            for index, trim in enumerate(trimlist, start=1):
                temp_outfile = f"{out_path_prefix}_temp{index}.wav"
                temp_outfiles.append(temp_outfile)
                sox_trim(track, temp_outfile, trim, framenum, SPF)
            cbn = sox.Combiner()
            formats = [ 'wav' for file in temp_outfiles ]
            cbn.set_input_format(file_type=formats)
            cbn.build(temp_outfiles, outfile, 'concatenate')
        elif type(trimlist[0]) is int or type(trimlist[0]) is type(None):
            sox_trim(track, outfile, trimlist, framenum, SPF)
    return trimfiles, temp_outfiles

def cleanup_temp_files(files):
    if type(files) is not list:
        f = os.path.normpath(files)
        if os.path.exists(f):
            os.remove(f)
    else:
        for f in files:
            f = os.path.normpath(f)
            if os.path.exists(f):
                os.remove(f)

def encode_flac(trimfiles, silent):
    for file in trimfiles:
        outfile = f"{os.path.splitext(file)[0]}.flac"
        if silent:
            subprocess.run(["flac", file, "-8", '--silent', "--force", "-o", outfile])
        else:
            subprocess.run(["flac", file, "-8", "--force", "-o", outfile])
        

def encode_aac(trimfiles, silent):
    for file in trimfiles:
        outfile = f"{os.path.splitext(file)[0]}.aac"
        if silent:
            subprocess.run(["qaac", file, "--adts", "-V 127", "--no-delay", '--silent', "-o", outfile])
        else:
            subprocess.run(["qaac", file, "--adts", "-V 127", "--no-delay", "-o", outfile])
        

def mpls_audio(mplsdict, nocleanup, silent):
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
        for infile in infiles:
            extracted_tracks, framerate, framenum = extract_tracks_as_wav(infile, silent)
            concat_files.append(extracted_tracks)
        for i in range(len(concat_files[0])):
            combine_files = [ concat_files[j][i] for j in range(len(concat_files)) ]
            cbn = sox.Combiner()
            formats = [ 'wav' for file in extracted_tracks ]
            cbn.set_input_format(file_type=formats)
            outfile = f"{out_path_prefix}_{i+2}_concat.wav"
            outfiles.append(outfile)
            cbn.build(combine_files, outfile, 'concatenate')
        if not nocleanup:
            for item in concat_files:
                cleanup_temp_files(item)
        return outfiles, framerate, framenum
    else:
        outfile = infiles
        return outfile, None, None

def AudioSource(infile, trimlist=None, framenum=None, framerate=None, noflac=False, noaac=False, nocleanup=False, silent=True):
    if trimlist is not None:
        trimlist = literal_eval(trimlist)
        trimfiles, temp_outfiles = trim_tracks_as_wav(infile, trimlist, framerate, framenum)
    else:
        trimfiles = infile

    if not noflac:
        encode_flac(trimfiles, silent)
    if not noaac:
        encode_aac(trimfiles, silent)
    
    if not nocleanup:
        cleanup_temp_files(infile)
        cleanup_temp_files(trimfiles)
        cleanup_temp_files(temp_outfiles)

    if not silent:
        print(f"\nDone trimming audio.")


def MPLSSource(mplsdict=None, trimlist=None, framenum=None, framerate=None, noflac=False, noaac=False, nocleanup=False, silent=True):
    infile, framerate, framenum = mpls_audio(mplsdict, nocleanup, silent)
    if len(infile) > 1:
        AudioSource(infile, trimlist, framenum, framerate, noflac, noaac, silent)
    else:
        VideoSource(infile, trimlist, framenum, framerate, noflac, noaac, silent)

def VideoSource(infile=None, trimlist=None, framenum=None, framerate=None, noflac=False, noaac=False, nocleanup=False, silent=True):
    if type(infile) is list:
        extracted_tracks, framerate_temp, framenum_temp = extract_tracks_as_wav(infile[0], silent)
    else:
        extracted_tracks, framerate_temp, framenum_temp = extract_tracks_as_wav(infile, silent)

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
        trimlist = literal_eval(trimlist)
        trimfiles, temp_outfiles = trim_tracks_as_wav(extracted_tracks, trimlist, framerate, framenum)
    else:
        trimfiles = extracted_tracks

    if not noflac:
        encode_flac(trimfiles, silent)
    if not noaac:
        encode_aac(trimfiles, silent)
    
    if not nocleanup:
        cleanup_temp_files(extracted_tracks)
        cleanup_temp_files(trimfiles)
        cleanup_temp_files(temp_outfiles)

    if not silent:
        print(f"\nDone trimming audio.")

def main():
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
        VideoSource(infile, trimlist, framenum, framerate, noflac, noaac, silent)
    elif mplsdict:
        MPLSSource(mplsdict, trimlist, framenum, framerate, noflac, noaac, silent)

if __name__ == "__main__":
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
                        help="String of list of list of trims",
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
    main()