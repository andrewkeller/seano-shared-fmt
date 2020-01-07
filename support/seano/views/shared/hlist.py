"""
support/seano/views/shared/hlist.py

Infrastructure to work with hierarchical lists (hlists)
"""


def seano_cascade_hlist(notes, key):
    '''
    Returns a single merged representation of multiple hierarchal list (``hlist``) structures.

    This function is designed to be used with notes outputted by a seano query.  This function expects that you
    provide it a set of notes, and the name of the key it should look at in each note that contains a single
    ``hlist`` structure per note.  The ``hlist`` structures found in each note are merged, and the result is
    returned.
    '''
    def add_or_append(dst, obj, tag):
        # dst is a recursive structure looking like: {'head': str, 'children': [ ... ]}
        # obj comes from yaml, and may be either a string, or a dict.
        # Goal here is to normalize the data type, and merge like keys.
        if isinstance(obj, dict):
            for head, subheads in obj.items(): # dict used for head/subhead relationship
                node = add_or_append(dst, head, tag)
                for subhead in subheads:
                    add_or_append(node, subhead, tag)
            return
        # Else, must be a str
        for x in dst['children']:
            if x['head'] == obj:
                x['tags'].append(tag)
                return x
        x = {'head': obj, 'tags': [tag], 'children': []}
        dst['children'].append(x)
        return x
    lst = {'children': []}
    tag = 0 # Assuming notes are consistently ordered, tag text using a similarly consistent number
    for n in notes:
        tag = tag + 1 # Always increment tag; tag represents distinct yaml file, even if target audience is missing
        for bullet in (n.get(key, None) or {}).get('en-US', None) or []:
            add_or_append(lst, bullet, tag)
    return lst['children']
