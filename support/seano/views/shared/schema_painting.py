"""
support/seano/views/shared/schema_painting.py

Infrastructure to retroactively modify seano's query output file.

Functionality like this is deliberately not part of seano itself to help keep seano's query
output schema as simple as possible.  These functions don't create any new information
that doesn't already exist, but they do make existing information easier to access on-the-fly.
"""

from .schema_plumbing import *


def seano_paint_backstory_releases(releases, start):
    """
    Iterates over the given releases list, starting at the given start release name, and
    progressing to all ancestors.  On every touched release, ``is-backstory`` is set to a boolean
    value indicating whether or not the release is part of a backstory relative to the given start
    release.

    The releases list is edited in-place.

    The start release is assumed to not be a backstory.

    Releases descendant from the start release are not modified; this algorithm only operates
    on ancestors.
    """
    releases_map = {x['name'] : x for x in releases}

    def paint(name, is_backstory):

        releases_map[name]['is-backstory'] = is_backstory

        ancestors = releases_map[name]['after']

        for ancestor in [x['name'] for x in ancestors if x.get('is-backstory', False)]:
            paint(ancestor, True)
        for ancestor in [x['name'] for x in ancestors if not x.get('is-backstory', False)]:
            paint(ancestor, is_backstory)

    paint(start, False)


def seano_paint_release_sys_limits(releases):
    """
    Iterates over the given releases list, propagating the min and max support OS fields
    across the entire release ancestry.

    The releases list is edited in-place.
    """
    fields = ['min-supported-os', 'max-supported-os']
    seano_copy_note_fields_to_releases(releases, fields)
    seano_propagate_sticky_release_fields(releases, fields)


def seano_paint_release_risk_levels(releases):
    """
    Iterates over the given releases list, calculating the aggregate risk level for each
    release based on data found in notes.

    The releases list is edited in-place.
    """
    for release in releases:
        if 'risk' in release:
            continue
        levels = [x.get('risk') for x in release['notes']]
        for level in ['high', 'medium', 'low']:
            if level in levels:
                release['risk'] = level
                break
        else:
            release['risk'] = '' if any([x != None for x in levels]) else None
