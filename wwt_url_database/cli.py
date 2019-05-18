# -*- mode: python; coding: utf-8 -*-
# Copyright 2019 the .Net Foundation
# Distributed under the terms of the revised (3-clause) BSD license.

"""Entrypoint for the command-line interface.

"""
import argparse
import sys

from . import Database


def die(msg):
    print('error:', msg, file=sys.stderr)
    sys.exit(1)

def warn(msg):
    print('warning:', msg, file=sys.stderr)


# "add" subcommand

def add_getparser(parser):
    parser.add_argument(
        'url',
        metavar = 'URL',
        help = 'The URL to add to the database',
    )

def add_impl(settings):
    db = Database()
    domain, record, existed = db.get_record(settings.url)

    if existed:
        warn(f'URL {settings.url} already registered; doing nothing')
        return

    domain.insert_record(record)


# The CLI driver:

def entrypoint():
    # Set up the subcommands from globals()

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand")
    commands = set()

    for py_name, value in globals().items():
        if py_name.endswith('_getparser'):
            cmd_name = py_name[:-10].replace('_', '-')
            subparser = subparsers.add_parser(cmd_name)
            value(subparser)
            commands.add(cmd_name)

    # What did we get?

    settings = parser.parse_args()

    if settings.subcommand is None:
        print('Run me with --help for help. Allowed subcommands are:')
        print()
        for cmd in sorted(commands):
            print('   ', cmd)
        return

    py_name = settings.subcommand.replace('-', '_')

    impl = globals().get(py_name + '_impl')
    if impl is None:
        die(f'no such subcommand "{settings.subcommand}"')

    # OK to go!

    impl(settings)
