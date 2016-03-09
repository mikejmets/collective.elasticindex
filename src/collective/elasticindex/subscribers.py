import functools

from collective.elasticindex.changes import changes
from Products.CMFCore.utils import getToolByName


def ignore_factorytool(func):
    """Don't call the subscriber if we are in context of a portal_factory.
    """

    @functools.wraps(func)
    def subscriber(content, event):
        factorytool = getToolByName(content, 'portal_factory', None)
        if factorytool is None or factorytool in content.aq_chain:
            return
        return func(content, event)

    return subscriber


@ignore_factorytool
def content_added(content, event):
    if changes.should_index_content(content):
        changes.index_content(content)


@ignore_factorytool
def content_modified(content, event):
    if changes.should_index_content(content):
        changes.index_content(content)


@ignore_factorytool
def content_deleted(content, event):
    if event.newParent is None:
        if changes.should_index_content(content):
            changes.unindex_content(content)


@ignore_factorytool
def content_published(content, event):
    if not changes.only_published:
        return
    if (event.old_state.getId() == 'published' and
        event.new_state.getId() != 'published'):
        changes.unindex_content(content)
    elif (event.new_state.getId() == 'published' and
          event.old_state.getId() != 'published'):
        changes.index_content(content)

@ignore_factorytool
def content_modified_status(content, event):
    changes.index_content(content)

