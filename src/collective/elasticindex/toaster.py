import json
import logging
import random
import urllib2
from collective.elasticindex.interfaces import IElasticSettings
from Products.CMFPlone.interfaces.siteroot import IPloneSiteRoot
from zope.component import queryUtility, getUtility


def exactQueryES(terms):
    settings = IElasticSettings(getUtility(IPloneSiteRoot))
    query = {
        "query": {
            "filtered": {
                "query": { "match_all": {}
                },
                "filter": {
                    "bool": { "must": terms }
                }
            }
        }
    }
    try:
        headers = {'Content-type': 'application/json', 
                   'Accept': 'text/plain'}
        url = random.choice(settings.get_search_urls())
        response = urllib2.urlopen(url, json.dumps(query))

        if response.msg != 'OK':
            logging.error('exactQueryES: error')
            raise RuntimeError('exactQueryES no OK: return %s' % response.msg)
    except Exception, e:
        logging.error('exactQueryES: exception = %s' % (
                str(e)))
        raise e
    result = json.loads(response.read())
    hits = result['hits']
    total = hits['total']
    if total == 0:
        print result
        return []
    return hits['hits']

def getLayeredTagFromES(uid):
    records = exactQueryES([
                {"term": { "metaType": "bb.toaster.ftlayeredtag" }},
                {"term": { "_id": uid }}
                ])
    if len(records) == 0:
        print result
        raise RuntimeError('_getLayeredTagFromES: UID %s not found' % uid)
    return records[0]['_source']

