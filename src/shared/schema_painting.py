"""
support/seano/views/shared/schema_painting.py

Infrastructure to retroactively modify seano's query output file.

Functionality like this is deliberately not part of seano itself to help keep seano's query
output schema as simple as possible.  These functions don't create any new information
that doesn't already exist, but they do make existing information easier to access on-the-fly.
"""
from .schema_plumbing import *


def seano_paint_backstory_releases(cmc, start):
    """
    Iterates over the releases list in the given ``SeanoMetaCache`` (``cmc``) object, starting
    at the given start release name, and progressing to all ancestors.  On every touched release,
    ``is-backstory`` is set to a boolean value indicating whether or not the release is part of
    a backstory relative to the given start release.

    The releases list is edited in-place.

    The start release is assumed to not be a backstory.

    Releases descendant from the start release are not modified; this algorithm only operates
    on ancestors.
    """
    def paint(name, is_backstory):

        cmc.named_releases[name]['is-backstory'] = is_backstory

        ancestors = cmc.named_releases[name]['after']

        for ancestor in [x['name'] for x in ancestors if x.get('is-backstory', False)]:
            paint(ancestor, True)
        for ancestor in [x['name'] for x in ancestors if not x.get('is-backstory', False)]:
            paint(ancestor, is_backstory)

    paint(start, False)


def seano_paint_release_sys_limits(cmc):
    """
    Iterates over the releases list in the given ``SeanoMetaCache`` (``cmc``) object,
    propagating the min and max support OS fields across the entire release ancestry.

    The releases list is edited in-place.
    """
    fields = ['min-supported-os', 'max-supported-os']
    seano_copy_note_fields_to_releases(cmc, fields)
    seano_propagate_sticky_release_fields(cmc, fields)


def seano_paint_release_risk_levels(cmc):
    """
    Iterates over the releases list in the given ``SeanoMetaCache`` (``cmc``) object,
    calculating the aggregate risk level for each release based on data found in notes.

    The releases list is edited in-place.

    This function is conceptually similar to seano_copy_note_fields_to_releases(),
    except that there is a *default* value when the 'risk' key does not exist in
    any note in the release.
    """
    for release in cmc.releases:
        if 'risk' in release:
            continue

        # Because we're iterating over all releases (including backstories),
        # we need to skip notes in each release that are copied from backstories:
        notes = [n for n in release['notes'] if not n.get('is-copied-from-backstory')]

        levels = [x.get('risk') for x in notes]
        for level in ['high', 'medium', 'low']:
            if level in levels:
                release['risk'] = level
                break
        else:
            release['risk'] = '' if any([x != None for x in levels]) else None
