"""
support/seano/views/shared/text_buf.py

Infrastructure to help build text blobs
"""
import sys
import tempfile


def to_ascii(txt):
    # ABK: Pylint can't read this if statement, and complains about `unicode` not existing in Python 3.
    if sys.hexversion >= 0x3000000:
        if isinstance(txt, bytes):
            return txt
        if isinstance(txt, str):
            return txt.encode('utf-8')
        return str(txt).encode('utf-8')
    if isinstance(txt, str):
        return txt
    if isinstance(txt, unicode): #pylint: disable=E0602
        return txt.encode('utf-8')
    return str(txt)


def to_unicode(txt):
    # ABK: Pylint can't read this if statement, and complains about `unicode` not existing in Python 3.
    if sys.hexversion >= 0x3000000:
        if isinstance(txt, bytes):
            return txt.decode('utf-8')
        if isinstance(txt, str):
            return txt
        return str(txt)
    if isinstance(txt, str):
        return txt.decode('utf-8')
    if isinstance(txt, unicode): #pylint: disable=E0602
        return txt
    return unicode(txt) #pylint: disable=E0602


class FencedTextBuffer(object):
    '''
    Helps you write a text blob with an optional prefix and suffix.  Designed to help you write the
    prefix and suffix up-front, while the code that builds the body may be long.  This helps keep
    the prefix and suffix close to each other when they are declared.

    You should use this class within a ``with`` statement so that proper cleanup happens if an
    exception is raised.

    This class accepts both ASCII strings UTF-8 strings, for both Python 2 and Python 3.

    The udump() method returns data in Unicode, regardless of the Python version.
    '''
    def __init__(self, prefix=None, suffix=None, skip_fences_when_body_empty=False):
        'Creates a default ``FencedTextBuffer`` object.'
        self.prefix = prefix
        self.body = tempfile.TemporaryFile()
        self.suffix = suffix
        self.skip_fences_when_body_empty = skip_fences_when_body_empty

    def __enter__(self):
        '''
        For compatibility with ``with``.  We have nothing special to do ourselves, but we should
        forward this notice to each of the file buffers.
        '''
        self.body.__enter__()
        return self

    def __exit__(self, ertype, value, traceback):
        '''
        For compatibility with ``with``.  We have nothing special to do ourselves, but we should
        forward this notice to each of the file buffers.
        '''
        self.body.__exit__(ertype, value, traceback)

    def write(self, txt):
        '''
        Writes the given ASCII or UTF-8 data to the body.
        '''
        self.body.write(to_ascii(txt))

    def udump(self, insert_before_body=None, insert_after_body=None):
        '''
        Returns the finalized, concatenated string version of all data currently saved in this
        object.

        Optionally accepts text to insert before or after the body hunk during assembly.  As far
        as the ``skip_fences_when_body_empty`` option is concerned, these injected values are
        "part of" (they add to) the body.

        The returned data is ALWAYS a unicode string, regardless of Python version.  This means
        it's a unicode object in Python 2, and a str object in Python 3.
        '''
        self.body.seek(0, 0)

        hunk = [insert_before_body, self.body.read(), insert_after_body]

        if not self.skip_fences_when_body_empty or any(hunk):
            hunk = [self.prefix] + hunk + [self.suffix]

        return u''.join(map(to_unicode, filter(None, hunk)))
