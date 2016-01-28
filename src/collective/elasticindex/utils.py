
import pyes
import urlparse

ANALYZED_STRING_MAPPING = {
    'index': 'analyzed',
    'type': 'string',
    'store': 'yes'
}

STORED_STRING_MAPPING = {
    'index': 'not_analyzed',
    'type': 'string',
    'store': 'yes',
}

STRING_MAPPING = {
    'index': 'not_analyzed',
    'type': 'string',
    'store': 'no',
}

DATE_MAPPING = {
    'index': 'not_analyzed',
    'type': 'date',
    'store': 'no'
}

INT_MAPPING = {
    'index': 'not_analyzed',
    'type': 'integer',
    'store': 'no'
}

BLOB_MAPPING = {
    'type': 'binary'
}

DOCUMENT_MAPPING = {
    '_index': {
        'enabled': True
    },
    # Stored
    'title': ANALYZED_STRING_MAPPING,
    'subject': ANALYZED_STRING_MAPPING,
    'description': ANALYZED_STRING_MAPPING,
    'content': ANALYZED_STRING_MAPPING,
    'author': ANALYZED_STRING_MAPPING,
    'contributors': ANALYZED_STRING_MAPPING,

    # Not analyzed
    '_id' : STORED_STRING_MAPPING,
    'contentId': STORED_STRING_MAPPING,
    'url': STORED_STRING_MAPPING,
    'metaType': STORED_STRING_MAPPING,

    # Not stored
    'created': DATE_MAPPING,
    'modified': DATE_MAPPING,
    'publishedYear': INT_MAPPING,
    'sortableTitle': STRING_MAPPING,
    'authorizedUsers': STRING_MAPPING,
    'categoryIds': STRING_MAPPING,
    'layeroneIds': STRING_MAPPING,
    'layertwoIds': STRING_MAPPING,
    'layerthreeIds': STRING_MAPPING,
    'layerfourIds': STRING_MAPPING,
    'layerfiveIds': STRING_MAPPING,
    'path': STRING_MAPPING,
    'taglist': STRING_MAPPING,
    'catId': STRING_MAPPING,
    'catTitle': STRING_MAPPING,
    'oneId': STRING_MAPPING,
    'oneTitle': STRING_MAPPING,
    'twoId': STRING_MAPPING,
    'twoTitle': STRING_MAPPING,
    'threeId': STRING_MAPPING,
    'threeTitle': STRING_MAPPING,
    'fourId': STRING_MAPPING,
    'fourTitle': STRING_MAPPING,
    'fiveId': STRING_MAPPING,
    'fiveTitle': STRING_MAPPING,
    'level': STRING_MAPPING,
    'categoryId': STRING_MAPPING,

    # Blobs
    'icon': BLOB_MAPPING,
}

def parse_url(url):
    info = urlparse.urlparse(url)
    if ':' in info.netloc:
        url, port = info.netloc.split(':', 1)
    else:
        port = 80
        if info.scheme == 'https':
            port = 443
        url = info.netloc
    return 'http', url, int(port)


def connect(urls):
    try:
        return pyes.ES(map(parse_url, urls))
    except:
        raise ValueError('Cannot connect to servers')


def create_index(settings):
    connection = connect(settings.server_urls)
    connection.indices.create_index_if_missing(settings.index_name)
    connection.indices.put_mapping(
        'document', {'properties' : DOCUMENT_MAPPING}, [settings.index_name])


def delete_index(settings):
    connection = connect(settings.server_urls)
    connection.indices.delete_index_if_exists(settings.index_name)
