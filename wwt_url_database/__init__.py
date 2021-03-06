# -*- mode: python; coding: utf-8 -*-
# Copyright 2019-2020 the .NET Foundation
# Distributed under the terms of the revised (3-clause) BSD license.

import hashlib
from urllib import parse
import os.path
import requests
import sys
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

    categories = None
    "A set of strings representing categories this URL has been assigned."

    extras = None
    "A dict of arbitrary extra stuff from the YAML document for this path."

    path = None
    content_length = None

    content_sha256 = None
    "This is a bytes object with binary digest data."

    content_type = None

    def __init__(self, domain, doc):
        self._domain = domain
        self.path = doc.pop('_path')
        self.content_type = doc.pop('content-type')

        self.content_length = doc.pop('content-length', None)
        if self.content_length is not None:
            self.content_sha256 = bytes.fromhex(doc.pop('content-sha256'))

        self.categories = set(doc.pop('categories', ()))

        self.extras = doc

    def as_dict(self):
        d = self.extras.copy()
        d['_path'] = self.path
        d['content-type'] = self.content_type

        if self.content_length is not None:
            d['content-length'] = self.content_length
            d['content-sha256'] = self.content_sha256.hex()

        if len(self.categories):
            d['categories'] = sorted(self.categories)

        return d

    def url(self):
        """Get the full URL associated with this record.

        TODO: may be semantically limited. E.g., test both HTTP and HTTPS. And
        cnames. And methods.

        """

        if self._domain.has_https():
            scheme = 'https'
        else:
            scheme = 'http'

        netloc = self._domain._domain

        # Map the domain name if the user has requested it. The intention is
        # that this functionality should only be used when checking URLs, to
        # allow us to check prototype sites. Trying to activate this
        # functionality in broader circumstances sounds like a recipe for
        # confusion everywhere.
        netloc = self._domain._db._active_maps.get(netloc, netloc)

        path = self.path  # XXX this can includes a query string!
        query = ''  # ... but urllib doesn't escape magic characters, so we can fake it
        fragment = ''
        return parse.urlunsplit((scheme, netloc, path, query, fragment))

    def initialize(self, session, static=False):
        """Initialize the record for this URL.

        At a minimum, we use a GET request to obtain its content-type. (TODO:
        this is of course narrowminded! One day we may need to do better.)

        If *static* is true, we assert that this URL is associated with some
        kind of static data file that should not change. In order to check
        changes, we record the byte length and SHA256 digest associated with
        the URL at the moment. Subsequent checks might re-download the file
        and check that things still agree.

        """
        url = self.url()
        resp = session.get(url, stream=True, allow_redirects=False)
        if not resp.ok:
            raise Exception(f'failed to fetch {url}: HTTP status {resp.status_code}')

        if resp.is_redirect:
            # Well, this certainly isn't a hack ...
            self.content_type = f'X-{resp.status_code}-Redirect'
            return

        self.content_type = resp.headers['content-type'].split(';')[0]  # ignore `; charset=utf-8`

        if static:
            d = hashlib.sha256()
            count = 0

            for chunk in resp.iter_content(chunk_size=None):
                d.update(chunk)
                count += len(chunk)

            self.content_length = count
            self.content_sha256 = d.digest()  # this is a bytes of the binary digest data


    def check(self, session, content=True):
        """Check this URL!

        Returns True if the URL had a problem, False if it's OK.

        This function prints things to stdout.

        """
        url = self.url()
        print(url, '... ', end='')

        def err(text):
            sys.stdout.flush()
            # make it red!
            sys.stdout.buffer.write(b'\x1b[1;31merror: ' + text.encode('utf-8') + b'\x1b[0m')

        try:
            resp = session.get(url, stream=True, allow_redirects=False)
            if not resp.ok:
                err(f'HTTP {resp.status_code}')
                return True

            if resp.is_redirect:
                if 'redirect-ok' in self.categories:
                    pass  # This used to be 200 content but is now a redirect and that's OK
                else:
                    # Well, this certainly isn't a hack ...
                    redir_content_type = f'X-{resp.status_code}-Redirect'

                    if redir_content_type != self.content_type:
                        err(f'expected {self.content_type}; got {redir_content_type}')
                        return True
            else:
                content_type = resp.headers['content-type'].split(';')[0]  # ignore `; charset=utf-8`

                if 'content-type-change-ok' in self.categories:
                    pass  # e.g. for webserviceproxy.aspx, which used to return app/xml for everything
                elif content_type != self.content_type:
                    if self.content_type == 'application/javascript' and content_type == 'application/x-javascript':
                        print('(ignoring JS content-type nit) ', end='')
                    elif self.content_type == 'application/x-zip-compressed' and content_type == 'application/zip':
                        print('(ignoring Zip content-type nit) ', end='')
                    else:
                        err(f'expected content-type {self.content_type}; got {content_type}')
                        return True

                if content and self.content_length is not None:
                    d = hashlib.sha256()
                    count = 0

                    for chunk in resp.iter_content(chunk_size=None):
                        d.update(chunk)
                        count += len(chunk)

                    if count != self.content_length:
                        err(f'content length changed from {self.content_length} to {count}')
                        return True

                    if d.digest() != self.content_sha256:
                        err(f'content SHA256 changed')
                        return True

            print('ok', end='')
        finally:
            print()

        return False


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
        first = True

        with open(self._path, 'rt') as f:
            for doc in yaml.safe_load_all(f):
                if first:
                    # Hack to allow empty domain metadata.
                    first = False

                    if doc is None:
                        doc = {}

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

    def has_https(self):
        return self._metadata.get('https', False)

    def has_case_sensitive_paths(self):
        return self._metadata.get('case-sensitive-paths', True)


class Database(object):
    _dbdir = None
    _domains = None
    _domain_aliases = None
    _active_maps = None

    def __init__(self, dbdir=None):
        if dbdir is None:
            dbdir = os.path.join(os.path.dirname(__file__), 'db')

        self._dbdir = dbdir
        domains = set()
        self._domain_aliases = {}
        self._active_maps = {}

        for entry in os.listdir(self._dbdir):
            if entry.endswith('.yaml'):
                domain = entry[:-5]
                domains.add(domain)
                self._domain_aliases[domain] = domain

        self._domains = sorted(domains)  # => consistent ordering

        for domain in self.domains():
            for cname in domain._metadata.get('cnames', ()):
                self._domain_aliases[cname] = domain._domain

    def _get_domain(self, dname):
        return Domain(self, dname, os.path.join(self._dbdir, dname + '.yaml'))

    def domains(self):
        for dname in self._domains:
            yield self._get_domain(dname)

    def get_records(self, category=None, domain=None, path_prefix=None):
        """Get a set of records.

        By default, this function generates all known records. The arguments
        can filter down the selection in various ways.

        """
        if domain is None:
            domains = self.domains()
        else:
            dname = self._domain_aliases.get(domain)
            if dname is None:
                raise Exception(f'illegal domain name {domain!r}')
            domains = [self._get_domain(dname)]

        for domain in domains:
            for record in domain.records():
                if category is not None and category not in record.categories:
                    continue

                if path_prefix is not None and not record.path.startswith(path_prefix):
                    continue

                if 'deprecated' in record.categories:
                    continue

                yield record

    def normalize(self, url):
        """Normalize a URL.

        Returns (domain, normpath), where both the domain and the path are
        normalized strings. The path includes a query string if one was
        provided in the source URL. Any URL fragment is discarded.

        """
        info = parse.urlsplit(url)

        dname = self._domain_aliases.get(info.netloc)
        if dname is None:
            raise Exception(f'illegal domain name {info.netloc!r} for URL {url!r}')

        # The main WWT web server, being IIS, is case-insensitive in its URL
        # paths. We define the downcased path as the normal form. We do not
        # currently normalize the query parts of the URL, which *might* be
        # case-insensitive depending on how a given API is implemented.
        normpath = info.path
        domain = self._get_domain(dname)

        if not domain.has_case_sensitive_paths():
            normpath = normpath.lower()

        # Note that we discard the fragment (for now?).
        normpath = parse.SplitResult('', '', normpath, info.query, '')
        normpath = normpath.geturl()
        normpath = url_normalize(normpath)

        return (dname, normpath)

    def get_record(self, url):
        """Obtain a preexisting record for a given URL.

        Uses the :meth:`normalize` method. Returns ``(domain, record,
        existed)``, where ``existed`` is True if the record was already in the
        file. If False, a new Record object was created and
        ``domain.insert_record()`` needs to be called to save it to disk.

        """
        domain, normpath = self.normalize(url)
        domain = self._get_domain(domain)

        for rec in domain.records():
            if rec.path == normpath:
                return (domain, rec, True)

        rec = Record(domain, {
            '_path': normpath,
            'content-type': 'UNKNOWN',
        })
        return (domain, rec, False)

    def activate_map(self, original, alias):
        """When fetching URLs, map *original* to *alias*

        Requests for the domain *original* will be directed to the domain
        *alias* instead.

        This functionality is so that we can deploy prototype versions of the
        website on alternative domain names, and check that everything is
        working. It is important to only use this mapping functionality in
        very limited cases, otherwise things are gonna get super confusing.

        """
        self._active_maps[original] = alias
