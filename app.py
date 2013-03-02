from werkzeug.wrappers import Request, Response
import zlib
import urllib2
from urlparse import urljoin
from collections import namedtuple

import gevent
from gevent import monkey
monkey.patch_all()

js_source = 'http://code.jquery.com/jquery-1.9.1.min.js'

UrlResult = namedtuple('UrlResult', ['url', 'headers', 'body'])


def discover_sourcemap(result, logger=None):
    """
    Given a UrlResult object, attempt to discover a sourcemap.
    """
    # When coercing the headers returned by urllib to a dict
    # all keys become lowercase so they're normalized
    sourcemap = result.headers.get('sourcemap', result.headers.get('x-sourcemap'))

    if not sourcemap:
        parsed_body = result.body.splitlines()
        # Source maps are only going to exist at either the top or bottom of the document.
        # Technically, there isn't anything indicating *where* it should exist, so we
        # are generous and assume it's somewhere either in the first or last 5 lines.
        # If it's somewhere else in the document, you're probably doing it wrong.
        if len(parsed_body) > 10:
            possibilities = set(parsed_body[:5] + parsed_body[-5:])
        else:
            possibilities = set(parsed_body)

        for line in possibilities:
            if line.startswith('//@ sourceMappingURL='):
                # We want everything AFTER the indicator, which is 21 chars long
                sourcemap = line[21:].rstrip()
                break

    if sourcemap:
        # fix url so its absolute
        sourcemap = urljoin(result.url, sourcemap)

    return sourcemap


def fetch_url(url, logger=None):
    """
    Pull down a URL, returning a UrlResult object.

    Attempts to fetch from the cache.
    """
    try:
        opener = urllib2.build_opener()
        # opener.addheaders = [('User-Agent', 'Sentry/%s' % sentry.VERSION)]
        req = opener.open(url)
        headers = req.headers
        body = req.read()
        if headers.get('content-encoding') == 'gzip':
            # Content doesn't *have* to respect the Accept-Encoding header
            # and may send gzipped data regardless.
            # See: http://stackoverflow.com/questions/2423866/python-decompressing-gzip-chunk-by-chunk/2424549#2424549
            body = zlib.decompress(body, 16 + zlib.MAX_WBITS)
        body = body.rstrip('\n')
    except Exception:
        if logger:
            logger.error('Unable to fetch remote source for %r', url, exc_info=True)
        return None

    result = UrlResult(url, headers, body)
    return result


def fetch_urls(urls):
    jobs = [gevent.spawn(fetch_url, url) for url in urls]
    gevent.joinall(jobs)
    return [job.value for job in jobs]


def sourcemap_from_url(url):
    js = fetch_url(url)
    sourcemap = discover_sourcemap(js)
    return fetch_url(sourcemap)


@Request.application
def application(request):
    sourcemap = sourcemap_from_url(js_source)
    return Response(sourcemap.body, mimetype='text/plain')

if __name__ == '__main__':
    from gevent.wsgi import WSGIServer
    WSGIServer(('', 4000), application).serve_forever()
