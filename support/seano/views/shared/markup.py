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
import json
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
import html
import markdown
from .html_buf import SeanoHtmlFragment


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


_MERMAID_AUTO_INIT_KEY = 0

class SeanoSingleFileHtmlTranslator(docutils.writers.html4css1.HTMLTranslator):
    '''
    This is a DocUtils Translator subclass that serializes a Node tree into
    what we colloquially call "single-file HTML".  It is built upon DocUtils'
    built-in HTML 4 & CSS 1 translator implementation.

    When using this translator, you should use the ``docutils.writers.html4css1.Writer``
    writer.
    '''

    def visit_SeanoMermaidNode(self, node):
        # ABK: Mermaid doesn't properly calculate the size of elements that are
        # not visible.  To workaround, don't compile Mermaid diagrams until they
        # are visible.  To implement this without requiring infrastructure
        # outside of this method, we're going to give every Mermaid diagram its
        # own unique identifier, and then use the `IntersectionObserver` API to
        # detect when the element becomes visible, and when that happens, tell
        # Mermaid to compile that specific diagram.
        global _MERMAID_AUTO_INIT_KEY
        _MERMAID_AUTO_INIT_KEY = _MERMAID_AUTO_INIT_KEY + 1
        key = 'mermaid-%d' % (_MERMAID_AUTO_INIT_KEY,)

        self.body.extend([
            '<pre class="mermaid" id="%s">' % (key,),
            node['code'],
            '</pre>',
            '''<script type="module">''',
                '''import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';''',
                '''const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;''',
                '''mermaid.initialize({'startOnLoad': false, 'securityLevel': 'antiscript', 'theme': prefersDarkMode ? 'dark' : 'neutral'});''',
                '''new IntersectionObserver((entries, observer) => {''',
                    '''entries.forEach(entry => {''',
                        '''if (entry.intersectionRatio > 0) {''',
                            '''observer.disconnect();''',
                            '''mermaid.run(%s);''' % (json.dumps({'querySelector': '#' + key}),),
                        '''}''',
                    '''});''',
                '''}).observe(document.getElementById('%s'));''' % (key,),
            '''</script>''',
        ])

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


class SeanoMarkup(object):
    """
    Base class for encapsulating some rich text markup that can self-convert to
    various output formats.  Includes some stock shared code to support some of
    the common types that are, under the hoods, derivatives, rather than
    distinct types, allowing the real subclasses to not need to reimplement
    everything all the time.
    """

    def __init__(self, payload, localization=None, tags=None):
        self.payload = payload
        self.localization = localization
        self.tags = tags or []

    def deep_copy(self):
        return self.__class__(payload=self.payload, localization=self.localization, tags=self.tags)

    def __bool__(self): return bool(self.payload)
    def __nonzero__(self): return bool(self.payload)

    def __eq__(self, other): return \
        self.__class__ == other.__class__ and \
        self.payload == other.payload and \
        self.localization == other.localization and \
        self.tags == other.tags

    def __str__(self): return repr(self.payload)
    def __repr__(self): return str(self)

    _line_pattern = re.compile(r'''^<p[^>]*>(?P<contents>.*)</p>\s*$''', re.MULTILINE | re.DOTALL)
    def toHtmlLine(self):
        '''
        Returns the same as `toHtmlBlock()`, except sans a top-level element.

        On soft errors, this function may return an empty `SeanoHtmlFragment`
        object.  This function never returns `None`.

        The algorithm that strips the top-level element off of the return value
        is fairly stupid; try to not pass unknown garbage into this function.
        '''
        result = self.toHtmlBlock()
        if not result:
            return result
        m = self._line_pattern.match(result.html)
        if not m:
            raise SeanoMarkupException('Compiled HTML does not look like a single line: %s' % (result.html,))
        result.html = m.group('contents').strip()
        return result

    # ABK: toHtmlBlock() is the main function that subclasses need to implement


class SeanoPlainText(SeanoMarkup):
    def toHtmlLine(self):
        return SeanoHtmlFragment(html=html.escape(self.payload))

    def toHtmlBlock(self):
        result = self.toHtmlLine()
        result.html = '<p>' + result.html + '</p>'
        return result


class SeanoFalseyMarkup(SeanoMarkup):
    def __init__(self, explanation=''):
        self.explanation = explanation

    def __eq__(self, other): return \
        self.__class__ == other.__class__ and \
        self.explanation == other.explanation

    def deep_copy(self): return SeanoFalseyMarkup(explanation=self.explanation)
    def __bool__(self): return False
    def __nonzero__(self): return False
    def __str__(self): return '<FalseyMarkup>'
    def toHtmlLine(self): return SeanoHtmlFragment(html='')
    def toHtmlBlock(self): return SeanoHtmlFragment(html='')


class SeanoReStructuredText(SeanoMarkup):
    def __str__(self): return 'RST(%s)' % (super().__str__())

    def toHtmlBlock(self):
        return _seano_rst_to_some_html(self.payload,
                                      writer_class=docutils.writers.html4css1.Writer,
                                      translator_class=SeanoSingleFileHtmlTranslator)


class SeanoMarkdown(SeanoMarkup):
    def __str__(self): return 'MD(%s)' % (super().__str__())

    def toHtmlBlock(self):
        return SeanoHtmlFragment(
            html=markdown.markdown(
                self.payload,
                extensions=['pymdownx.superfences', 'pymdownx.highlight'],
            ),
        )


SUPPORTED_MARKUP = {
    'rst': SeanoReStructuredText,
    'md': SeanoMarkdown,
    '': SeanoPlainText,
}
