import os
import re
from urlparse import urljoin
from functools import partial
from operator import attrgetter, itemgetter
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.urls import url_decode
from werkzeug.wsgi import SharedDataMiddleware
from http import fetch_url, fetch_urls
from base import Application
import sourcemap
from collections import namedtuple

from gevent import monkey
monkey.patch_all()


BadToken = namedtuple('BadToken', ['token', 'expected', 'line', 'pre', 'post'])


class ValidationError(Exception):
    pass


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
    if js is None:
        raise ValidationError('Unable to fetch %r' % url.encode('utf8'))
    make_absolute = partial(urljoin, url)
    smap_url = discover_sourcemap(js)
    if smap_url is None:
        raise ValidationError('Unable to locate a SourceMap in %r' % url.encode('utf8'))
    smap_url = make_absolute(smap_url)
    smap = fetch_url(smap_url)
    if smap is None:
        raise ValidationError('Unable to fetch %r' % smap_url.encode('utf8'))
    try:
        return sourcemap.loads(smap.body)
    except ValueError:
        raise ValidationError('Invalid SourceMap format %r' % smap_url.encode('utf8'))


def sources_from_index(index, base):
    make_absolute = partial(urljoin, base)
    sources = fetch_urls(map(make_absolute, index.sources))
    return {s.url: s.body.splitlines() for s in sources}


WHITESPACE_RE = re.compile(r'^\s*')
prefix_length = lambda line: len(WHITESPACE_RE.match(line).group())
is_blank = lambda line: bool(len(line.strip()))


def generate_report(base, index, sources):
    make_absolute = partial(urljoin, base)
    errors = []
    warnings = []
    for token in index:
        if token.name is None:
            continue
        src = sources[make_absolute(token.src)]
        line = src[token.src_line]
        start = token.src_col
        end = start + len(token.name)
        substring = line[start:end]
        if substring != token.name:
            pre_context = src[token.src_line - 3:token.src_line]
            post_context = src[token.src_line + 1:token.src_line + 4]
            all_lines = pre_context + post_context + [line]
            common_prefix = reduce(min, map(prefix_length, filter(is_blank, all_lines)))
            if common_prefix > 3:
                trim_prefix = itemgetter(slice(common_prefix, None, None))
                pre_context = map(trim_prefix, pre_context)
                post_context = map(trim_prefix, post_context)
                line = trim_prefix(line)
            bad_token = BadToken(token, substring, line, pre_context, post_context)

            if token.name in line:
                # It at least matched the right line, so just capture a warning
                # Note: Sourcemap compilers suck.
                warnings.append(bad_token)
            else:
                errors.append(bad_token)

    return {'errors': errors, 'warnings': warnings, 'tokens': index}


class Validator(Application):
    def get_urls(self):
        return Map([
            Rule('/', endpoint='index'),
            Rule('/validate', endpoint='validate'),
        ])

    def index(self, request):
        return self.render('index.html')

    def validate(self, request):
        url = url_decode(request.environ['QUERY_STRING']).get('url')
        try:
            index = sourcemap_from_url(url)
            sources = sources_from_index(index, url)
            report = generate_report(url, index, sources)
        except ValidationError, e:
            return self.render('error.html', {'error': e.message})

        context = {
            'report': report,
            'sources': sources.keys(),
        }
        return self.render('report.html', context)


def make_app():
    app = Validator('templates')
    return SharedDataMiddleware(app, {
        '/static':  os.path.join(os.path.dirname(__file__), 'static')
    })


if __name__ == '__main__':
    import sys

    app = make_app()
    port = int(os.environ.get('PORT', 5000))

    if '--debug' in sys.argv:
        from werkzeug.serving import run_simple
        run_simple('', port, app, use_debugger=True, use_reloader=True)
    else:
        from gevent.wsgi import WSGIServer
        WSGIServer(('', port), app).serve_forever()
