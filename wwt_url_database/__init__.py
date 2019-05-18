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
    _domain = None
    _metadata = None
    _path = None

    def __init__(self, db, domain, path):
        self._db = db
        self._domain = domain
        self._path = path

        # The first YAML doc is the metadata header.
        for doc in self._all_yaml_docs():
            self._metadata = doc
            break

    def _all_yaml_docs(self):
        with open(self._path, 'rt') as f:
            for doc in yaml.safe_load_all(f):
                assert doc is not None
                yield doc

    def records(self):
        first = True

        for doc in self._all_yaml_docs():
            if first:
                first = False
            else:
                yield Record(self, doc)

    def _rewrite(self, records):
        """Assumes that records are correctly formatted and sorted.

        What does "correctly formatted" mean? Example: that the URL path is
        properly normalized.

        """
        def all_dicts():
            yield self._metadata

            for rec in records:
                yield rec.as_dict()

        tf = tempfile.NamedTemporaryFile(
            mode = 'wt',
            dir = self._db._dbdir,
            prefix = self._domain,
            delete = False,
        )

        with tf as f:
            yaml.dump_all(all_dicts(),
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
    _domain_aliases = None

    def __init__(self, dbdir=None):
        if dbdir is None:
            dbdir = os.path.join(os.path.dirname(__file__), 'db')

        self._dbdir = dbdir
        self._domains = set()
        self._domain_aliases = {}

        for entry in os.listdir(self._dbdir):
            if entry.endswith('.yaml'):
                domain = entry[:-5]
                self._domains.add(domain)
                self._domain_aliases[domain] = domain

        for domain in self.domains():
            for cname in domain._metadata['cnames']:
                self._domain_aliases[cname] = domain._domain

    def domains(self):
        for dname in self._domains:
            yield Domain(self, dname, os.path.join(self._dbdir, dname + '.yaml'))

    def all_records(self):
        for domain in self.domains():
            for record in domain.records():
                yield record

    def normalize(self, url):
        """Normalize a URL.

        Returns (domain, normpath), where both the domain and the path are
        normalized strings. The path includes a query string if one was
        provided in the source URL. Any URL fragment is discarded.

        """
        info = parse.urlsplit(url)

        domain = self._domain_aliases.get(info.netloc)
        if domain is None:
            raise Exception(f'illegal domain name {info.netloc!r} for URL {url!r}')

        # Note that we discard the fragment (for now?).
        normpath = parse.SplitResult('', '', info.path, info.query, '')
        normpath = normpath.geturl()
        normpath = url_normalize(normpath)

        return (domain, normpath)

    def get_record(self, url):
        """Obtain a preexisting record for a given URL.

        Uses the :meth:`normalize` method. Returns ``(domain, record,
        existed)``, where ``existed`` is True if the record was already in the
        file. If False, a new Record object was created and
        ``domain.insert_record()`` needs to be called to save it to disk.

        """
        domain, normpath = self.normalize(url)
        domain = Domain(self, domain, os.path.join(self._dbdir, domain + '.yaml'))

        for rec in domain.records():
            if rec.path == normpath:
                return (domain, rec, True)

        rec = Record(domain, dict(path=normpath))
        return (domain, rec, False)
