"""
support/seano/views/shared/schema_painting.py

Infrastructure to retroactively modify seano's query output file.

Functionality like this is deliberately not part of seano itself to help keep seano's query
output schema as simple as possible.  These functions don't create any new information
that doesn't already exist, but they do make existing information easier to access on-the-fly.
"""


def seano_paint_backstory_releases(releases, start):
    """
    Edits the given releases list in-place, starting from the given start release name.
    A member named `is-backstory` is added to each release, with a boolean value indicating
    whether or not the release is part of a backstory.

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
