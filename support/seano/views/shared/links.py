"""
support/seano/views/shared/links.py

Infrastructure to help process links to external servers
"""
import re

github_issue_url_regex = re.compile(r'^https?://github.com/[^/]+/([^/]+)/issues/([0-9]+)$')
jira_url_regex = re.compile(r'^https?://[^/]*jira[^/]*/browse/([A-Z]+\-[0-9]+)$')
redmine_url_regex = re.compile(r'^https?://[^/]*redmine[^/]*/issues/([0-9]+)$')


def get_ticket_display_name(url):
    '''
    Returns the display name of the ticket addressable at the given URL.
    '''
    m = github_issue_url_regex.match(url)
    if m: return '/'.join([m.group(1), m.group(2)])

    m = jira_url_regex.match(url)
    if m: return m.group(1)

    m = redmine_url_regex.match(url)
    if m: return m.group(1)

    raise Exception("Don't know how to parse the given ticket URL: %s" % (url,))
