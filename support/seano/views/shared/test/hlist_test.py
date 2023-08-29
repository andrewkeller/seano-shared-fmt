import unittest
import yaml

from ..hlist import *
from ..hlist import _parse_hlist_node
from ..markup import SeanoMarkdown, SeanoReStructuredText


def SAMPLE_FILES():
    return list(yaml.load_all('''
alfa-loc-md:
  en-US: foo
alfa-loc-rst:
  en-US: bar
---
alfa-loc-rst:
  en-US: fish

---
bravo-loc-md:
  en-US:
  - cat: bird

---
charlie-list-loc-rst:
- en-US: pineapple
charlie-list-loc-md:
- en-US: apple
---
charlie-loc-list-md:
  en-US:
  - grape
---
charlie-list-loc-rst:
- en-US:
  - peanut: butter

---
delta-loc-list-md:
  en-US: orange

---
echo-loc-hlist-md:
  en-US:
  - macOS:
    - panther
    - tiger
---
echo-loc-hlist-md:
  en-US:
  - macOS:
    - lion
---
echo-loc-hlist-md:
  en-US:
  - linux: ubuntu
''', Loader=yaml.FullLoader))


if 'unittest.util' in __import__('sys').modules:
    # Show full diff in self.assertEqual.
    __import__('sys').modules['unittest.util']._MAX_LENGTH = 999999999


class HlistParsingTests(unittest.TestCase):
    maxDiff = None # Always display full diffs, even with large structures

    def testInitHlistNode(self):
        # Goal: ensure none of these throw
        self.assertFalse(SeanoUnlocalizedHListNode(element=None, children=None))
        self.assertTrue(SeanoUnlocalizedHListNode(element=SeanoMarkdown("hello"), children=None))
        self.assertTrue(SeanoUnlocalizedHListNode(element=None, children=SeanoMarkdown("hello")))
        self.assertTrue(SeanoUnlocalizedHListNode(element=None, children=[SeanoMarkdown("hello")]))
        self.assertTrue(SeanoUnlocalizedHListNode(element=None, children=[SeanoUnlocalizedHListNode(element=SeanoMarkdown("hello"), children=None)]))

    def testHListNodeParser(self):
        self.assertEqual(
            [SeanoUnlocalizedHListNode(element=SeanoMarkdown('hello', localization='en-US', tags=['some-id']), children=None)],
            list(_parse_hlist_node('hello', 'en-US', 'some-id', SUPPORTED_MARKUP['md'])),
        )

        self.assertEqual(
            [SeanoUnlocalizedHListNode(element=SeanoMarkdown('hello', localization='en-US', tags=['some-id']), children=[
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('world', localization='en-US', tags=['some-id']), children=None),
            ])],
            list(_parse_hlist_node({'hello': 'world'}, 'en-US', 'some-id', SUPPORTED_MARKUP['md'])),
        )

        self.assertEqual(
            [SeanoUnlocalizedHListNode(element=SeanoMarkdown('hello', localization='en-US', tags=['some-id']), children=[
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('world', localization='en-US', tags=['some-id']), children=[
                    SeanoUnlocalizedHListNode(element=SeanoMarkdown('again', localization='en-US', tags=['some-id']), children=None),
                ]),
            ])],
            list(_parse_hlist_node({'hello': {'world': 'again'}}, 'en-US', 'some-id', SUPPORTED_MARKUP['md'])),
        )

        self.assertEqual(
            [SeanoUnlocalizedHListNode(element=SeanoMarkdown('hello', localization='en-US', tags=['some-id']), children=None)],
            list(_parse_hlist_node(['hello'], 'en-US', 'some-id', SUPPORTED_MARKUP['md'])),
        )

        self.assertEqual(
            [SeanoUnlocalizedHListNode(element=SeanoMarkdown('hello', localization='en-US', tags=['some-id']), children=[
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('world', localization='en-US', tags=['some-id']), children=None),
            ])],
            list(_parse_hlist_node([{'hello': 'world'}], 'en-US', 'some-id', SUPPORTED_MARKUP['md'])),
        )

        self.assertEqual(
            [SeanoUnlocalizedHListNode(element=SeanoMarkdown('hello', localization='en-US', tags=['some-id']), children=[
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('world', localization='en-US', tags=['some-id']), children=[
                    SeanoUnlocalizedHListNode(element=SeanoMarkdown('again', localization='en-US', tags=['some-id']), children=None),
                ]),
            ])],
            list(_parse_hlist_node([{'hello': {'world': 'again'}}], 'en-US', 'some-id', SUPPORTED_MARKUP['md'])),
        )

        self.assertEqual(
            [
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('hello', localization='en-US', tags=['some-id']), children=[
                    SeanoUnlocalizedHListNode(element=SeanoMarkdown('world', localization='en-US', tags=['some-id']), children=[
                        SeanoUnlocalizedHListNode(element=SeanoMarkdown('again', localization='en-US', tags=['some-id']), children=None),
                    ]),
                ]),
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('goodbye', localization='en-US', tags=['some-id']), children=[
                    SeanoUnlocalizedHListNode(element=SeanoMarkdown('moon', localization='en-US', tags=['some-id']), children=None),
                ]),
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('cat', localization='en-US', tags=['some-id']), children=None),
            ],
            list(_parse_hlist_node([{'hello': {'world': 'again'}}, {'goodbye': 'moon'}, 'cat'], 'en-US', 'some-id', SUPPORTED_MARKUP['md'])),
        )


    def testParseNothing(self):
        # Goal: Prevent subsequent tests from needing to test with empty lists
        self.assertEqual(
            SeanoUnlocalizedHListNode(element=None, children=None),
            seano_read_hlist(notes=[], keys=[], localizations=[]),
        )
        self.assertEqual(
            SeanoUnlocalizedHListNode(element=None, children=None),
            seano_read_hlist(notes=[], keys=[], localizations=['en-US']),
        )
        self.assertEqual(
            SeanoUnlocalizedHListNode(element=None, children=None),
            seano_read_hlist(notes=[], keys=['sample-loc-md'], localizations=['en-US']),
        )

    def testParseBlob_standard(self):
        self.assertEqual(
            SeanoUnlocalizedHListNode(element=None, children=[
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('foo', localization='en-US'), children=None),
                SeanoUnlocalizedHListNode(element=SeanoReStructuredText('fish', localization='en-US'), children=None),
            ]),
            seano_read_hlist(
                notes=SAMPLE_FILES(),
                keys=['alfa-loc-md', 'alfa-loc-rst'],
                localizations=['en-US', 'de-DE'],
            ),
        )

        self.assertEqual(
            SeanoUnlocalizedHListNode(element=None, children=[
                SeanoUnlocalizedHListNode(element=SeanoReStructuredText('bar', localization='en-US'), children=None),
                SeanoUnlocalizedHListNode(element=SeanoReStructuredText('fish', localization='en-US'), children=None),
            ]),
            seano_read_hlist(
                notes=SAMPLE_FILES(),
                keys=['alfa-loc-rst', 'alfa-loc-md'],
                localizations=['en-US', 'de-DE'],
            ),
        )

    def testParseBlob_importFromHList(self):
        self.assertEqual(
            SeanoUnlocalizedHListNode(element=None, children=[
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('foo', localization='en-US'), children=None),
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('cat', localization='en-US'), children=[
                    SeanoUnlocalizedHListNode(element=SeanoMarkdown('bird', localization='en-US'), children=None),
                ]),
            ]),
            seano_read_hlist(
                notes=SAMPLE_FILES(),
                keys=['alfa-loc-md', 'bravo-loc-md'],
                localizations=['en-US', 'de-DE'],
            ),
        )

    def testParseList_standard(self):
        self.assertEqual(
            SeanoUnlocalizedHListNode(element=None, children=[
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('apple', localization='en-US'), children=None),
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('grape', localization='en-US'), children=None),
                SeanoUnlocalizedHListNode(element=SeanoReStructuredText('peanut', localization='en-US'), children=[
                    SeanoUnlocalizedHListNode(element=SeanoReStructuredText('butter', localization='en-US'), children=None),
                ]),
            ]),
            seano_read_hlist(
                notes=SAMPLE_FILES(),
                keys=['charlie-list-loc-md', 'charlie-loc-list-md', 'charlie-list-loc-rst'],
                localizations=['en-US', 'de-DE'],
            ),
        )

    def testParseList_importFromBlob(self):
        self.assertEqual(
            SeanoUnlocalizedHListNode(element=None, children=[
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('grape', localization='en-US'), children=None),
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('orange', localization='en-US'), children=None),
            ]),
            seano_read_hlist(
                notes=SAMPLE_FILES(),
                keys=['charlie-loc-list-md', 'delta-loc-list-md'],
                localizations=['en-US', 'de-DE'],
            ),
        )

    def testParseHList_standard(self):
        self.assertEqual(
            SeanoUnlocalizedHListNode(element=None, children=[
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('macOS', localization='en-US'), children=[
                    SeanoUnlocalizedHListNode(element=SeanoMarkdown('panther', localization='en-US'), children=None),
                    SeanoUnlocalizedHListNode(element=SeanoMarkdown('tiger', localization='en-US'), children=None),
                    SeanoUnlocalizedHListNode(element=SeanoMarkdown('lion', localization='en-US'), children=None),
                ]),
                SeanoUnlocalizedHListNode(element=SeanoMarkdown('linux', localization='en-US'), children=[
                    SeanoUnlocalizedHListNode(element=SeanoMarkdown('ubuntu', localization='en-US'), children=None),
                ]),
            ]),
            seano_read_hlist(
                notes=SAMPLE_FILES(),
                keys=['echo-loc-hlist-md'],
                localizations=['en-US', 'de-DE'],
            ),
        )


if __name__ == '__main__':
    unittest.main()
