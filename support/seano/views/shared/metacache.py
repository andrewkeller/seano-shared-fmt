"""
support/seano/views/shared/metacache.py

Infrastructure to help with efficient caching of metadata related to seano schemas
"""
import json


class SeanoMetaCache(object):
    """
    A centralized, portable, transparent caching mechanism for metadata related to seano query data.

    The general concept is that wherever you want a "releases list", use this class instead, and
    functions can set members on this object for caching without you needing to realize that they're
    doing it, or need to manage caching on your own.

    For context, a number of release ancestry analysis functions require deep traversals of the
    release ancestry graph.  Because the release ancestry graph is not large, this isn't terribly
    expensive on the face of it...  until you realize that some views of data perform deep traversals
    for each release, and sometimes multiple times over a range of other fields...  Once you start
    doing deep graph traversals N^2 or N^3 times (and a deep graph traversal itself has N^N
    complexity on its own!), those times begin to add up quickly.

    **WARNING**: Be careful about mutating data saved to this class.  Because random functions cache
    data on this object *(that is the purpose of this class, after all)*, it is conceptually possible
    to make the caches obsolete without properly invalidating them.  If you desire to mutate the data
    on this object, you should generally prefer to make a whole new ``SeanoMetaCache`` object (which
    would have nothing cached), and use that copy to store the new data.  This helps ensure that
    caches stored on a ``SeanoMetaCache`` object are always valid.
    """
    def __init__(self, serialized_seano_query_output_data):
        """
        Initializes a ``SeanoMetaCache`` object.

        Parameters:

        - ``serialized_seano_query_output_data`` (string): The raw data from a seano query output

        This function deserializes the given seano query output data, grabs the releases object, and
        maps the releases list to some commonly used schemas.  When this initializer finishes, the
        following members are set on this class:

        - ``everything``: The top-level dictionary in the seano query output file
        - ``releases``: The original releases list inside the seano query output file
        - ``named_releases``: A copy of the releases list, converted to a dictionary, keyed by the
          names of each release.
        """
        self.everything = json.loads(serialized_seano_query_output_data)
        self.releases = self.everything['releases']
        self.named_releases = {release['name']: release for release in self.releases}
