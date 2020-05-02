=======
bvsfunc
=======

This is the documentation of **bvsfunc**.

.. toctree::
   :maxdepth: 4
   :caption: Contents:

Functions
---------
.. autosummary::

   bvsfunc.mods.DescaleAAMod
   bvsfunc.util.ap_video_source
   bvsfunc.util.ap_mpls_source

============
bvsfunc.mods
============

.. automodule:: bvsfunc.mods.descaleaamod
   :noindex:
   :members:
   :undoc-members:
   :show-inheritance:

============
bvsfunc.util
============

AudioProcessor Dependencies
---------------------------

* `pysox <https://github.com/rabitt/pysox>`_
* `ffprobe-python <https://github.com/gbstack/ffprobe-python>`_

AudioProcessor PATH Executable Dependencies
-------------------------------------------
* `ffmpeg/ffprobe <https://www.ffmpeg.org/>`_
* `sox <http://sox.sourceforge.net/>`_
* `eac3to <https://forum.doom9.org/showthread.php?t=125966>`_
* `qaac <https://sites.google.com/site/qaacpage/>`_

AudioProcessor Examples
-----------------------
.. code-block:: python

    import bvsfunc as bvs

    # m2ts example
    filepath = r"E:\0000.m2ts"
    src = SourceFilter(filepath)
    src = src[:500] + src[1000:2000]
    process = False
    if process:
        audiotrims = [[None,500],[1000,2000]]
        files = bvs.util.ap_video_source(infile=filepath, trimlist=autotrims, noflac=True, silent=True)

    # mpls example
    filepath = r"E:\BD_VIDEO"
    mpls = core.mpls.Read(filepath, 2)
    src = core.std.Splice([core.lsmas.LWLibavSource(mpls['clip'][i]) for i in range(mpls['count'])])
    src = src[:500] + src[1000:2000]
    process = False
    if process:
        audiotrims = [[None,500],[1000,2000]]
        files = bvs.util.ap_mpls_source(mplsdict=mpls, trimlist=audiotrims, noflac=True, silent=False)

AudioProcessor Tips
-----------------------
* For a truly silent experience with eac3to, delete the `success.wav` and `error.wav` files in your install directory

.. automodule:: bvsfunc.util.AudioProcessor
   :noindex:
   :members:
   :undoc-members:
   :show-inheritance:
