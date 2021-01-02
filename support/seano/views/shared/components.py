"""
support/seano/views/shared/components.py

Shared code that renders certain common view components.
"""
import itertools
from .hlist import seano_cascade_hlist
from .markup import rst_line_to_html
from .links import get_ticket_display_name


def seano_render_html_ticket(url):
    ticket = '<a href="%s" target="_blank">%s</a>' % (url, get_ticket_display_name(url))
    return '<span style="font-size:75%">' + ticket + '</span>'


def seano_html_note_list_line_formatter_simple(node, notes):  #pylint: disable=W0613
    return rst_line_to_html(node['head']).html


def seano_html_note_list_line_formatter_text_with_tickets(node, notes):  #pylint: disable=C0103
    result = seano_html_note_list_line_formatter_simple(node, notes)

    if node.get('already_printed_tickets', False):
        return result

    # To minimize UX noise, we don't want to print tickets on literally every line.
    # As an easy solution, only print tickets on the first line in a note tree where
    # that line and all sub-lines have the same ticket list.

    queue = list(node['children']) # Explicitly clone the children list so we don't corrupt it
    while queue:
        if queue[0]['tags'] != node['tags']:
            # Defer printing of tickets until we get to a deeper sub-line.
            return result
        queue.extend(queue.pop(0)['children'])

    # We've decided to print tickets on this line.  Silence tickets on all sub-lines:

    queue = list(node['children']) # Explicitly clone the children list so we don't corrupt it
    while queue:
        queue[0]['already_printed_tickets'] = True
        queue.extend(queue.pop(0)['children'])

    # Gather all tickets:
    tickets = itertools.chain(*[notes[x].get('tickets') or [] for x in node['tags']])

    # Remove duplicates without changing sort order:
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


def seano_render_html_note_list(notes, key, line_formatter=None):

    if not line_formatter:
        line_formatter = seano_html_note_list_line_formatter_simple

    def render_lst(lst):

        result = [
            '<li>' + line_formatter(n, notes) + render_lst(n['children']) + '</li>'
            for n in lst
        ]

        if not result:
            return ''

        return '<ul>' + ''.join(result) + '</ul>'

    return render_lst(seano_cascade_hlist(notes, key))
