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


def seano_release_ancestor_names_including_self(name, cmc):
    """
    Returns an unordered set of the names of all releases that are ancestors of the given release
    name in the ancestry graph contained inside the given ``SeanoMetaCache`` (``cmc``) object,
    including the given release name itself.

    Parameters:

    - ``name`` (string): The name of the release you're interested in
    - ``cmc`` (``SeanoMetaCache``): A ``SeanoMetaCache`` object containing the release ancestry graph
      that is pertinent to the release name with which you're inquiring

    Returns: a set of release names (a set of strings)
    """
    try:
        cache = cmc.ancestor_release_name_sets_including_self
    except AttributeError:
        cache = {}
        cmc.ancestor_release_name_sets_including_self = cache
    try:
        return cache[name]
    except KeyError:
        result = set([name]).union(*[
            seano_release_ancestor_names_including_self(x['name'], cmc) for x in cmc.named_releases[name]['after']
        ])
        cache[name] = result
        return result


def seano_release_descendant_names_including_self(name, cmc):
    """
    Returns an unordered set of the names of all releases that are descendants of the given release
    name in the ancestry graph contained inside the given ``SeanoMetaCache`` (``cmc``) object,
    including the given release name itself.

    Parameters:

    - ``name`` (string): The name of the release you're interested in
    - ``cmc`` (``SeanoMetaCache``): A ``SeanoMetaCache`` object containing the release ancestry graph
      that is pertinent to the release name with which you're inquiring

    Returns: a set of release names (a set of strings)
    """
    try:
        cache = cmc.descendant_release_name_sets_including_self
    except AttributeError:
        cache = {}
        cmc.descendant_release_name_sets_including_self = cache
    try:
        return cache[name]
    except KeyError:
        result = set([name]).union(*[
            seano_release_descendant_names_including_self(x['name'], cmc) for x in cmc.named_releases[name]['before']
        ])
        cache[name] = result
        return result


def seano_minimum_ancestor_list(bag, cmc):
    """
    Given a bag of release names (S) and a ``SeanoMetaCache`` (``cmc``) object containing a set of
    releases, this function returns a subset of S (M) where no release in M is a descendant of any
    release in M.

    Parameters:

    - ``bag`` (iterable of strings): The source list of release names
    - ``cmc`` (``SeanoMetaCache``): A ``SeanoMetaCache`` containing a set of releases

    Returns: list of release names (list of strings)
    """
    if not isinstance(bag, list):
        bag = list(bag)

    for item in bag:
        if len(bag) < 2:
            # It's no longer possible to remove any elements
            break
        smaller_bag = [x for x in bag if x != item]
        if item in set().union(*[seano_release_descendant_names_including_self(x, cmc) for x in smaller_bag]):
            bag = smaller_bag

    return bag


def seano_minimum_descendant_list(bag, cmc):
    """
    Given a bag of release names (S) and a ``SeanoMetaCache`` (``cmc``) object containing a set of
    releases, this function returns a subset of S (M) where no release in M is an ancestor of any
    release in M.

    Parameters:

    - ``bag`` (iterable of strings): The source list of release names
    - ``cmc`` (``SeanoMetaCache``): A ``SeanoMetaCache`` containing a set of releases

    Returns: list of release names (list of strings)
    """
    if not isinstance(bag, list):
        bag = list(bag)

    for item in bag:
        if len(bag) < 2:
            # It's no longer possible to remove any elements
            break
        smaller_bag = [x for x in bag if x != item]
        if item in set().union(*[seano_release_ancestor_names_including_self(x, cmc) for x in smaller_bag]):
            bag = smaller_bag

    return bag


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


def seano_copy_note_fields_to_releases(cmc, fields):
    """
    Iterates over the releases list inside the given ``SeanoMetaCache`` (``cmc``) object, copying
    from notes onto the each associated release the fields and their values identified by the given
    list of fields.

    The given releases list is edited in-place.

    Inputs:

    - ``cmc`` (``SeanoMetaCache``): a ``SeanoMetaCache`` object containing releases
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

    # For each release:
    for r in cmc.releases:

        # For each field we're copying from notes to releases:
        for f in fields.keys():

            # Because we're iterating over all releases (including backstories),
            # we need to skip notes in each release that are copied from backstories:
            notes = [n for n in r['notes'] if not n.get('is-copied-from-backstory')]

            # For each note, grab the value for the current field:
            values = [n[f] for n in notes if f in n]
            if values:

                # Merge the new values into the release:
                try:
                    r[f] = fields[f](
                        does_privileged_base_exist=f in r,
                        privileged_base=r.get(f),
                        additions=values,
                    )
                except SeanoSchemaPaintingException as e:
                    # We are not going to swallow this exception; we will let it unwind the stack.
                    # However, we would like to improve the error message before it goes.
                    msg = e.args[0] + '''

This happened because multiple notes within the {release} release
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


def seano_propagate_sticky_release_fields(cmc, fields):
    """
    Iterates over the releases list inside the given ``SeanoMetaCache`` (``cmc``) object, copying
    from ancestor releases to descendant releases the fields and their values identified by the
    given list of fields.

    The given releases list is edited in-place.

    Inputs:

    - ``cmc`` (``SeanoMetaCache``): a ``SeanoMetaCache`` object containing releases
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

    _seen_releases = set()
    def process_release(release):
        if release['name'] in _seen_releases:
            return
        _seen_releases.add(release['name'])

        # Process all parents first:
        for r in release['after']:
            process_release(cmc.named_releases[r['name']])

        # Copy each field from the parent release, one by one:
        for f in fields:
            # List all non-transitive immediate parents:
            values = seano_minimum_descendant_list(bag=[x['name'] for x in release['after']], cmc=cmc)
            # Convert release names to release objects:
            values = [cmc.named_releases[r] for r in values]
            # Fetch the value of the current field from each of the release objects, if set:
            values = [r[f] for r in values if f in r]
            # If this field was set on any parent:
            if values:
                # ... then copy the value to this release:
                # (note that we may have to reconcile multiple values from multiple parent releases)
                try:
                    release[f] = seano_field_mergetool_opaque(
                        does_privileged_base_exist=f in release,
                        privileged_base=release.get(f),
                        additions=values,
                    )
                except SeanoSchemaPaintingException as e:
                    # We are not going to swallow this exception; we will let it unwind the stack.
                    # However, we would like to improve the error message before it goes.
                    msg = e.args[0] + '''

This happened because multiple ancestors of the {release} release
have changed the value of {field} to different values,
and seano isn't smart enough to reconcile the differences and save a
provably correct merged value on the {release} release.  The easiest
way to workaround this problem is to open up seano-config.yaml, and
on the {release} release, manually set the correctly merged value of
{field}.'''.format(release=release['name'], field=f)
                    e.args = (msg,) + e.args[1:]
                    raise

    for r in reversed(cmc.releases): # Not required, but reduces unnecessary recursion
        process_release(r)
