"""
support/seano/views/shared/html_buf.py

Infrastructure to help build HTML files
"""
from .text_buf import FencedTextBuffer

try:
    from html import escape as _html_escape_func # correct on python 3; explodes on python 2
except ImportError:
    # Must be python 2
    from cgi import escape as _html_escape_func

def html_escape(txt):
    # ABK: So, pylint doesn't follow the try/except logic above, which results in it issuing W1505 saying that
    #      `cgi.escape` is deprecated **ON PYTHON 3**.  In my experimentation, this is the easiest workaround.
    return _html_escape_func(txt) #pylint: disable=W1505


class SeanoHtmlFragment(object):
    '''
    Encapsulates an HTML fragment, in a world where the HTML fragment may require that certain CSS or JS be added in
    the headder of the final document.  A "fragmented fragment", if you will.
    '''
    def __init__(self, html, css=None, js=None): #pylint: disable=C0103
        self.html = html or ''
        self.css = css or ''
        self.js = js or '' #pylint: disable=C0103

    def __bool__(self):
        if not self.html and not self.css and not self.js:
            return False
        return True
    __nonzero__ = __bool__


class SeanoHtmlBuffer(object):
    '''
    Helps you write a single-file HTML file, in a world where:

    - it's a fairly non-trivial document, so you want to use a file buffer for performance
    - you don't know all of the CSS and JS prior to writing the body
    - you want to support Unicode & Python 2 & Python 3 (file streams are a pain)

    You should use this class within a ``with`` statement so that proper cleanup happens if an exception is raised.

    This class accepts both ASCII strings UTF-8 strings.

    This class does not HTML-encode anything.  As far as the caller is concerned, the only thing this class does
    automatically is auto-translate between ASCII and UTF-8.  If something has to be HTML-encoded (such as most JS!),
    the caller must do it prior to writing the data here.
    '''
    def __init__(self):
        '''
        Creates a default ``SeanoHtmlBuffer`` object.  Default data includes:

        - HTML, HEAD, and BODY elements
        - UTF-8 character encoding declaration
        - Mobile-friendly viewport declaration
        '''
        self.doc = FencedTextBuffer(prefix='<html>', suffix='</html>')
        self.head = FencedTextBuffer(prefix='<head>', suffix='</head>', skip_fences_when_body_empty=True)
        self.css = FencedTextBuffer(prefix='<style type="text/css">', suffix='</style>', skip_fences_when_body_empty=True) #pylint: disable=C0301
        self.js = FencedTextBuffer(prefix='<script>', suffix='</script>', skip_fences_when_body_empty=True) #pylint: disable=C0103
        self.body = FencedTextBuffer(prefix='<body>', suffix='</body>')

        self.write_head('''<meta charset="utf-8">''')
        self.write_head('''<meta name="viewport" content="width=device-width, initial-scale=1.0">''')

    def __enter__(self):
        '''
        For compatibility with ``with``.  We have nothing special to do ourselves, but we should forward this notice to
        each of the file buffers.
        '''
        self.doc.__enter__()
        self.head.__enter__()
        self.css.__enter__()
        self.js.__enter__()
        self.body.__enter__()
        return self

    def __exit__(self, ertype, value, traceback):
        '''
        For compatibility with ``with``.  We have nothing special to do ourselves, but we should forward this notice to
        each of the file buffers.
        '''
        self.doc.__exit__(ertype, value, traceback)
        self.head.__exit__(ertype, value, traceback)
        self.css.__exit__(ertype, value, traceback)
        self.js.__exit__(ertype, value, traceback)
        self.body.__exit__(ertype, value, traceback)

    def write_head(self, txt):
        '''
        Writes the given ASCII or UTF-8 data to the generic ``<HEAD>`` section.
        '''
        self.head.write(txt)

    def write_css(self, txt):
        '''
        Writes the given ASCII or UTF-8 data to the CSS section.
        '''
        self.css.write(txt)

    def write_js(self, txt):
        '''
        Writes the given ASCII or UTF-8 data to the JavaScript section.
        '''
        self.js.write(txt)

    def write_body(self, txt):
        '''
        Writes the given ASCII or UTF-8 data to the ``<BODY>`` section.
        '''
        self.body.write(txt)

    def all_data(self):
        '''
        Returns the finalized, concatenated string version of all data currently saved in this object.

        The returned data is ALWAYS a unicode string, regardless of Python version.  This means it's a unicode object
        in Python 2, and a str object in Python 3.
        '''
        return self.doc.udump(
            insert_after_body=self.head.udump(
                insert_after_body=self.css.udump() + self.js.udump()
            ) + self.body.udump()
        )
