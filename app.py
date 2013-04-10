#!/usr/bin/env python
import os
import re
import sourcemap
from urlparse import urljoin
from functools import partial
from operator import attrgetter, itemgetter
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule

from validator.http import fetch_url, fetch_urls, fetch_libs
from validator.base import Application
from validator.errors import (
    ValidationError, UnableToFetchSource, UnableToFetchSourceMap,
    SourceMapNotFound, InvalidSourceMapFormat)
from validator.objects import BadToken, SourceMap


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
        raise UnableToFetchSource(url)
    make_absolute = partial(urljoin, url)
    smap_url = discover_sourcemap(js)
    if smap_url is None:
        raise SourceMapNotFound(url)
    smap_url = make_absolute(smap_url)
    smap = fetch_url(smap_url)
    if smap is None:
        raise UnableToFetchSourceMap(smap_url)
    try:
        return SourceMap(smap_url, sourcemap.loads(smap.body))
    except ValueError:
        raise InvalidSourceMapFormat(smap_url)


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
            Rule('/validate', endpoint='validate_html'),
            Rule('/validate.json', endpoint='validate_json'),
            Rule('/libraries', endpoint='libraries_html'),
            Rule('/libraries.json', endpoint='libraries_json'),
        ])

    def index(self, request):
        return self.render('index.html')

    def libraries_html(self, request):
        return self.render('libraries.html')

    def libraries_json(self, request):
        libs = fetch_libs()
        return self.json(libs, callback=request.GET.get('callback'))

    def validate_html(self, request):
        try:
            return self.render('report.html', self.validate(request))
        except ValidationError, e:
            return self.render('error.html', {'error': e})

    def validate_json(self, request):
        callback = request.GET.get('callback')
        try:
            data = self.validate(request)
            # We can't encode the tokens, nor do we care
            del data['report']['tokens']
            # No need to return back the huge sourcemap
            del data['sourcemap']
            return self.json(data, callback=callback)
        except ValidationError, e:
            return self.json({'error': e}, callback=callback)

    def validate(self, request):
        url = request.GET.get('url')
        smap = sourcemap_from_url(url)
        sources = sources_from_index(smap.index, url)
        report = generate_report(url, smap.index, sources)

        context = {
            'url': url,
            'report': report,
            'sources': sources.keys(),
            'sourcemap_url': smap.url,
            'sourcemap': smap.index.raw,
        }
        return context


def make_app(with_static=True, with_sentry=False):
    app = Validator('templates')
    if with_static:
        from werkzeug.wsgi import SharedDataMiddleware
        app = SharedDataMiddleware(app, {
            '/static': os.path.join(os.path.dirname(__file__), 'static')
        })

    if with_sentry:
        from raven import Client
        from raven.middleware import Sentry
        app = Sentry(app, client=Client())

    return app


if __name__ == '__main__':
    import sys

    is_debug = '--debug' in sys.argv

    app = make_app(with_sentry=not is_debug)
    port = int(os.environ.get('PORT', 5000))

    if is_debug:
        from werkzeug.serving import run_simple
        run_simple('', port, app, use_debugger=True, use_reloader=True)
    else:
        from gevent.wsgi import WSGIServer
        from gevent import monkey
        monkey.patch_all()
        WSGIServer(('', port), app).serve_forever()
