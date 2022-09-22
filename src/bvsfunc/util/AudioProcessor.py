#!/usr/bin/env python

import subprocess
import argparse
import os
import shutil
# import datetime
from fractions import Fraction
from typing import *
from pathlib import Path,PurePath

# This is due to how mediainfo reports framrates. others may need to be added
FRAMERATE_MAP = {
    '23.976': '24000/1001',
    '29.97': '30000/1001',
    '25.000': '25/1'
}

########################
#  metadata functions  #
########################

def _get_metainfo(in_file, trims_framerate, frames_total):
    try:
        from pymediainfo import MediaInfo
    except ModuleNotFoundError:
        raise ModuleNotFoundError("_extract_metainfo: missing dependency'mediainfo'")
    media_info = MediaInfo.parse(in_file)
    extracted_metainfo = {
        "framerate": None,
        "framenum": None,
        "audio_tracks": []
    }
    stream_id = 0
    for track in media_info.tracks:
        if track.track_type == "Video":
            if track.framerate_den is None or track.framerate_num is None:
                extracted_metainfo["framenum"] = int(track.frame_count) if frames_total is None else frames_total
                try:
                    extracted_metainfo['framerate'] = FRAMERATE_MAP[track.frame_rate] if trims_framerate is None else trims_framerate
                except KeyError:
                    raise KeyError("Your source video is not one of the supported framrates. Either supply a custom framerate with trims_framerate or, if it is a common framerate, submit an issue.")
            else:
                framerate_num = int(track.framerate_num)
                framerate_den = int(track.framerate_den)
                extracted_metainfo['framerate'] = f"{framerate_num}/{framerate_den}" if trims_framerate is None else trims_framerate
                extracted_metainfo["framenum"] = int(track.frame_count) if frames_total is None else frames_total
            extracted_metainfo["duration"] = track.duration
            stream_id += 1
        elif track.track_type == "Audio":
            audio_track = {"stream_id": stream_id}
            if track.delay_relative_to_video is not None:
                audio_track["offset_time"] = float(int(track.delay_relative_to_video) / 1000)
            else:
                audio_track["offset_time"] = float(0)
            audio_track['format'] = track.format
            extracted_metainfo["audio_tracks"].append(audio_track)
            stream_id += 1
        else:
            stream_id += 1
            pass
    return extracted_metainfo

def _build_extract_data(in_file, out_prefix, trims_framerate, frames_total):
    extracted_metainfo = _get_metainfo(in_file, trims_framerate, frames_total)
    for audio_track in extracted_metainfo["audio_tracks"]:
        codecs = ['wav','flac','aac']
        for ext in codecs:
            audio_track[ext] = f"{str(out_prefix)}_{audio_track['stream_id']}_cut.{ext}"
        audio_track['raw_wav'] = f"{str(out_prefix)}_{audio_track['stream_id']}.wav"

    return extracted_metainfo

##############################
#  extract & trim functions  #
##############################

def _create_symlink_for_sane_ripping_fuck_eac3to(in_file):
    file_purepath = PurePath(in_file)
    dir = file_purepath.parts[-2]
    if dir == "STREAM":
        import tempfile
        temp = tempfile.gettempdir()
        file_path = Path(fr"{temp}\{file_purepath.parts[-1]}")
        # remove existing links in case a previous cut was interrupted. 
        if (Path.is_symlink(file_path)):
            file_path.unlink(missing_ok=False)
        file_path.symlink_to(file_purepath)
        return file_path.absolute() 
    else:
        return Path(in_file).absolute()

def _extract_tracks_as_wav(in_file, meta_info, overwrite, silent):
    for track in meta_info['audio_tracks']:
        extract_file = Path(track['raw_wav'])
        if Path(in_file).suffix != ".wav":
            if not Path(extract_file).exists() or overwrite:
                temp_file = _create_symlink_for_sane_ripping_fuck_eac3to(in_file)
                eac3to_cmds = ["eac3to", f"{temp_file}", "-log=NUL", f"{track['stream_id']}:", f"{extract_file}"]
                ffmpeg_cmds = ["ffmpeg", "-i", f"{temp_file}", "-map", f"0:{track['stream_id'] - 1}", f"{extract_file}"]
                subp_args = {}
                subp_args |= {'args': eac3to_cmds} if track['format'] != "AAC" else {'args': ffmpeg_cmds}
                subp_args |= {'stdout':subprocess.DEVNULL, 'creationflags':subprocess.CREATE_NO_WINDOW, 'shell':True} if silent else {'shell':True}
                subprocess.call(**subp_args)
                if (Path(temp_file).is_symlink()):
                    Path(temp_file).unlink(missing_ok=False)
            elif not silent:
                print(f"AudioProcessor: wav file exists and overwrite not specified.")
                print(f"AudioProcessor: {extract_file}")
        else:
            print(f"AudioProcessor: input is already a wav file. no extraction needed")
            shutil.copy(Path(in_file),extract_file)
            print(f"AudioProcessor: {extract_file}")
    return 

def _sox_trim(in_file, outfile, trim, framenum, offset_time, SPF, silent):
    try:
        import sox
    except ModuleNotFoundError:
        raise ModuleNotFoundError('AudioProcessor.VideoSource: missing sox dependency for trimming.')
    in_file = os.path.normpath(in_file)
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
    start_time = SPF * float(startframe + round(abs(offset_time) / SPF))
    end_time = SPF * float(endframe)
    tfm.trim(start_time, end_time)
    tfm.build(in_file,outfile)

def _trim_tracks_as_wav(meta_info, trim_list, trims_framerate, overwrite, silent):
    try:
        import sox
    except ModuleNotFoundError:
        raise ModuleNotFoundError('AudioProcessor.VideoSource: missing sox dependency for trimming.')
    framerate = Fraction(trims_framerate if meta_info['framerate'] is None else meta_info['framerate'])
    SPF = float(1.0 / framerate)
    for track in meta_info['audio_tracks']:
        temp_outfiles = []
        raw_wav = track['raw_wav']
        out_path_prefix = os.path.splitext(raw_wav)[0]
        outfile = track['wav']
        if not Path(outfile).exists() or overwrite:
            if type(trim_list[0]) is list and len(trim_list) > 1:
                for index, trim in enumerate(trim_list, start=1):
                    temp_outfile = f"{out_path_prefix}_temp{index}.wav"
                    temp_outfiles.append(temp_outfile)
                    _sox_trim(raw_wav, temp_outfile, trim, meta_info['framenum'], track['offset_time'], SPF, silent)
                cbn = sox.Combiner()
                if silent:
                    cbn.set_globals(verbosity=0)
                formats = [ 'wav' for file in temp_outfiles ]
                cbn.set_input_format(file_type=formats)
                cbn.build(temp_outfiles, outfile, 'concatenate')
            elif type(trim_list[0]) is int or type(trim_list[0]) is type(None):
                _sox_trim(raw_wav, outfile, trim_list, meta_info['framenum'], track['offset_time'], SPF, silent)
        elif not silent:
            print(f"AudioProcessor: trimmed wav file exists and overwrite not specified.")
            print(f"AudioProcessor: {outfile}")
    _cleanup_temp_files(temp_outfiles)
    return 

########################
#  encoding functions  #
########################

def _encode_flac(meta_info, overwrite, silent):
    dep = shutil.which("flac")
    if dep is None:
        raise SystemExit('flac encoder was not found in your PATH.')
    for track in meta_info['audio_tracks']:
        wav = track['wav']
        outfile = track['flac']
        if not Path(outfile).exists() or overwrite:
            flac_cmds = ["flac", wav, "-8", "--force", "-o", outfile]
            if silent:
                flac_cmds.insert(3,'--silent')
            subp_args = {'args': flac_cmds}
            subp_args |= {'stdout':subprocess.DEVNULL, 'creationflags':subprocess.CREATE_NO_WINDOW, 'shell':True} if silent else {'shell':True}
            subprocess.call(**subp_args)
        elif not silent:
            print(f"AudioProcessor: flac file exists and overwrite not specified.")
            print(f"AudioProcessor: {outfile}")
    return

def _encode_aac(meta_info, overwrite, silent):
    dep = shutil.which("qaac")
    if dep is None:
        raise SystemExit('qaac encoder was not found in your PATH.')
    for track in meta_info['audio_tracks']:
        wav = track['wav']
        outfile = track['aac']
        if not Path(outfile).exists() or overwrite:
            aac_cmds = ["qaac", wav, "--adts", "-V 127", "--no-delay", "-o", outfile]
            if silent:
                aac_cmds.insert(5,'--silent')
            subp_args = {'args': aac_cmds}
            subp_args |= {'stdout':subprocess.DEVNULL, 'creationflags':subprocess.CREATE_NO_WINDOW, 'shell':True} if silent else {'shell':True}
            subprocess.call(**subp_args)
        elif not silent:
            print(f"AudioProcessor: aac file exists and overwrite not specified.")
            print(f"AudioProcessor: {outfile}")
    return    

#######################
#  utility functions  #
#######################

def _cleanup_temp_files(files):
    if type(files) is not list:
        f = Path(files)
        if f.exists():
            Path.unlink(f)
    else:
        for f in files:
            f = Path(f)
            if f.exists():
                Path.unlink(f)

def _get_out_prefix(in_file, out_file, out_dir):
    if out_file is None and out_dir is None:
        out_dir = Path.cwd()
        out_file = PurePath(PurePath(in_file).name).stem
    elif out_file is not None and out_dir is None:
        out_dir = Path.cwd()
    elif out_file is None and out_dir is not None:
        out_dir = Path(out_dir)
        out_file = PurePath(PurePath(in_file).name).stem
    else:
        out_dir = Path(out_dir)
    out_prefix = PurePath.joinpath(out_dir, out_file)
    return Path(out_prefix)

def _write_files(meta_info, flac, aac, wav, overwrite, silent):
    missing_files_found = False
    if overwrite:
        return missing_files_found
    for track in meta_info['audio_tracks']:
        if flac:
            if not Path(track['flac']).exists():
                missing_files_found = True
                if not silent: print(f"{Path(track['flac'])} does not exist")
            elif not silent:
                print(f"{Path(track['flac'])} exists")
        if aac:
            if not Path(track['aac']).exists():
                missing_files_found = True
                if not silent: print(f"{Path(track['aac'])} does not exist")
            elif not silent:
                print(f"{Path(track['aac'])} exists")
        if wav:
            if not Path(track['wav']).exists():
                missing_files_found = True
                if not silent: print(f"{Path(track['wav'])} does not exist")
            elif not silent:
                print(f"{Path(track['wav'])} exists")
    if not missing_files_found:
        return missing_files_found
    else:
        return missing_files_found

#########################
#  core input handling  #
#########################

def _mpls_audio(mpls_dict, wav, overwrite, silent):
    clip_list = mpls_dict['clip']
    in_files = []
    for clip in clip_list:
        if clip:
            in_file = str(clip, 'utf-8')
            in_file = os.path.normpath(in_file)
            in_files.append(in_file)

    out_path_prefix = os.path.splitext(str(clip_list[0], 'utf-8'))[0]
    outfiles = []
    if len(in_files) > 1:
        try:
            import sox
        except ModuleNotFoundError:
            raise ModuleNotFoundError('AudioProcessor.VideoSource: missing sox dependency for concatonating.')
        for in_file in in_files:
            concat_files = []
            extracted_tracks = video_source(in_file, flac=False, aac=False, wav=True, overwrite=overwrite, silent=silent)
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
            if not wav:
                for item in concat_files:
                    _cleanup_temp_files(item)
        return outfiles
    else:
        outfile = in_files
        return outfile

def mpls_source(
                mpls_dict:str, 
                trim_list:Union[List[Optional[int]], List[List[Optional[int]]]]=None, 
                out_file:Optional[str]=None, 
                out_dir:Optional[str]=None, 
                trims_framerate:Optional[Fraction]=None, 
                flac:bool=True, 
                aac:bool=True, 
                wav:bool=False,
                overwrite:bool=False,
                silent:bool=True
                ):
    """
    Processes audio from a given mpls file. Functions include trimming losslessly and encoding to flac and/or aac. 
    Will concatonate the aligned audio streams when mpls defines multiple video files.

    Notes on trim_list:
        Supports: single, multiple, empty ended, and negative trims.

        Format: [[inclusive,exclusive],...].

        Examples: 
            trim_list = [100,500]

            trim_list = [None,500]

            trim_list = [100,None]

            trim_list = [[None,500],[1000,2000],[100,None]]

            trim_list = [-1000,None]

            trim_list = [None,-24]

        Note: Trims are absolute references to the source, not relative to each other.

    :param mpls_dict: The full filepath to the mpls file containing videos to process.
    :type mpls_dict: [type]
    :param trim_list: A list or a list of lists of trims following python slice syntax, defaults to None.
    :type trim_list: list, optional
    :param trims_framerate: Framerate of your source. Overrides automatic detection. 
        If your source framerate is not the same as your output framerate,
        such as with interlaced sources, you
        Can be retrieved with core.fps().
        Defaults to None.
    :type out_file: string
    :param out_dir: A string path for the file output directory. Defaults the script file location. Requires the string format to be: r"path"
    :type out_dir: string
    :type trims_framerate: Fraction, optional
    :param out_file: A string prefix to name the output files with.
    :param frames_total: The total number of frames in the clip before trimming. 
        Useful for VFR, where this *must* be the total before any trimming.
        Otherwise, probably just leave it blank.
    :type frames_total: int, optional
    :param flac: Enable FLAC encoding, defaults to True.
    :type flac: bool, optional
    :param aac: Enable AAC encoding, defaults to True.
    :type aac: bool, optional
    :param wav: Retain output of trimmed wav files, defaults to False.
    :type wav: bool, optional
    :param overwrite: Overwrite existing files (including wav) and forces re-extract and re-encode, deaults to False.
    :type overwrite: bool, optional
    :param silent: Silence eac3to, ffmpeg, flac, and qaac, defaults to True.
    :type silent: bool, optional
    :return: A list of filepaths to all of the final processed files.
    :rtype: list
    """
    in_file = _mpls_audio(mpls_dict, wav, overwrite, silent)

    outfiles = video_source(in_file, trim_list, out_file, out_dir, trims_framerate, flac, aac, wav, overwrite, silent)
    
    return outfiles

def video_source(
                in_file:str, 
                trim_list:Union[List[Optional[int]], List[List[Optional[int]]]]=None, 
                out_file:Optional[str]=None, 
                out_dir:Optional[str]=None, 
                trims_framerate:Optional[Fraction]=None,
                frames_total:Optional[int]=None,
                flac:bool=True, 
                aac:bool=True, 
                wav:bool=False,
                overwrite:bool=False,
                silent:bool=True
                ):
    """
    Processes audio from a given video file. Functions include trimming losslessly and encoding to flac and/or aac.

    Notes on trim_list:
        Supports: single, multiple, empty ended, and negative trims.

        Format: [[inclusive,exclusive],...].

        Examples: 
            trim_list = [100,500]

            trim_list = [None,500]

            trim_list = [100,None]

            trim_list = [[None,500],[1000,2000],[100,None]]

            trim_list = [-1000,None]

            trim_list = [None,-24]

        Note: Trims are absolute references to the source, not relative to each other.

    :param in_file: The full filepath to the video file containing audio to process.
    :type in_file: string
    :param trim_list: A list or a list of lists of trims following python slice syntax, defaults to None.
    :type trim_list: list, optional
    :param trims_framerate: Framerate of your source. Overrides automatic detection. 
        If your source framerate is not the same as your output framerate,
        such as with interlaced sources, you
        Can be retrieved with core.fps().
        Defaults to None.
    :type out_file: string
    :param out_dir: A string path for the file output directory. Defaults the script file location. Requires the string format to be: r"path"
    :type out_dir: string
    :type trims_framerate: Fraction, optional
    :param out_file: A string prefix to name the output files with.
    :param frames_total: The total number of frames in the clip before trimming. 
        Useful for VFR, where this *must* be the total before any trimming.
        Otherwise, probably just leave it blank.
    :type frames_total: int, optional
    :param flac: Enable FLAC encoding, defaults to True.
    :type flac: bool, optional
    :param aac: Enable AAC encoding, defaults to True.
    :type aac: bool, optional
    :param wav: Retain output of trimmed wav files, defaults to False.
    :type wav: bool, optional
    :param overwrite: Overwrite existing files (including wav) and forces re-extract and re-encode, deaults to False.
    :type overwrite: bool, optional
    :param silent: Silence eac3to, ffmpeg, flac, and qaac, defaults to True.
    :type silent: bool, optional
    :raises SystemExit: Missing dependencies.
    :return: A list of filepaths to all of the final processed files.
    :rtype: list
    """

    in_file = str(os.path.abspath(in_file))

    if type(in_file) is list:
        in_file = in_file[0]

    out_prefix = _get_out_prefix(in_file, out_file, out_dir)

    meta_info = _build_extract_data(in_file, out_prefix, trims_framerate, frames_total)

    if trim_list is None or trim_list == [None,None]:
        for track in meta_info["audio_tracks"]:
            for x in track:
                if isinstance(track[x], str): 
                    track[x] = track[x].replace('_cut','')

    check_write = _write_files(meta_info, flac, aac, wav, overwrite, silent)
    if check_write:
        _extract_tracks_as_wav(in_file, meta_info, overwrite, silent)

        if trim_list is not None:
            if type(trim_list[0]) is list and len(trim_list) == 1:
                trim_list = trim_list[0]
            _trim_tracks_as_wav(meta_info, trim_list, trims_framerate, overwrite, silent)

    elif not silent: 
        print("AudioProcessor: All files exist and overwrite not specified.")
    outfiles = []
    if flac:
        _encode_flac(meta_info, overwrite, silent)
        outfiles.extend([track['flac'] for track in meta_info['audio_tracks']])
    if aac:
        _encode_aac(meta_info, overwrite, silent)
        outfiles.extend([track['aac'] for track in meta_info['audio_tracks']])
    if not wav:
        _cleanup_temp_files([track['wav'] for track in meta_info['audio_tracks']])
    else:
        outfiles.extend([track['wav'] for track in meta_info['audio_tracks']])
    
    # always cleanup raw wav
    _cleanup_temp_files([track['raw_wav'] for track in meta_info['audio_tracks']])

    return outfiles
    

def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-I", "--in_file",
                        default = None,
                        help="The file which contains audio to process. Can be a video or audio file. Only one source type can be spcified, in_file or mpls_dict.",
                        action="store")
    parser.add_argument("-M", "--mpls_dict",
                        default = None,
                        help="A dictionary constructed from an mpls, such as from VapourSynth-ReadMpls. Overrides the in_file argument.",
                        action="store")
    parser.add_argument("-T", "--trim_list",
                        default = None,
                        help="List or list of lists of trims",
                        action="store")
    parser.add_argument("--out_file",
                        default = "filename",
                        help="A string prefix to name the output files with.",
                        action="store")
    parser.add_argument("--out_dir",
                        default = r"C:\out",
                        help="A string path for the file output directory. Defaults the script file location.",
                        action="store")
    parser.add_argument("-F", "--trims_framerate",
                        default = "24000/1001",
                        help="Frame rate (ie. 24000/1001)",
                        action="store")
    parser.add_argument("--flac",
                        action="store_true", default=False,
                        help="Enable FLAC encoding (default: %(default)s)")
    parser.add_argument("--aac",
                        action="store_true", default=False,
                        help="Enable AAC encoding (default: %(default)s)")
    parser.add_argument("--wav",
                        action="store_true", default=False,
                        help="Retain output of trimmed wav files (default: %(default)s)")
    parser.add_argument("--overwrite",
                        action="store_true", default=False,
                        help="Overwrite existing files (including wav) and forces re-extract and re-encode. (default: %(default)s)")
    parser.add_argument("--silent",
                        action="store_true", default=False,
                        help="Silence eac3to, ffmpeg, flac, and qaac. (default: %(default)s)")
    args = parser.parse_args()
    in_file = args.in_file
    mpls_dict = args.mpls_dict
    trim_list = args.trim_list
    out_file = args.out_file
    out_dir = args.out_dir
    trims_framerate = args.trims_framerate
    flac = args.flac
    aac = args.aac
    wav = args.wav
    overwrite = args.overwrite
    silent = args.silent
    if in_file and mpls_dict:
        raise SystemExit('You must spcify only one input type, in_file or mpls_dict.')
    elif in_file:
        video_source(in_file, trim_list, out_file, out_dir, trims_framerate, flac, aac, wav, overwrite, silent)
    elif mpls_dict:
        mpls_source(mpls_dict, trim_list, out_file, out_dir, trims_framerate, flac, aac, wav, overwrite, silent)

if __name__ == "__main__":
    _main()