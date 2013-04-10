from collections import namedtuple
import sys
import re
import zlib
import urllib2
import simplejson
from bs4 import BeautifulSoup


UrlResult = namedtuple('UrlResult', ['url', 'headers', 'body'])

CHARSET_RE = re.compile(r'charset=(\S+)')
DEFAULT_ENCODING = 'utf-8'
DEFAULT_CONTENT_TYPE = 'text/plain; charset=%s' % DEFAULT_ENCODING


def fetch_url(url, logger=None):
    """
    Pull down a URL, returning a UrlResult object.

    Attempts to fetch from the cache.
    """
    try:
        opener = urllib2.build_opener()
        opener.addheaders = [
            ('User-Agent', 'THE SourceMap Validator/0.0'),
            ('Accept-Encoding', 'gzip'),  # gzip for the speedz
        ]
        req = opener.open(url)
        headers = req.headers
        body = req.read()
        if headers.get('content-encoding') == 'gzip':
            # Content doesn't *have* to respect the Accept-Encoding header
            # and may send gzipped data regardless.
            # See: http://stackoverflow.com/questions/2423866/python-decompressing-gzip-chunk-by-chunk/2424549#2424549
            body = zlib.decompress(body, 16 + zlib.MAX_WBITS)
        content_type = headers.get('content-type', DEFAULT_CONTENT_TYPE)
        try:
            encoding = CHARSET_RE.search(content_type).group(1)
        except AttributeError:
            encoding = DEFAULT_ENCODING
        body = body.decode(encoding).rstrip('\n')
    except Exception:
        if logger:
            logger.error('Unable to fetch remote source for %r', url, exc_info=True)
        return None

    return UrlResult(url, headers, body)


def fetch_urls(urls):
    if 'gevent' in sys.modules:
        gevent = sys.modules['gevent']
        jobs = [gevent.spawn(fetch_url, url) for url in urls]
        gevent.joinall(jobs)
        return [job.value for job in jobs]
    return map(fetch_url, urls)


def fetch_libs():
    cdnjs = get_cdnjs_libs()
    return [
        {
            'title': 'cdnjs.com',
            'libs': cdnjs,
        }
    ]


def get_cdnjs_libs():
    packages = simplejson.loads(fetch_url('http://cdnjs.com/packages.json').body)['packages']
    packages = filter(lambda pkg: pkg['filename'].endswith('.js'), packages)
    make_url = lambda pkg: (pkg['name'], 'http://cdnjs.cloudflare.com/ajax/libs/%(name)s/%(version)s/%(filename)s' % pkg)
    return map(make_url, packages)
