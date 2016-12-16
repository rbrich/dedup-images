#!/usr/bin/env python3

from distutils.core import setup
from Cython.Build import cythonize

setup(
    name='dedup-images',
    version='1.0.0',
    description='Find duplicate images',
    author='Radek Brich',
    author_email='radek.brich@devl.cz',
    url='https://github.com/rbrich/dedup-images',
    keywords=['duplicate images', 'perceptual hash', 'pHash'],
    ext_modules=cythonize('pyx/phash.pyx'),
    packages=['dedupimages'],
    scripts=['dedup-images.py'],
    requires=['Cython']
)
