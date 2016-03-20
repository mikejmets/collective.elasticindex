
from Acquisition import aq_base
from collective.elasticindex import SERVER_URLS
from Products.CMFCore.interfaces import IPropertiesTool
from zope.component import getUtility


class EmptySettings(object):
    only_published = True
    index_security = False
    index_name = None
    server_urls = []
    public_server_urls = []
    public_through_plone = False
    normalize_domain_name = None


class SettingsAdapter(object):

    def __init__(self, context):
        self._id = context.getId()
        properties = getUtility(IPropertiesTool)
        self._activated = hasattr(
            aq_base(properties),
            'elasticindex_properties')
        if self._activated:
            self._properties = properties.elasticindex_properties
        else:
            self._properties = EmptySettings()

    def get_search_urls(self):
        return map(lambda u: '/'.join((u, self.index_name, '_search')),
                    SERVER_URLS)

    @property
    def activated(self):
        return self._activated

    @apply
    def only_published():

        def getter(self):
            return bool(self._properties.only_published)

        def setter(self, value):
            self._properties.only_published = bool(value)
            return value

        return property(getter, setter)

    @apply
    def index_security():

        def getter(self):
            return bool(self._properties.index_security)

        def setter(self, value):
            self._properties.index_security = bool(value)
            return value

        return property(getter, setter)

    @apply
    def index_name():

        def getter(self):
            if self._properties.index_name:
                return self._properties.index_name
            return self._id

        def setter(self, value):
            self._properties.index_name = value
            return value

        return property(getter, setter)

    @apply
    def normalize_domain_name():

        def getter(self):
            return self._properties.normalize_domain_name or None

        def setter(self, value):
            if value:
                self._properties.normalize_domain_name = value
            else:
                self._properties.normalize_domain_name = None
            return self._properties.normalize_domain_name

        return property(getter, setter)

    @apply
    def server_urls():

        def getter(self):
            return SERVER_URLS

        def setter(self, value):
            self._properties.server_urls = tuple(value)
            return SERVER_URLS

        return property(getter, setter)

    @apply
    def public_server_urls():

        def getter(self):
            return self._properties.public_server_urls

        def setter(self, value):
            self._properties.public_server_urls = tuple(value)
            return self._properties.public_server_urls

        return property(getter, setter)

    @apply
    def public_through_plone():

        def getter(self):
            return bool(self._properties.public_through_plone)

        def setter(self, value):
            self._properties.public_through_plone = bool(value)
            return value

        return property(getter, setter)
