"""
support/seano/views/shared/markup.py

Infrastructure to help compile rich text markup
"""
import re
try:
    from StringIO import StringIO # correct on python 2.x; explodes on python 3.x
except ImportError:
    # Must be python 3.x
    from io import StringIO
from docutils import core as docutils_core #pylint: disable=E0401
from docutils.writers.html4css1 import Writer as docutils_Writer #pylint: disable=E0401
from .html_buf import SeanoHtmlFragment


class SeanoMarkupException(Exception):
    pass


_dl_elem_pattern = re.compile(r'''\s*</?d[ldt](?: [^>]*)?>\s*''', re.MULTILINE)
def rst_to_html(txt):
    '''
    Compiles the given reStructuredText blob into an HTML snippet, sans the ``<html>`` and ``<body>`` elements.

    Returns a SeanoHtmlFragment object containing the HTML fragment, and also recommended CSS/JS to make it work.

    On soft errors, this function may return an empty ``SeanoHtmlFragment`` object.  This function never returns None.
    '''
    if not txt.strip(): return SeanoHtmlFragment(html='')
    # Docutils likes to print warnings & errors to stderr & the compiled output.  We don't particularly want that
    # here...  What we'd like ideally is to capture any warnings and errors, and explicitly report them to the
    # caller.  If this is being used within Waf, we'd ideally like to trigger a build failure (and never have
    # surprise output in the rendered HTML).
    #
    # Fortunately, Docutils lets us do this.
    #
    # More info on settings overrides here:
    #   https://sourceforge.net/p/docutils/mailman/message/30882883/
    #   https://github.com/pypa/readme_renderer/blob/master/readme_renderer/rst.py
    error_accumulator = StringIO()
    parts = docutils_core.publish_parts(txt, writer=docutils_Writer(), settings_overrides={
        'warning_stream': error_accumulator,
    })

    # Artificially fail if any errors or warnings were reported
    errors = error_accumulator.getvalue().splitlines()
    error_accumulator.close() # ABK: Not sure if this is required, but most of the docs have it
    if errors:
        # ABK: Some errors include the bad markup, and some don't.  Not sure what the pattern is yet.
        #      For now, for all errors, append the original full markup, with line numbers.
        with_line_numbers = []
        for line in txt.splitlines():
            with_line_numbers.append('%4d    %s' % (len(with_line_numbers) + 1, line))
        errors.append('    %s' % ('\n    '.join(with_line_numbers)))
        raise SeanoMarkupException('\n'.join(errors))

    # No errors; return the rendered HTML fragment
    html = parts['fragment']
    css = parts['stylesheet']

    # Docutils likes to insert <dl>, <dd>, and <dt> elements.  Long term, it would be nice to know why (screen readers
    # come to mind).  For now, those elements are causing problems with styling.  Yank them out.
    html = _dl_elem_pattern.sub('', html)

    # The CSS that Docutils returns is wrapped inside a <style> element.  We don't want that here.  Yank it out.
    css_prefix = '<style type="text/css">\n\n'
    if not css.startswith(css_prefix):
        raise SeanoMarkupException('CSS returned from the reStructuredText compiler has an unexpected prefix: %s', css)
    css = css[len(css_prefix):]

    css_suffix = '\n\n</style>\n'
    if not css.endswith(css_suffix):
        raise SeanoMarkupException('CSS returned from the reStructuredText compiler has an unexpected suffix: %s', css)
    css = css[:len(css) - len(css_suffix)]

    # The default Pygments CSS does not work in dark mode; let's fix that:
    css = css + '''

@media (prefers-color-scheme: dark) {
    /* Custom overrides for Pygments so that it doesn't suck in dark mode */
    pre.code .ln { color: lightgrey; } /* line numbers */
    pre.code .comment, code .comment { color: rgb(127, 139, 151) }
    pre.code .keyword, code .keyword { color: rgb(236, 236, 22) }
    pre.code .literal.string, code .literal.string { color: rgb(217, 200, 124) }
    pre.code .name.builtin, code .name.builtin { color: rgb(255, 60, 255) }
}'''

    return SeanoHtmlFragment(html=html, css=css)


_rst_line_pattern = re.compile(r'''^<p[^>]*>(?P<contents>.*)</p>\s*$''', re.MULTILINE)
def rst_line_to_html(txt):
    '''
    Returns the HTML equivalent of the given tiny reStructuredText snippet, sans a top-level element.

    The returned result is encapsulated in a ``SeanoHtmlFragment`` object.

    On soft errors, this function may return an empty ``SeanoHtmlFragment`` object.  This function never
    returns ``None``.

    The algorithm that strips the top-level element off of the return value is fairly stupid; try to
    not pass unknown garbage into this function.
    '''
    result = rst_to_html(txt)
    if not result:
        return result
    m = _rst_line_pattern.match(result.html)
    if not m:
        raise SeanoMarkupException('Compiled HTML does not look like a single line: %s' % (txt,))
    result.html = m.group('contents')
    return result
