#! /usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
# Copyright 2019 the .Net Foundation
# Distributed under the terms of the revised (3-clause) BSD license.

from __future__ import absolute_import, division, print_function

from os.path import join as pjoin
from setuptools import setup

from setupbase import find_packages, get_version

name = 'wwt_url_database'
version = get_version(pjoin(name, '_version.py'))

with open('README.rst') as f:
    LONG_DESCRIPTION = f.read()

setup_args = dict(
    name             = name,
    description      = 'A utility database of URLs exposed by the AAS WorldWide Telescope.',
    long_description = LONG_DESCRIPTION,
    version          = version,
    packages         = find_packages(),
    author           = 'Peter K. G. Williams',
    author_email     = 'peter@newton.cx',
    url              = 'https://github.com/WorldWideTelescope/wwt_url_database',
    license          = 'BSD',
    platforms        = "Linux, Mac OS X, Windows",
    keywords         = ['Science'],
    classifiers      = [
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    include_package_data = True,
    install_requires = [
        'six',
    ],
    extras_require = {
        'test': [
            'pytest',
            'pytest-cov',
        ],
        'docs': [
            'sphinx>=1.6',
            'sphinx-automodapi',
            'numpydoc',
            'sphinx_rtd_theme',
        ],
    },
    entry_points = {
    },
)

if __name__ == '__main__':
    setup(**setup_args)
