# -*- mode: python; coding: utf-8 -*-
# Copyright 2019 the .Net Foundation
# Distributed under the terms of the revised (3-clause) BSD license.

"""Entrypoint for the command-line interface.

"""
import argparse


def die(msg):
    import sys
    print('error:', msg, file=sys.stderr)
    sys.exit(1)


def get_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand")

    check = subparsers.add_parser('check')

    return parser


def cli_check(settings):
    print('Hello world!')


def entrypoint():
    import sys

    parser = get_parser()
    settings = parser.parse_args()

    if settings.subcommand is None:
        print('Run me with --help for help')
        return

    impl = globals().get('cli_' + settings.subcommand.replace('-', '_'))
    if impl is None:
        die(f'no such subcommand "{impl}"')

    impl(settings)
