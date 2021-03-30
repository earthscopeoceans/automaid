# Part of automaid -- a Python package to process MERMAID files
# pymaid environment (Python v2.7)
#
# Developer: Joel D. Simon (JDS)
# Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
# Last modified by JDS: 30-Mar-2021
# Last tested: Python 2.7.15, Darwin-18.7.0-x86_64-i386-64bit

def get_version():
    """Return automaid version number.

    Versioning goes as vX.X.X-Y, where Y designates a pre-release,
    and is one of [0-9], then [A-Z], and finally [a-z].

    """

    return 'v3.4.0-8'

def get_url():
    return 'https://github.com/earthscopeoceans/automaid'
