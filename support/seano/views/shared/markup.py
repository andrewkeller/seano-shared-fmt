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
import re
try:
    from StringIO import StringIO # correct on python 2.x; explodes on python 3.x
except ImportError:
    # Must be python 3.x
    from io import StringIO
# ABK: Why can't pylint import these modules?
import docutils.core #pylint: disable=E0401
import docutils.nodes #pylint: disable=E0401
import docutils.parsers.rst #pylint: disable=E0401
import docutils.writers.html4css1 #pylint: disable=E0401
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
    }

    def run(self):
        node = SeanoMermaidNode()
        node['code'] = '\n'.join(self.content)
        node['options'] = {}
        if 'alt' in self.options:
            node['alt'] = self.options['alt']
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

        alt = node.get('alt')
        if alt:
            alt = ' alt="{alt}"'.format(alt=self.encode(alt))
        else:
            alt = ''

        self.body.append('''<pre{alt} class="code literal-block">{code}'''.format(
            alt=alt,
            code=self.encode(node['code']),
        ))

    def depart_SeanoMermaidNode(self, node):
        self.body.append('</pre>')


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
