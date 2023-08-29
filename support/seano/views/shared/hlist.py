"""
support/seano/views/shared/hlist.py

Infrastructure to work with hierarchical lists (hlists)
"""
from functools import reduce

from .markup import (
    SUPPORTED_MARKUP,
    SeanoMarkup,
    SeanoFalseyMarkup,
    SeanoMarkupException,
)


class SeanoUnlocalizedHListNode(object):
    """
    Represents a hierarchical list of ``SeanoMarkup`` objects, commonly referred
    to in the ``seano`` ecosystem as an "hlist".

    Main features:

    - some automatic type coercion
    - some error checking
    - developer-friendly iteration utilities
    """
    def __init__(self, element, children):
        self.element = element
        self.children = children

        # `children` is supposed to be a `list` of `SeanoUnlocalizedHListNode`
        # objects that each have a `SeanoMarkup` object as their `element`.

        # To simplify code elsewhere, allow the top-level `children` container
        # to be some limited variants, such as None, generators, or markup:
        if self.children is None:
            self.children = [] # no children
        elif isinstance(self.children, SeanoUnlocalizedHListNode):
            pass # correct type (nothing to change)
        elif isinstance(self.children, SeanoMarkup):
            self.children = [self.children]
        elif hasattr(self.children, '__iter__'): # allow generators
            pass # close enough (list comprehension below will convert to list)
        else:
            raise SeanoMarkupException('assertion error: unsupported hlist children list: %s' % (self.children,))

        # To simplify code elsewhere, allow each item inside `children` to be
        # some limited variants, such as markup:
        def fixup_type(item):
            if item is None:
                raise SeanoMarkupException('assertion error: no hlist node child is allowed to be None')
            elif isinstance(item, SeanoUnlocalizedHListNode) and not item.element:
                raise SeanoMarkupException('assertion error: no hlist node child is allowed to have a falsey element; proposed node child: %s' % (item,))
            elif isinstance(item, SeanoUnlocalizedHListNode):
                return item
            elif isinstance(item, SeanoFalseyMarkup):
                return SeanoUnlocalizedHListNode(element=item, children=None) # Special case
            elif isinstance(item, SeanoMarkup) and not item:
                raise SeanoMarkupException('assertion error: no hlist node child is allowed to have a falsey element; proposed node child: %s' % (item,))
            elif isinstance(item, SeanoMarkup):
                return SeanoUnlocalizedHListNode(element=item, children=None)
            raise SeanoMarkupException('assertion error unsupported hlist child payload: %s' % (item,))
        self.children = [fixup_type(x) for x in self.children]

    def deep_copy(self):
        return SeanoUnlocalizedHListNode(
            element=None if self.element is None else self.element.deep_copy(),
            children=[x.deep_copy() for x in self.children],
        )

    def __bool__(self): return bool(self.element) or bool(self.children)
    def __nonzero__(self): return bool(self.element) or bool(self.children)

    def __eq__(self, other): return isinstance(other, SeanoUnlocalizedHListNode) and self.element == other.element and self.children == other.children

    def __str__(self): return '%s -> %s' % (self.element, self.children)
    def __repr__(self): return str(self)

    def walk(self, level=1, include_root=False, unroll_recursion=True):
        """
        Recursively iterates over this object, providing a custom iteration
        node object at each step, with special named properties describing
        the current state of navigation.  Notably:

        - level: the integer level of the current node in the hlist; starts at 1
        - level_diff: the change in the level since the last node
        - text: the text payload of this node
        - num_children: the number of children of this node
        - note_ids: the list of note IDs that contributed to this node

        The values provided during iteration are deep clones of this object,
        which means that you are free to mutate them during iteration, and
        that any custom values you set on this object will be missing.
        """
        tree = SeanoUnlocalizedHListIterNode(node=self, level=level - 1)
        for node in tree._walk(include_root=include_root, unroll_recursion=unroll_recursion):
            yield node

    def __iter__(self):
        """
        A shortcut for the default behavior of the ``walk()`` method.
        """
        for node in self.walk():
            yield node

    def first(self):
        """
        Returns just the first element, if it exists.  Returns a
        ``SeanoFalseyMarkup`` object if this hlist is empty.

        This method is more performant than going through the iterator API,
        because the iterator API always does a full traversal of the entire
        tree before it returns the first node.
        """
        for child in self.children:
            return child.element
        return SeanoFalseyMarkup('You asked for the first element in a SeanoUnlocalizedHListNode object, but there were no contents at all')

    def __add__(self, other):
        result = self.deep_copy()
        result.merge(other)
        return result

    def merge(self, other):
        for incoming in other.children:
            for check in self.children:
                if check.element.payload == incoming.element.payload:
                    check.element.tags = sorted(set(check.element.tags).union(incoming.element.tags))
                    check.merge(incoming)
                    break
            else:
                self.children.append(incoming.deep_copy())
        return self


class SeanoUnlocalizedHListIterNode(SeanoUnlocalizedHListNode):
    """
    A subclass of ``SeanoUnlocalizedHListNode`` that is designed for more
    convenient iteration.

    Main features:

    - Can stand-in as a normal ``SeanoUnlocalizedHListNode`` object
    - When initialized, performs a deep clone of the original, so that you
      can mutate this copy without mutating the original
    - Cloning this class intentionally returns a ``SeanoUnlocalizedHListNode``
      tree, not a tree of this class
    - Adds some conveneince properties, such as `level`, `num_children`,
      and `note_ids`
    """
    def __init__(self, node, level):
        # Because `node` is a `SeanoUnlocalizedHListNode`, we can assume it
        # has already been sanitized, which means we can skip the expensive
        # sanitizing that `SeanoUnlocalizedHListNode` performs:
        self.element = node.element
        self.children = [__class__(x, level + 1) for x in node.children]
        # Adding in additional behavior:
        self.level = level
        self.num_children = len(node.children)
        self.note_ids = getattr(node.element, 'tags', []) # Not all markup is real (i.e., `SeanoFalseyMarkup`)

    def _walk(self, include_root=False, unroll_recursion=True):
        if include_root:
            yield self
        for child in self.children:
            yield child
            if unroll_recursion:
                for grandchild in child._walk():
                    yield grandchild


def _parse_hlist_node(data, localization, note_id, markup_constructor):
    if isinstance(data, list):
        # either list or hlist (don't care which yet)
        for v in data:
            for result in _parse_hlist_node(data=v, localization=localization, note_id=note_id, markup_constructor=markup_constructor):
                yield result
        return

    if isinstance(data, dict):
        # hlist (convert key/value to element/children)
        for k, v in data.items():
            yield SeanoUnlocalizedHListNode(
                element=markup_constructor(payload=k, localization=localization, tags=[note_id] if note_id else []),
                children=list(_parse_hlist_node(data=v, localization=localization, note_id=note_id, markup_constructor=markup_constructor))
            )
        return

    # all other values are assumed to be markup text, though sometimes Yaml
    # can decide to use other types...  pass the raw value to the markup
    # constructor and hope it works.
    yield SeanoUnlocalizedHListNode(
        element=markup_constructor(payload=data, localization=localization, tags=[note_id] if note_id else []),
        children=None,
    )

def _parse_list_loc_hlist(data, pick_locs, note_id, markup_constructor):
    for item in data:
        for loc in pick_locs:
            if loc in item:
                for result in _parse_hlist_node(
                    data=item[loc],
                    localization=loc,
                    note_id=note_id,
                    markup_constructor=markup_constructor,
                ):
                    yield result
                break
        else:
            yield SeanoFalseyMarkup('Missing localization')


def _parse_loc_hlist(data, pick_locs, note_id, markup_constructor):
    for loc in pick_locs:
        if loc in data:
            return _parse_hlist_node(
                data=data[loc],
                localization=loc,
                note_id=note_id,
                markup_constructor=markup_constructor,
            )
    return SeanoFalseyMarkup('Missing localization')


def _parse_unloc_hlist(data, pick_locs, note_id, markup_constructor):
    return _parse_hlist_node(
        data=data,
        localization=None,
        note_id=note_id,
        markup_constructor=markup_constructor,
    )


SUPPORTED_STRUCTURES = [
    ('-list-loc',   _parse_list_loc_hlist),
    ('-loc-list',   _parse_loc_hlist),
    ('-loc-hlist',  _parse_loc_hlist),
    ('-loc',        _parse_loc_hlist),
    ('',            _parse_unloc_hlist),
]

def seano_get_struct_parser(key):
    key_root, _, markup_language = key.rpartition('-')
    try:
        markup_constructor = SUPPORTED_MARKUP[markup_language]
    except KeyError:
        key_root = key
        markup_constructor = SUPPORTED_MARKUP['']  # plain text

    for suffix, constructor in SUPPORTED_STRUCTURES:
        if key_root.endswith(suffix):
            return lambda **kw: constructor(
                markup_constructor=markup_constructor,
                **kw
            )

    raise SeanoMarkupException('internal error')


def seano_read_hlist(notes, keys, localizations):
    """
    A big, fat, one-stop-shop for reading keys from multiple note objects,
    merging them, enabling you to iterate over them, and encapsulating the
    type of markup used for each fragment.

    Dirty little secret: under the hood, most structures we type into `seano`
    notes are convertable into hlists, even if they aren't officially hlists.
    For example, `*-loc-hlist-*`, `*-list-loc-*`, and `*-loc-*` are all
    readable by this function.  Yes, somewhat confusingly, if you use this
    function to read `example-loc-md`, this function will return an hlist with
    one element, despite that field being a simple localized blob.  In the
    long term, this actually turns out to be useful because it lets you read
    that field from more than one note (the `notes` parameter is a list).
    This behavior also conveniently permits hlist values in fields that expect
    blobs (a developer convenience when writing documentation), without
    forcing the view layer to have two different paths for rendering blobs.

    IMPORTANT: This function is not designed to read a field that is *not*
    some kind of container of rich text markup.

    This function returns a `SeanoUnlocalizedHListNode`` object, which is a
    recursive container that represents the entire hlist, and provides
    developer-friendly iteration tools.

    Due to the schema we've chosen to use in `seano` notes, this function is
    your last chance to choose the desired localization.  The result returned
    from this function is always un-localized, though it does contain memory
    of the localization it came from, for use in embedding in the output
    document.

    `keys` and `localizations` are both treated as priority lists.  The first
    match in any given case will be used.

    `notes` is a list of note objects in which to search.  All of the notes are
    always searched.
    """
    def _inner():
        for note in notes:
            for key in keys:
                if key in note:
                    for hunk in seano_get_struct_parser(key)(
                        note_id   = note.get('id') or None,
                        data      = note[key],
                        pick_locs = localizations,
                    ):
                        if hunk.element:
                            yield SeanoUnlocalizedHListNode(element=None, children=[hunk])
                        else:
                            yield hunk
                    break

    return reduce(lambda a, b: a.merge(b), _inner(), SeanoUnlocalizedHListNode(element=None, children=None))
