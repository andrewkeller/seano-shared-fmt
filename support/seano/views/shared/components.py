"""
support/seano/views/shared/components.py

Shared code that renders certain common view components.
"""
import itertools
from .hlist import SeanoUnlocalizedHListIterNode
from .links import get_ticket_display_name


def seano_render_html_ticket(url):
    ticket = '<a href="%s" target="_blank">%s</a>' % (url, get_ticket_display_name(url))
    return '<span style="font-size:75%">' + ticket + '</span>'


def seano_html_hlist_blob_formatter_simple(node):
    return node.element.toHtmlBlock().html


def seano_html_hlist_line_formatter_simple(node):
    return node.element.toHtmlLine().html


def seano_html_hlist_line_formatter_text_with_tickets(notes, line_formatter=None):  #pylint: disable=C0103
    line_formatter = line_formatter or seano_html_hlist_line_formatter_simple
    def formatter(node):
        result = line_formatter(node)

        # To minimize UX noise, we don't want to print tickets on literally every line.
        # As an easy solution, only print tickets on the first line in a note tree where
        # that line and all sub-lines have the same ticket list.

        # Has one of our parents already printed?
        if getattr(node, 'is_printed', False):
            # One of our parents was already printed.  Bail.
            return result

        # None of our parents have printed.  Do all of our children have the
        # same tickets as us?

        def get_tickets(note_ids):
            return itertools.chain(*[note.get('tickets') or [] for note in notes if note['id'] in note_ids])
        tickets = list(get_tickets(note_ids=node.element.tags))
        tickets_set = set(tickets)

        for child in node.walk():
            if tickets_set != set(get_tickets(child.note_ids)):
                # One of our children has a different note set than us.
                # Defer printing of tickets until we get to a deeper sub-line.
                return result

        # We've decided to print tickets on this line.  Silence tickets on all sub-lines:
        def silence(x):
            x.is_printed = True
            for child in x.children:
                silence(child)
        silence(node)

        # Remove duplicate tickets without changing sort order:
        def dedup(lst):
            seen = set()
            for x in lst:
                if x not in seen:
                    seen.add(x)
                    yield x
        tickets = dedup(tickets)

        # Compile tickets into HTML:
        tickets = [seano_render_html_ticket(x) for x in tickets]

        # Return entire note line, with all of the tickets:
        return ' '.join([result] + tickets)

    return formatter


def seano_render_html_hlist(hlist, is_blob_field=False, block_formatter=None, line_formatter=None):

    block_formatter = block_formatter or seano_html_hlist_blob_formatter_simple
    line_formatter = line_formatter or seano_html_hlist_line_formatter_simple

    def _run(node):

        if node.level > 0:
            yield '<li>'
            yield line_formatter(node=node)
        elif node.element:
            yield block_formatter(node=node)

        if node.children:
            if node.level >= 0:
                yield '<ul>'
            for child in node.children:
                for hunk in _run(node=child):
                    yield hunk
            if node.level >= 0:
                yield '</ul>'

        if node.level > 0:
            yield '</li>'

    return ''.join(_run(node=SeanoUnlocalizedHListIterNode(node=hlist, level=-1 if is_blob_field else 0)))
