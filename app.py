from werkzeug.wrappers import Request, Response
from urlparse import urljoin
from functools import partial
from operator import attrgetter
from http import fetch_url, fetch_urls
import sourcemap
from collections import namedtuple
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('./templates'))
report_template = env.get_template('report.html')

from gevent import monkey
monkey.patch_all()

# js_source = 'http://code.jquery.com/jquery-1.9.1.min.js'
# js_source = 'http://d3nslu0hdya83q.cloudfront.net/dist/1.0/raven.min.js'
js_source = 'http://getsentry-cdn.s3.amazonaws.com/test/raven.min.js'

BadToken = namedtuple('BadToken', ['token', 'expected', 'line', 'pre', 'post'])


def discover_sourcemap(result):
    """
    Given a UrlResult object, attempt to discover a sourcemap.
    """
    # First, check the header
    smap = result.headers.get('SourceMap', result.headers.get('X-SourceMap'))

    if not smap:
        smap = sourcemap.discover(result.body)
    return smap


def sourcemap_from_url(url):
    js = fetch_url(url)
    make_absolute = partial(urljoin, url)
    smap = fetch_url(make_absolute(discover_sourcemap(js)))
    return sourcemap.loads(smap.body)


@Request.application
def application(request):
    index = sourcemap_from_url(js_source)
    make_absolute = partial(urljoin, js_source)
    sources = {s.url: s.body.splitlines() for s in fetch_urls(map(make_absolute, index.sources))}
    bad_tokens = []
    for token in index:
        if token.name is None:
            continue
        src = sources[make_absolute(token.src)]
        line = src[token.src_line]
        start = token.src_col
        end = start + len(token.name)
        substring = line[start:end]
        if substring != token.name:
            pre_context = src[token.src_line-3:token.src_line]
            post_context = src[token.src_line+1:token.src_line+4]
            bad_tokens.append(BadToken(token, substring, line.decode('utf-8'), pre_context, post_context))

    context = dict(
        errors=bad_tokens,
        all_tokens=index
    )
    return Response(report_template.render(**context), mimetype='text/html')

if __name__ == '__main__':
    from gevent.wsgi import WSGIServer
    import os
    port = int(os.environ.get('PORT', 5000))
    WSGIServer(('', port), application).serve_forever()
