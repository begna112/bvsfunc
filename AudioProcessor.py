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
            duration = stream.duration
            framerate = stream.r_frame_rate
            framenum = math.ceil(float(duration) * Fraction(framerate))
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

def cleanup_temp_files(extracted_tracks, trimfiles, temp_outfiles):
    for track in extracted_tracks:
        if os.path.exists(track):
            os.remove(track)

    for trimfile in trimfiles:
        if os.path.exists(trimfile):
            os.remove(trimfile)

    for temp in temp_outfiles:
        if os.path.exists(temp):
            os.remove(temp)

def encode_flac(trimfiles, silent):
    if silent:
        silentstr = '--silent'
    else:
        silentstr = ''
    for file in trimfiles:
        outfile = f"{os.path.splitext(file)[0]}.flac"
        subprocess.run(["flac", file, "-8", silentstr, "--force", "-o", outfile])

def encode_aac(trimfiles, silent):
    if silent:
        silentstr = '--silent'
    else:
        silentstr = ''
    for file in trimfiles:
        outfile = f"{os.path.splitext(file)[0]}.aac"
        subprocess.run(["qaac", file, "--adts", "-V 127", "--no-delay", silentstr, "-o", outfile])

def mpls_audio(mplsdict, silent):
    cliplist = mplsdict['clip']
    infiles = []
    for clip in cliplist:
        if clip:
            infile = str(clip, 'utf-8')
            infile = os.path.normpath(infile)
            infiles.append(infile)

    out_path_prefix = os.path.splitext(str(cliplist[0], 'utf-8'))[0]
    if len(infiles) > 1:
        for infile in infiles:
            extracted_tracks, framerate, framenum = extract_tracks_as_wav(infile, silent)
        cbn = sox.Combiner()
        formats = [ 'wav' for file in extracted_tracks ]
        cbn.set_input_format(file_type=formats)
        outfile = f"{out_path_prefix}_concat.wav"
        cbn.build(extracted_tracks, outfile, 'concatenate')
        return outfile, framerate, framenum
    else:
        outfile = infiles[0]
        return outfile, None, None
    
def MPLSSource(mplsdict=None, trimlist=None, framenum=None, framerate=None, noflac=False, noaac=False, nocleanup=False, silent=True):
    infile, framerate, framenum = mpls_audio(mplsdict, silent)
    VideoSource(infile, trimlist, framenum, framerate, noflac, noaac, silent)

def VideoSource(infile=None, trimlist=None, framenum=None, framerate=None, noflac=False, noaac=False, nocleanup=False, silent=True):

    extracted_tracks, framerate_temp, framenum_temp = extract_tracks_as_wav(infile, silent)

    if framerate is None:
        framerate = framerate_temp
    else:
        framerate = Fraction(framerate)
    if framenum is None:
        framenum = framenum_temp

    if trimlist:
        trimlist = literal_eval(trimlist)
        trimfiles, temp_outfiles = trim_tracks_as_wav(extracted_tracks, trimlist, framerate, framenum)
    else:
        trimfiles = extracted_tracks

    if not noflac:
        encode_flac(trimfiles, silent)
    if not noaac:
        encode_aac(trimfiles, silent)
    
    if not nocleanup:
        cleanup_temp_files(extracted_tracks,trimfiles, temp_outfiles)

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
                        help="The file which contains audio to trim",
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