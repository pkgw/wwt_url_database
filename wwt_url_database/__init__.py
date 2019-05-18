# -*- mode: python; coding: utf-8 -*-
# Copyright 2019 the .Net Foundation
# Distributed under the terms of the revised (3-clause) BSD license.

from urllib import parse
import os.path
import tempfile
from url_normalize import url_normalize
import warnings
import yaml

from ._version import version_info, __version__  # noqa

__all__ = '''
__version__
version_info
Database
Domain
Record
'''.split()


class Record(object):
    _domain = None
    extras = None
    path = None

    def __init__(self, domain, doc):
        self._domain = domain
        self.path = doc.pop('path')
        self.extras = doc

    def as_dict(self):
        d = self.extras.copy()
        d['path'] = self.path
        return d


class Domain(object):
    _db = None
    _path = None

    def __init__(self, db, path):
        self._db = db
        self._path = path

    def records(self):
        try:
            with open(self._path, 'rt') as f:
                for doc in yaml.safe_load_all(f):
                    assert doc is not None
                    yield Record(self, doc)
        except FileNotFoundError:
            pass  # i.e., yield no results

    def _rewrite(self, records):
        "Assumes that records are correctly formatted and sorted."

        with tempfile.NamedTemporaryFile(mode='wt', dir=self._db._dbdir, delete=False) as f:
            yaml.dump_all(
                (rec.as_dict() for rec in records),
                stream = f,
                explicit_start = True,
                sort_keys = True,
            )

        os.rename(f.name, self._path)

    def insert_record(self, rec):
        """Rewrite the multi-YAML file including the new record *rec*.

        If there's an existing record associated with the same path, it will
        be replaced.

        """
        by_path = {irec.path: irec for irec in self.records()}
        by_path[rec.path] = rec
        self._rewrite(by_path[p] for p in sorted(by_path.keys()))


class Database(object):
    _dbdir = None
    _domains = None

    def __init__(self, dbdir=None):
        if dbdir is None:
            dbdir = os.path.join(os.path.dirname(__file__), 'db')

        self._dbdir = dbdir
        self._domains = set()

        for entry in os.listdir(self._dbdir):
            if entry.endswith('.yaml'):
                domain = entry[:-5]
                self._domains.add(domain)

    def domains(self):
        for dname in self._domains:
            yield Domain(self, os.path.join(self._dbdir, dname + '.yaml'))

    def all_records(self):
        for domain in self.domains():
            for record in domain.records():
                yield record

    def normalize(self, url):
        """Normalize a URL.

        Returns (domain, normpath), where both the domain and the path have
        been normalized. The path includes a query string. Any URL fragment is
        discarded.

        """
        info = parse.urlsplit(url)

        # TODO: normalize: e.g. www.worldwidetelescope.org => worldwidetelescope.org
        domain = info.netloc

        # Note that we discard the fragment (for now?).
        normpath = parse.SplitResult('', '', info.path, info.query, '')
        normpath = normpath.geturl()
        normpath = url_normalize(normpath)

        return (domain, normpath)

    def get_record(self, url):
        """Obtain a preexisting record for a given URL.

        Uses the :meth:`normalize` method. If a matching record is found,
        return ``(domain, record)``, otherwise returns ``(domain, None)``.

        """
        domain, normpath = self.normalize(url)
        domain = Domain(self, os.path.join(self._dbdir, domain + '.yaml'))

        for rec in domain.records():
            if rec.path == normpath:
                return (domain, rec)

        return (domain, None)
