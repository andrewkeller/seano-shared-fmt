"""
support/seano/views/shared/markup.py

Infrastructure to help compile rich text markup

*********************************************
Institutional Knowledge on how DocUtils works
*********************************************

DocUtils has a "Node tree" concept that is responsible for laying out the
structured form of a document.  Confusingly, there are *two* different node
trees: (a) a class hierarchy of different kinds of Nodes, and (b) a document
hierarchy of specific Node subclass objects that contain the data of the
document.

Certain Node classes are subclasses of other Node classes, which helps share
code that serializes content to a certain filetype.

The document tree is a tree of Node objects; each Node object then contains
a fragment of the document, as it existed in the original reStructuredText
document.

In a sense, Nodes are the "common unifying document type" used internally
by DocUtils to represent a document, prior to serializing to the requested
target document type.

Nodes are *not* responsible for serializing into a specific filetype.  The
"Translator" concept is used to convert the tree of node objects into a
serialized document.  A translator takes a single Node object (which presumably
is the root of a Node tree), and serializes it into the document type it owns
based on the class type of the Node object.  There is usually only one
translator per serialized document type (RTF, PDF, man page, etc).

If you want to support new output file types, what you want to define is a new
Translator subclass.

If you want to support a new directive in reStructuredText, you *may* want to
create a new Node subclass, in particular if what the new directive receives
from the user is conceptually a new kind of data.  For data types already
supported, there's no reason you can't use an existing Node subclass.  Either
way, you want to then create a Directive subclass and register it.  This
registration process appears to be global, and may cause compatibility issues
as complexity grows.  Iterate as needed.
"""
import base64
import re
try:
    from StringIO import StringIO # correct on python 2.x; explodes on python 3.x
except ImportError:
    # Must be python 3.x
    from io import StringIO
import sys
# ABK: Why can't pylint import these modules?
import docutils.core #pylint: disable=E0401
import docutils.nodes #pylint: disable=E0401
import docutils.parsers.rst #pylint: disable=E0401
import docutils.writers.html4css1 #pylint: disable=E0401
from .html_buf import SeanoHtmlFragment
from .mermaid import compile_mermaid_to_svg


class SeanoMarkupException(Exception):
    pass


class SeanoMermaidNode(docutils.nodes.General, docutils.nodes.Element):
    '''
    This is a DocUtils Node subclass that represents the data received from
    the user in a reStructuredText document when they use the ``.. mermaid::``
    directive.

    Nodes only declare data fragment types and store original document data;
    they do not declare the directive itself or serialize any data to any
    specific file format.

    Per DocUtils conventions, this class should be named "mermaid" (lowercase).
    However, that makes me (ABK) nervous, so I'm being more verbose for now.
    '''
    pass


class SeanoMermaidDirective(docutils.parsers.rst.Directive):
    '''
    This is a DocUtils Directive subclass that parses a Mermaid directive
    invocation from reStructuredText and converts it into a Node object
    (specifically the Node subclass named ``SeanoMermaidNode``).

    Per DocUtils conventions, this class should be named "Mermaid" (titlecase).
    However, that makes me (ABK) nervous, so I'm being more verbose for now.
    '''
    has_content = True # Mermaid source passed via what reStructuredText calls the "content"
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = { # Dictionary of options accepted by this directive
        'alt': docutils.parsers.rst.directives.unchanged,
        'min-width': docutils.parsers.rst.directives.unchanged,
        'max-width': docutils.parsers.rst.directives.unchanged,
    }

    def run(self):
        node = SeanoMermaidNode()
        node['code'] = '\n'.join(self.content)
        node['options'] = {}
        if 'alt' in self.options:
            node['alt'] = self.options['alt']
        if 'min-width' in self.options:
            node['min-width'] = self.options['min-width']
        if 'max-width' in self.options:
            node['max-width'] = self.options['max-width']
        return [node]

# Actually register our Mermaid directive.  This is the line that makes the
# syntax ``.. mermaid::`` work in a reStructuredText document.
docutils.parsers.rst.directives.register_directive('mermaid', SeanoMermaidDirective)


class SeanoSingleFileHtmlTranslator(docutils.writers.html4css1.HTMLTranslator):
    '''
    This is a DocUtils Translator subclass that serializes a Node tree into
    what we colloquially call "single-file HTML".  It is built upon DocUtils'
    built-in HTML 4 & CSS 1 translator implementation.

    When using this translator, you should use the ``docutils.writers.html4css1.Writer``
    writer.
    '''

    def visit_SeanoMermaidNode(self, node):

        # ABK: I don't have enough experience with HTML and JavaScript at the
        #      moment to confidently embed the Mermaid compiler into a
        #      single-file HTML document.  As a workaround, we pre-compile the
        #      diagram into an SVG, and embed it into the document.  This is a
        #      little sad, becuase:
        #
        #      - This circumvents support for dynamic type (i.e., accessibility)
        #      - Booting up an ECMAScript runtime is *SLOW*.  And because mmdc
        #        is a shell script that boots up Chromium (an ECMAScript runtime
        #        implementation), runs the Mermaid compiler, and shuts down,
        #        compiling Mermaid diagrams from Python is painfully slow.
        #
        #      In theory, compiling Mermaid diagrams at compile-time could be
        #      nice, because we could have build failures for Mermaid syntax
        #      errors at compile time.  However, for syntax errors, mmdc yields
        #      a pretty "syntax error" graphic, and returns *success* (??).
        #
        #      Long story short, this implementation is probably good enough for
        #      now, but there are a number of improvements centered around
        #      performance, accessibility, and automation that I'd like to see
        #      get implemented in the long term.

        # Compile the Mermaid diagram into an SVG in both light mode and dark mode:
        data = compile_mermaid_to_svg(node['code'], themes=['neutral', 'dark'])

        # Base-64-encode the SVGs:
        if sys.hexversion >= 0x3000000: # base64 wants bytes, not str
            data = [x.encode('utf-8') for x in data]
        data = [base64.b64encode(x) for x in data]
        if sys.hexversion >= 0x3000000: # self wants str, not bytes
            data = [x.decode('utf-8') for x in data]

        # Wrap each Base-64-encoded SVG in the correct URL syntax:
        data = ['data:image/svg+xml;base64,' + x for x in data]

        # Formally name the light mode and dark mode images in this code:
        lightdata, darkdata = data

        # Fetch additional options:
        alt = node.get('alt')
        min_width = node.get('min-width')
        max_width = node.get('max-width')

        # Output to the page body our compiled SVG:
        self.body.append(''.join([
            '<picture>',
                '<source srcset="{dark}" media="(prefers-color-scheme: dark)" />'.format(dark=darkdata),
                '<img',
                    ' src="{light}"'.format(light=lightdata),
                    ' alt="{alt}"'.format(alt=self.encode(alt)) if alt else '',
                    ' style="{css}"'.format(css=';'.join(filter(None, [
                        'min-width:{min_width}'.format(min_width=min_width) if min_width else '',
                        'max-width:{max_width}'.format(max_width=max_width) if max_width else '',
                    ]))),
                ' />',
            '</picture>',
        ]))

    def depart_SeanoMermaidNode(self, node):
        pass


_dl_elem_pattern = re.compile(r'''\s*</?d[ldt](?: [^>]*)?>\s*''', re.MULTILINE)
def _seano_rst_to_some_html(txt, writer_class, translator_class):
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
    #
    # Documentation on how to use custom translator objects:
    #   https://gist.github.com/mastbaum/2655700
    #
    error_accumulator = StringIO()
    writer = writer_class()
    writer.translator_class = translator_class
    parts = docutils.core.publish_parts(txt, writer=writer, settings_overrides={
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


def rst_to_html(txt):
    return _seano_rst_to_some_html(txt,
                                  writer_class=docutils.writers.html4css1.Writer,
                                  translator_class=SeanoSingleFileHtmlTranslator)


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
