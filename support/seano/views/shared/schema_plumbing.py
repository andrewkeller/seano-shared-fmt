"""
support/seano/views/shared/schema_plumbing.py

Low-level infrastructure to retroactively modify seano's query output file.

Functionality like this is deliberately not part of seano itself to help keep seano's query
output schema as simple as possible.  These functions don't create any new information
that doesn't already exist, but they do make existing information easier to access on-the-fly.
"""
import os


class SeanoSchemaPaintingException(Exception):
    pass


def seano_field_mergetool_opaque(does_privileged_base_exist, privileged_base, additions):
    """
    A merge tool used by some seano plumbing that performs a merge of an opaque type.

    Inputs:

    - ``does_privileged_base_exist`` (``bool``): whether or not an existing ``privileged_base`` exists
    - ``privileged_base`` (``any``): a value that ``additions`` are getting merged *into*
    - ``additions`` (``[any]``): a list of values to merge together onto the ``privileged_base``

    Returns: (any) the merged result; ``privileged_base`` is not modified

    Nature of the merge algorithm:

    1. If the ``privileged_base`` exists, then it overrides any ``additions`` and is the final answer.
    2. If all the ``additions`` are the same value, then any one of the ``additions`` is the final answer.

    On any error, a ``SeanoSchemaPaintingException`` is raised.
    """
    if does_privileged_base_exist:
        return privileged_base

    if not additions or not all([x == additions[0] for x in additions]):
        raise SeanoSchemaPaintingException('Unable to merge values: %s' % (additions,))

    return additions[0]


def seano_copy_note_fields_to_releases(releases, fields):
    """
    Iterates over the given releases list, copying from notes onto the each associated release
    the fields and their values identified by the given list of fields.

    The given releases list is edited in-place.

    Inputs:

    - ``releases`` (``list``): a seano release list
    - ``fields`` (``list`` or ``dict``): a list of fields to copy from each note onto the
      respective releases, or a dictionary of fields to copy, associated with their merge
      tool functions

    Returns: nothing

    On any error, a ``SeanoSchemaPaintingException`` is raised.

    WARNING: This algorithm is designed for **rarely changing value**.  Things you change once
    in a blue moon.  This algorithm **has no reasonable merge tool**, and when you change a value
    more than once in the same release, things explode.
    """
    if isinstance(fields, list):
        fields = {x: seano_field_mergetool_opaque for x in fields}

    for r in releases:
        for f in fields.keys():
            values = [n[f] for n in r['notes'] if f in n]
            if values:
                try:
                    r[f] = fields[f](
                        does_privileged_base_exist=f in r,
                        privileged_base=r.get(f),
                        additions=values,
                    )
                except SeanoSchemaPaintingException as e:
                    # We are not going to swallow this exception; we will let it unwind the stack.
                    # However, we would like to improve the error message before it goes.
                    msg = e.args[0] + os.linesep + os.linesep + \
'''This happened because multiple notes within the {release} release
tried to set a different new value for {field},
and seano isn't smart enough to reconcile the differences and save a
provably correct merged value on the {release} release.  To workaround
this problem, you have two main choices:

1. Create a new release in between the two notes that conflict, such that
   each release edits {field} only once
2. Open up seano-config.yaml, and on the {release} release, manually
   set the correctly merged value of {field}'''.format(release=r['name'], field=f)
                    e.args = (msg,) + e.args[1:]
                    raise


def seano_propagate_sticky_release_fields(releases, fields):
    """
    Iterates over the given releases list, copying from ancestor releases to descendant releases
    the fields and their values identified by the given list of fields.

    The given releases list is edited in-place.

    Inputs:

    - ``releases`` (``list``): a seano release list
    - ``fields`` (``list`` or ``dict``): a list of fields to copy from one release to the next,
      or a dictionary of fields to copy, associated with their merge tool functions

    Returns: nothing

    On any error, a ``SeanoSchemaPaintingException`` is raised.

    WARNING: This algorithm is designed for **rarely changing value**.  Things you change once
    in a blue moon.  This algorithm **has no reasonable merge tool**, and when you change a value
    in more than one parallel ancestry, when the ancestries eventually merge, things explode.
    """
    if isinstance(fields, list):
        fields = {x: seano_field_mergetool_opaque for x in fields}

    releases_lookup = {r['name']: r for r in releases}

    _ancestor_inheritance = {}
    def get_ancestor_inheritance(node):
        try:
            return _ancestor_inheritance[node]
        except KeyError:
            result = set([node]).union(*map(get_ancestor_inheritance,
                                            [x['name'] for x in releases_lookup[node]['after']]))
            _ancestor_inheritance[node] = result
            return result

    _non_transitive_parents = {}
    def get_non_transitive_parents(node):
        try:
            return _non_transitive_parents[node]
        except KeyError:
            # Start with all ancestors:
            result = [r['name'] for r in releases_lookup[node]['after']]
            # Remove transitive ancestors:
            for candidate in list(result):
                if candidate in set().union(*[get_ancestor_inheritance(x) for x in result if x != candidate]):
                    result.remove(candidate)
            _non_transitive_parents[node] = result
            return result

    _seen_releases = set()
    def process_release(release):
        if release['name'] in _seen_releases:
            return
        _seen_releases.add(release['name'])

        # Process all parents first:
        for r in release['after']:
            process_release(releases_lookup[r['name']])

        # Copy each field from the parent release, one by one:
        for f in fields:
            values = get_non_transitive_parents(release['name'])
            values = [releases_lookup[r] for r in values]
            values = [r[f] for r in values if f in r]
            if values:
                try:
                    release[f] = seano_field_mergetool_opaque(
                        does_privileged_base_exist=f in release,
                        privileged_base=release.get(f),
                        additions=values,
                    )
                except SeanoSchemaPaintingException as e:
                    # We are not going to swallow this exception; we will let it unwind the stack.
                    # However, we would like to improve the error message before it goes.
                    msg = e.args[0] + os.linesep + os.linesep + \
'''This happened because multiple ancestors of the {release} release
have changed the value of {field} to different values,
and seano isn't smart enough to reconcile the differences and save a
provably correct merged value on the {release} release.  The easiest
way to workaround this problem is to open up seano-config.yaml, and
on the {release} release, manually set the correctly merged value of
{field}.'''.format(release=release['name'], field=f)
                    e.args = (msg,) + e.args[1:]
                    raise

    for r in reversed(releases): # Not required, but reduces unnecessary recursion
        process_release(r)
