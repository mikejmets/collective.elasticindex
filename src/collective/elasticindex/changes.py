
import logging
import re
import threading
import urlparse

from AccessControl.PermissionRole import rolesForPermissionOn
from Acquisition import aq_base
from plone import api
from plone.i18n.normalizer.base import mapUnicode
from Products.CMFCore.CatalogTool import _mergedLocalRoles
from Products.CMFCore.interfaces import IFolderish, IContentish
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.interfaces.siteroot import IPloneSiteRoot
from Products.CMFPlone.utils import safe_unicode
from transaction.interfaces import ISavepointDataManager, IDataManagerSavepoint
from zope.component import queryUtility
from zope.interface import implements
import transaction

from collective.elasticindex.interfaces import IElasticSettings
from collective.elasticindex.toaster import getLayeredTagFromES
from collective.elasticindex.utils import connect

logger = logging.getLogger('collective.elasticindex')

num_sort_regex = re.compile('\d+')

def sortable_string(string):
    return num_sort_regex.sub(
        lambda m: m.group().zfill(6),
        mapUnicode(safe_unicode(string)).lower().strip())

def get_uid(content):
    """Return content identifier to use in ES.
    """
    if IPloneSiteRoot.providedBy(content):
        uid = 'root'
    else:
        uid = content.UID()
    return uid or None

def get_security(content):
    """Return a list of roles and users with View permission.
    Used to filter out items you're not allowed to see.
    """
    allowed = set(rolesForPermissionOn('View', content))
    # shortcut roles and only index the most basic system role if the object
    # is viewable by either of those
    if 'Anonymous' in allowed:
        return ['Anonymous']
    elif 'Authenticated' in allowed:
        return ['Authenticated']
    try:
        acl_users = getToolByName(content, 'acl_users', None)
        if acl_users is not None:
            local_roles = acl_users._getAllLocalRoles(content)
    except AttributeError:
        local_roles = _mergedLocalRoles(content)
    for user, roles in local_roles.items():
        for role in roles:
            if role in allowed:
                allowed.add('user:' + user)
    if 'Owner' in allowed:
        allowed.remove('Owner')
    return list(allowed)

def get_data(content, security=False, domain=None):
    """Return data to index in ES.
    """
    uid = get_uid(content)
    if not uid:
        return None, None
    title = content.Title()
    try:
        text = content.SearchableText()
    except:
        text = title
    url = content.absolute_url()
    if domain:
        parts = urlparse.urlparse(url)
        url = urlparse.urlunparse((parts[0], domain) + parts[2:])

    data = {'title': title,
            'contentId': content.id,
            'metaType': content.portal_type,
            'sortableTitle': sortable_string(title),
            'description': content.Description(),
            'subject': content.Subject(),
            'contributors': content.Contributors(),
            'url': url,
            'path': '/'.join(content.getPhysicalPath()),
            'author': content.Creator(),
            'content': text}
    if content.portal_type in (
            'bb.toaster.audioartefact', 'bb.toaster.documentartefact', 
            'bb.toaster.otherartefact', 'bb.toaster.videoartefact'):
        tags = []
        data['categoryIds'] = []
        data['categoryTitles']= []
        data['layeroneIds']= []
        data['layeroneTitles']= []
        data['layertwoIds']= []
        data['layertwoTitles']= []
        data['layerthreeIds']= []
        data['layerthreeTitles']= []
        data['layerfourIds']= []
        data['layerfourTitles']= []
        data['layerfiveIds']= []
        data['layerfiveTitles']= []
        for tag in content.taglist:
            record = getLayeredTagFromES(tag)
            titleList = record['title'].split('_')
            idList = record['contentId'].split('_')
            data['categoryIds'].append(idList[0])
            data['categoryTitles'].append(titleList[0])
            if len(titleList) > 1:
                data['layeroneIds'].append(idList[1])
                data['layeroneTitles'].append(titleList[1])
            else:
                data['layeroneIds'].append('')
                data['layeroneTitles'].append('')
            if len(titleList) > 2:
                data['layertwoIds'].append(idList[2])
                data['layertwoTitles'].append(titleList[2])
            else:
                data['layertwoIds'].append('')
                data['layertwoTitles'].append('')
            if len(titleList) > 3:
                data['layerthreeIds'].append(idList[3])
                data['layerthreeTitles'].append(titleList[3])
            else:
                data['layerthreeIds'].append('')
                data['layerthreeTitles'].append('')
            if len(titleList) > 4:
                data['layerfourIds'].append(idList[4])
                data['layerfourTitles'].append(titleList[4])
            else:
                data['layerfourIds'].append('')
                data['layerfourTitles'].append('')
            if len(titleList) > 5:
                data['layerfiveIds'].append(idList[5])
                data['layerfiveTitles'].append(titleList[5])
            else:
                data['layerfiveIds'].append('')
                data['layerfiveTitles'].append('')

            #for i in range(len(titleList)):
            #    tags.append(titleList[i])
            #    if i == 0:
            #        data['categoryIds'].append(idList[i])
            #        data['categoryTitles'].append(titleList[i])
            #    elif i == 1:
            #        data['layeroneIds'].append(idList[i])
            #        data['layeroneTitles'].append(titleList[i])
            #    elif i == 2:
            #        data['layertwoIds'].append(idList[i])
            #        data['layertwoTitles'].append(titleList[i])
            #    elif i == 3:
            #        data['layerthreeIds'].append(idList[i])
            #        data['layerthreeTitles'].append(titleList[i])
            #    elif i == 4:
            #        data['layerfourIds'].append(idList[i])
            #        data['layerfourTitles'].append(titleList[i])
            #    elif i == 5:
            #        data['layerfiveIds'].append(idList[i])
            #        data['layerfiveTitles'].append(titleList[i])
        data['tags'] = tags
        data['superclass'] = 'artefact'
        kws = []
        ftkeywords = content.ftkeywords
        if ftkeywords is not None and len(ftkeywords) > 0:
            kws = ftkeywords.split(",")
            kws = [kw.strip() for kw in kws]
            kws = [kw for kw in kws if len(kw) > 0]
        data['keywords'] = kws
        data['format'] = content.getFTFormat()
        data['taglist'] = content.taglist

    elif content.portal_type == 'bb.toaster.ftlayeredtag':
        data['catId'] = content.category.to_object.id
        data['catTitle'] = content.category.to_object.title
        if content.one:
            data['oneId'] = content.one.to_object.id
            data['oneTitle'] = content.one.to_object.title
        if content.two:
            data['twoId'] = content.two.to_object.id
            data['twoTitle'] = content.two.to_object.title
        if content.three:
            data['threeId'] = content.three.to_object.id
            data['threeTitle'] = content.three.to_object.title
        if content.four:
            data['fourId'] = content.four.to_object.id
            data['fourTitle'] = content.four.to_object.title
        if content.five:
            data['fiveId'] = content.five.to_object.id
            data['fiveTitle'] = content.five.to_object.title

    elif content.portal_type == 'bb.toaster.ftlayer':
        data['level'] = content.level

    if security:
        data['authorizedUsers'] = get_security(content)

    if hasattr(aq_base(content), 'pub_date_year'):
        data['publishedYear'] = getattr(content, 'pub_date_year')

    created = content.created()
    if created is not (None, 'None'):
        data['created'] = created.strftime('%Y-%m-%dT%H:%M:%S')

    modified = content.modified()
    if modified is not (None, 'None'):
        data['modified'] = modified.strftime('%Y-%m-%dT%H:%M:%S')

    return uid, data

def list_content(content, callback):
    """Recursively list CMF content out of the given one. ``callback``
    is called every thousand items after a commit.
    """

    def recurse(content):
        for child in content.contentValues():
            if IFolderish.providedBy(child):
                for grandchild in recurse(child):
                    yield grandchild
            yield child

    count = 0
    total = 0
    if IFolderish.providedBy(content):
        for child in recurse(content):
            yield child
            count += 1
            total += 1
            if count > 200:
                logger.info('{0} items indexed'.format(total))
                transaction.commit()
                content._p_jar.cacheGC()
                callback()
                count = 0
        yield content
    elif IContentish.providedBy(content):
        yield content


class ElasticSavepoint(object):
    implements(IDataManagerSavepoint)

    def __init__(self, manager, index, unindex):
        self.manager = manager 
        self._index = index.copy()
        self._unindex = set(unindex)

    def rollback(self):
        self.manager._index = self._index
        self.manager._unindex = self._unindex


class ElasticChanges(threading.local):
    implements(ISavepointDataManager)

    def __init__(self, manager):
        self.manager = manager
        self._clear()

    def _clear(self):
        self._index = dict()
        self._unindex = set()
        self._settings = None
        self._connection = None
        self._activated = None
        self._get_status = None

    def _get_settings(self):
        if self._settings is None:
            portal = queryUtility(IPloneSiteRoot)
            if portal is None:
                return None
            self._settings = IElasticSettings(portal)
            if self._settings.only_published:
                self._get_status = getToolByName(
                    portal, 'portal_workflow').getInfoFor
        return self._settings

    @property
    def only_published(self):
        settings = self._get_settings()
        if settings is None:
            return False
        return self._settings.only_published

    def _is_activated(self):
        if self._activated is None:
            settings = self._get_settings()
            if settings is None:
                return False
            self._activated = bool(settings.activated)
            if self._activated:
                transaction = self.manager.get()
                transaction.join(self)
        return bool(self._activated)

    def should_index_content(self, content):
        if not self._is_activated():
            return False
        if self._get_status is None:
            return True
        return self._get_status(
            content, 'review_state', default='nope') == 'published'

    def should_index_container(self, contents):
        if self._is_activated():
            for content in contents:
                if (self._get_status is None or
                    self._get_status(
                        content, 'review_state', default='nope') == 'published'):
                    yield content

    def verify_and_index_container(self, content):
        if not self._is_activated():
            return
        for item in self.should_index_container(
            list_content(content, self._is_activated)):
            uid, data = get_data(item, security=self._settings.index_security,
                                 domain=self._settings.normalize_domain_name)
            if data:
                if uid in self._unindex:
                    self._unindex.remove(uid)
                self._index[uid] = data

    def index_content(self, content):
        if not self._is_activated():
            return
        uid, data = get_data(content, security=self._settings.index_security,
                             domain=self._settings.normalize_domain_name)
        if data:
            if uid in self._unindex:
                self._unindex.remove(uid)
            self._index[uid] = data

    def unindex_content(self, content):
        if not self._is_activated():
            return
        uid = get_uid(content)
        if uid in self._index:
            del self._index[uid]
        self._unindex.add(uid)

    def savepoint(self):
        return ElasticSavepoint(self, self._index, self._unindex)

    def commit(self, transaction):
        pass

    def sortKey(self):
        return 'Z' * 100

    def abort(self, transaction):
        self._clear()

    def tpc_begin(self, transaction):
        pass

    def tpc_vote(self, transaction):
        if self._index or self._unindex:
            settings = self._get_settings()
            if settings.server_urls:
                self._connection = connect(settings.server_urls)

    def tpc_finish(self, transaction):
        if self._connection is not None:
            settings = self._get_settings()
            for uid, data in self._index.iteritems():
                try:
                    self._connection.index(
                        data,
                        settings.index_name,
                        'document',
                        id=uid,
                        bulk=True)
                except:
                    errormsg = 'Error while indexing document {0} in Elasticsearch'.format(uid)
                    logger.exception(errormsg)
            for uid in self._unindex:
                try:
                    self._connection.delete(
                        settings.index_name,
                        'document',
                        uid,
                        bulk=True)
                except:
                    errormsg = 'Error while unindexing document {0} in Elasticsearch'.format(uid)
                    logger.exception(errormsg)
            if self._index or self._unindex:
                try:
                    self._connection.flush_bulk(True)
                except:
                    logger.exception(
                        'Error while flushing changes to Elasticsearch')
        self._clear()

    def tpc_abort(self, transaction):
        self._clear()


changes = ElasticChanges(transaction.manager)
