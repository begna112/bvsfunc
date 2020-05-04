import re
from fractions import Fraction
from functools import partial
from typing import Callable, Optional, Union

from vsutil import get_w

import vapoursynth as vs

core = vs.core

def DescaleAAMod(src: vs.VideoNode,
                 w: Optional[int] = None, h: int = 720, thr: int = 10,
                 kernel: str ='bicubic',
                 b: Union[float, Fraction] = Fraction(0),
                 c: Union[float, Fraction] = Fraction(1, 2),
                 taps: int = 4,
                 expand: int = 3, inflate: int = 3,
                 showmask: bool = False) -> vs.VideoNode:
    """
    Mod of DescaleAA to use nnedi3_resample, which produces sharper results than nnedi3 rpow2.

    Original script by Frechdachs

    Original Summary:
        Downscale only lineart with an inverted kernel and interpolate
        it back to its original resolution with NNEDI3.

        Parts of higher resolution like credits are protected by a mask.

        Basic idea stolen from a script made by Daiz.

    :param src:         Source clip
    :type src:          VideoNode
    :param w:           Downscale resolution width, defaults to 1280
    :type w:            int, optional
    :param h:           Downscale resolution height, defaults to 720
    :type h:            int
    :param thr:         Threshhold used in masking, defaults to 10
    :type thr:          int
    :param kernel:      Downscaling kernel, defaults to 'bilinear'
    :type kernel:       str
    :param b:           Downscaling parameter used in fvf.Resize, defaults to 0
    :type b:            var
    :param c:           Downscaling parameter used in fvf.Resize, defaults to 1/2
    :type c:            var
    :param taps:        Downscaling parameter used in fvf.Resize, defaults to 4
    :type taps:         int
    :param expand:      Number of times to expand the difference mask, defaults to 3
    :type expand:       int
    :param inflate:     Number of times to inflate the difference mask, defaults to 3
    :type inflate:      int
    :param showmask:    Return mask created, defaults to False
    :type showmask:     bool

    :return:            The filtered video
    :rtype:             VideoNode
    """
    import fvsfunc as fvf
    from nnedi3_resample import nnedi3_resample

    if kernel.lower().startswith('de'):
        kernel = kernel[2:]

    ow = src.width
    oh = src.height

    if w is None:
        w = get_w(h, src.width/src.height)

    bits = src.format.bits_per_sample
    sample_type = src.format.sample_type

    if sample_type == vs.INTEGER:
        maxvalue = (1 << bits) - 1
        thr = thr * maxvalue // 0xFF
    else:
        maxvalue = 1
        thr /= (235 - 16)

    # Fix lineart
    src_y = core.std.ShufflePlanes(src, planes=0, colorfamily=vs.GRAY)
    deb = fvf.Resize(src_y, w, h, kernel=kernel, a1=b, a2=c, taps=taps, invks=True)
    sharp = nnedi3_resample(deb, ow, oh, invks=True,invkstaps=2, kernel="bicubic",
                            a1=0.70, a2=0, nns=4, qual=2, pscrn=4)
    edgemask = core.std.Prewitt(sharp, planes=0)

    if kernel == "bicubic" and c >= 0.7:
        edgemask = core.std.Maximum(edgemask, planes=0)
    sharp = core.resize.Point(sharp, format=src.format.id)

    # Restore true 1080p
    deb_upscale = fvf.Resize(deb, ow, oh, kernel=kernel, a1=b, a2=c, taps=taps)
    diffmask = core.std.Expr([src_y, deb_upscale], 'x y - abs')
    for _ in range(expand):
        diffmask = core.std.Maximum(diffmask, planes=0)
    for _ in range(inflate):
        diffmask = core.std.Inflate(diffmask, planes=0)

    mask = core.std.Expr([diffmask,edgemask], 'x {thr} >= 0 y ?'.format(thr=thr))
    mask = mask.std.Inflate().std.Deflate()
    out_y = core.std.MaskedMerge(src, sharp, mask, planes=0)

	#scale chroma
    new_uv = nnedi3_resample(src, ow, oh, invks=True, invkstaps=2, kernel="gauss", a1=30, nns=4, qual=2, pscrn=4 ,chromak_down="gauss",
                             chromak_down_invks=True, chromak_down_invkstaps=2, chromak_down_taps=1, chromak_down_a1=16)
    edgemask = core.std.Prewitt(new_uv, planes=0)
    edgemask_uv = core.std.Invert(edgemask, planes=[0])

    # Restore true 1080p
    deb_upscale = fvf.Resize(src, ow, oh, kernel=kernel, a1=b, a2=c, taps=taps)
    diffmask = core.std.Expr([src, deb_upscale], 'x y - abs')
    for _ in range(expand):
        diffmask = core.std.Maximum(diffmask, planes=0)
    for _ in range(inflate):
        diffmask = core.std.Inflate(diffmask, planes=0)

    mask_uv = core.std.Expr([diffmask,edgemask_uv], 'x {thr} >= 0 y ?'.format(thr=thr))
    mask_uv = mask_uv.std.Inflate().std.Deflate()
    out_uv = core.std.MaskedMerge(src, new_uv, mask_uv, planes=[1,2])

    out = core.std.ShufflePlanes([out_y, out_uv, out_uv], planes=[0,1,2], colorfamily=vs.YUV)

    if showmask:
        out = mask
    return out
