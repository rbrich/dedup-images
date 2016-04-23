ImageDups
=========

Find duplicate or similar images. The images are compared
not only by their bits, but also by their visual content.
For example, this can recognise different scans of same original
image. Or images manipulated by resize, crop, rotation,
blur, noise or color changes.

Imagedups is build on perceptual hash algorithms from [pHash
library](http://phash.org/docs/design.html). Default algorithm
is *MH*, which is very accurate, other options are *DCT* and *Radial*,
both faster and reasonably accurate.


Usage
-----

Hash `~/Pictures` directory, recursively traversing into subdirectories (-r),
using fast compare to detect modified files (-F) and present each group
of similar images in GUI window (-x):

    imagedups.py -r ~/Pictures -F -x

All options are documented in program help:

    imagedups.py --help


GUI
---

The program contains simple GUI to show identified groups of similar images.
Use `-x` option to switch on the GUI.

The GUI requires few common Python modules:

* tkinter (python3-tk)
* PIL + ImageTk (python3-pil, python3-pil.imagetk)

I also suggest to change the image viewer to your favorite light-weight
alternative. I use `feh`.

The default `xdg-open` should open some viewer
on any system, but it's usually full-blown photo viewer, which is not good
for one-shot image viewing.

Just edit the config file at `~/.config/imagedups.conf`.


Installation
------------

Build:

    ./setup.py build

Build requires:

* python3-dev
* cython3
* libphash-dev

Install:

    sudo ./setup.py install

Inplace build (to run without installation):

    ./setup.py build_ext --inplace


pHash Build
-----------

Download source from [phash.org](http://phash.org/download/).

Build requires:

* cimg-dev

Build:

    ./configure --disable-video-hash --disable-audio-hash --enable-pthread --enable-openmp
    make
    sudo make install
    sudo ldconfig


Programming Documentation
-------------------------

Build:

    cd doc
    make html

Build requires:

    python3-sphinx

Read in default browser:

    make read
