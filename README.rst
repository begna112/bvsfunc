=======
bvsfunc
=======

bvsfunc, a collection of VapourSynth functions and wrappers written and/or "borrowed" by begna112. This README is stolen from LightArrowsEXE.

Full information on how every function/wrapper works and specific dependencies can be found in the `documentation <https://bvsfunc.readthedocs.io/en/latest/>`_.

How to install
--------------

Install with `python3 setup.py install`.

Functions can be loaded into VS...

.. code-block:: python

    import bvsfunc as bvs

    bvs.util.AudioProcessor
    bvs.mods.DescaleAAMod
    ...

or accessed via the commandline...

.. code-block:: python

    $ > AudioProcessor -h

