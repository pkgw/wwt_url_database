====================================
URL Database File Format Description
====================================

Here we document the textual file format used to store the URL database.


Overall Database
================

The database consists of a directory containing multi-document YAML text
files. Line endings should ideally be native to the host operating system, and
files are Unicode text encoded in UTF-8.

Each text file contains information about URLs specific to one domain (or
CNAMEd set of equivalent domains). For the domain ``example.com``, the name of
the file should be ``example.com.yaml``.


Domain File
===========

Each domain file is a multi-document YAML text file. The overall textual structure
of the file looks like::

  ---
  <YAML document 1>
  ---
  <YAML document 2>
  ---
  <etc>
  ---
  <final YAML document>

The first YAML document in the domain file is a set of metadata about this
domain. The remaining YAML documents are individual records defining URLs to
be tracked. To ease tracking with version control systems, the “record”
documents are sorted in the overall file by their ``_path`` key. If you want
to add a record to a domain file, the ideal workflow is to write a new,
temporary file with the record inserted in the appropriate position, and then
use an atomic rename to replace the existing file with your updated temporary
file.

Also to ease version control, each YAML document in the domain file should be
written with its dictionary keys sorted, list items sorted when appropriate,
etc.

The minimal example domain file is::

  ---
  ---
  _path: /


Domain Metadata Document
------------------------

The domain metadata YAML document is a dictionary at its top level. It can
contain the following keys.

``cnames``
  A sorted list of aliases to the domain in question, *not* including the
  “primary” domain as defined by the filename of the domain file. The
  equivalence relation here is as in a DNS CNAME: every URL associated with
  the primary domain should function identically to a URL associated with a
  ``cname`` alias as well.

  For example, if the file ``example.com.yaml`` has the following content::

    ---
    cnames:
    - www.example.com
    ---
    _path: /

  Then the URLs ``http://example.com/`` and ``http://www.example.com/`` should
  both function equivalently.


URL Record Document
-------------------

Each URL record YAML document is a dictionary at its top level.

Path
~~~~

At a minimum, each record must contain a key called ``_path`` that provides an
absolute URL path defining the URL in question. A minimal record document
might simply consist of::

  _path: /robots.txt

The path may contain path parameters (semicolon-delimited) and query
parameters (ampersand-delimited) but not a fragment specifier
(octothorpe-delimited).

A URL record containing just a path indicates that an HTTP request to the URL
defined by combining the domain name in question and the path in question
should return an HTTP 2xx or 3xx status code. The document ``example.com.yaml``
containing::

  ---
  ---
  _path: /index.html?foo=bar

Indicates that the URL ``http://example.com/index.html?foo=bar`` should be
successfully accessible in this way.

Static Content
~~~~~~~~~~~~~~

If the record contains the key ``content-length``, that indicates that the
content returned by the server for the URL request (following redirects)
should have exactly the length specified by the record. The value in the
record is an integer number of bytes.

If the record contains the key ``content-sha256``, the indicate that the
SHA256 digest of the the content returned by the server should match the
value specified by the record. The value in the record should be a lowercase
hexadecimal expression of the digest.

Example::

  _path: /m51.txt
  content-length: 1650240
  content-sha256: fd3589aa8a72beb48939de884e3ee5324b510c145003f375c77cd4ecb1a79672

These features are aimed at declaring “static content” that should not change
over time. When adding a URL, giving the ``--static`` flag to ``wwturldb add``
causes these keys to be recorded in the database file.
