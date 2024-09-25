# -*- coding: utf-8 -*-

def get_version():
    """Return automaid version number.

    v<MAJOR>.<MINOR>.<PATCH>-<PRE_RELEASE>

    Versioning goes as vX.X.X-Y, where Y designates a pre-release, and is one of
    [0-9], then [A-Z], after which point a patch version (at the very least)
    must be incremented because git tags are case insensitive.

    """

    return 'v4.0.0-0'

def get_url():
    return 'https://github.com/earthscopeoceans/automaid [doi: 10.5281/zenodo.5057096]'
