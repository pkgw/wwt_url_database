# -*- mode: python; coding: utf-8 -*-
# Copyright 2019 the .Net Foundation
# Distributed under the terms of the revised (3-clause) BSD license.

"""Entrypoint for the command-line interface.

"""
import argparse
import requests
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
        '--static',
        action = 'store_true',
        help = 'Indicate that this URL should return static, unchanging content',
    )
    parser.add_argument(
        '-c', '--category',
        action = 'append',
        metavar = 'CATEGORY',
        help = 'Mark the URL as belonging to the specified CATEGORY',
    )
    parser.add_argument(
        'url',
        metavar = 'URL',
        help = 'The URL to add to the database',
    )

def add_impl(settings):
    url = settings.url

    if not url.startswith('http'):
        warn('prepending "http://" since I don\'t see a scheme and the URL parser is picky')
        url = 'http://' + url

    db = Database()
    domain, record, existed = db.get_record(url)

    if existed:
        warn(f'URL {settings.url} already registered; doing nothing')
        return

    session = requests.session()
    record.initialize(session, static=settings.static)

    for cat in settings.category:
        record.categories.add(cat)

    domain.insert_record(record)


# "check" subcommand

def check_getparser(parser):
    parser.add_argument(
        'domain',
        nargs = '?',
        metavar = 'DOMAIN',
        help = 'A specific domain to check',
    )
    parser.add_argument(
        '--map',
        action = 'append',
        metavar = 'ORIGINAL=ALIAS',
        help = 'Rewrite requests for the domain ORIGINAL to point to ALIAS instead',
    )

def check_impl(settings):
    session = requests.session()
    db = Database()
    errors = 0

    for mapspec in settings.map:
        pieces = mapspec.split('=', 1)
        if len(pieces) != 2:
            die(f'invalid "--map" specification {mapspec!r}: should contain one equals sign')

        original, alias = pieces

        if original not in db._domains:
            die(f'invalid "--map" specification {mapspec!r}: original domain name {original} not recognized')

        db.activate_map(original, alias)

    for rec in db.get_records(domain=settings.domain):
        if rec.check(session):
            errors += 1

    if errors > 0:
        die(f'found {errors} broken URLs')


# "dump_urls" subcommand

def dump_urls_getparser(parser):
    pass

def dump_urls_impl(settings):
    db = Database()

    for rec in db.get_records():
        print(rec.url())


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
