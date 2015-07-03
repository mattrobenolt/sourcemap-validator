#!/usr/bin/env python
import os
import re
import sourcemap
from os.path import commonprefix
from urlparse import urljoin
from functools import partial
from operator import itemgetter
from werkzeug.routing import Map, Rule

from validator.http import fetch_url, fetch_urls, fetch_libs
from validator.base import Application
from validator.errors import (
    ValidationError, UnableToFetchMinified, UnableToFetchSourceMap,
    UnableToFetchSources, SourceMapNotFound, InvalidSourceMapFormat,
    BrokenComment, UnknownSourceMapError, InvalidLines)
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
    if js.status_code != 200:
        raise UnableToFetchMinified(url)
    make_absolute = partial(urljoin, url)
    smap_url = discover_sourcemap(js)
    if smap_url is None:
        raise SourceMapNotFound(url)
    smap_url = make_absolute(smap_url)
    smap = fetch_url(smap_url)
    if smap.status_code != 200:
        raise UnableToFetchSourceMap(smap_url)
    try:
        return SourceMap(js, smap_url, sourcemap.loads(smap.body))
    except sourcemap.SourceMapDecodeError as e:
        raise UnknownSourceMapError(smap_url, e)
    except ValueError as e:
        raise InvalidSourceMapFormat(smap_url, e)


def sources_from_index(smap, base):
    index = smap.index
    make_absolute = partial(urljoin, base)
    if 'sourcesContent' in index.raw:
        sources = index.raw['sourcesContent']
        return {make_absolute(index.sources[i]): s.splitlines() for i, s in enumerate(sources)}

    sources = fetch_urls(map(make_absolute, index.sources))
    missed_sources = filter(lambda s: s.body is None, sources)
    if missed_sources:
        raise UnableToFetchSources(smap.url, missed_sources)
    return {s.url: s.body.splitlines() for s in sources}


COMMENT_RE = re.compile(r'^(/\*.+?\*/\n?)', re.M | re.S)
WHITESPACE_RE = re.compile(r'^\s*')
prefix_length = lambda line: len(WHITESPACE_RE.match(line).group())
is_blank = lambda line: bool(len(line.strip()))


def generate_report(base, smap, sources):
    make_absolute = partial(urljoin, base)
    errors = []
    warnings = []
    minified = smap.minified.body

    # Here, we're checking out many lines at the top of the minified
    # source are a part of a comment.
    # This is important because people like to inject a comment at the top
    # after generating their SourceMap, fucking everything else up
    try:
        top_comment = COMMENT_RE.match(minified).groups()[0]
    except (AttributeError, TypeError):
        # There wasn't a comment at all, so ignore everything
        bad_lines = 0
    else:
        # If the comment ends in a newline, we can ignore that whole line
        end_with_newline = top_comment.endswith('\n')
        top_comment = top_comment.splitlines()
        bad_lines = len(top_comment) - 1
        if end_with_newline:
            bad_lines += 1

    for token in smap.index:
        if token.name is None:
            continue
        if token.dst_line < bad_lines:
            # lol, the token is referencing a line that is a comment. Derp.
            raise BrokenComment(token)
        src = sources[make_absolute(token.src)]
        try:
            line = src[token.src_line]
        except IndexError:
            raise InvalidLines(token)
        start = token.src_col
        end = start + len(token.name)
        substring = line[start:end]
        # Check for an exact match, or an off-by-one from uglify
        if token.name not in (substring, line[start+1:end+1]):
            if len(line) > 200:
                # This is a good guess that the source file is minified too
                pre_context = []
                post_context = []
                line = line[token.src_col - 5:token.src_col + 50]
            else:
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
                # Note: SourceMap compilers suck.
                warnings.append(bad_token)
            else:
                errors.append(bad_token)

    # Cap results to 1000 each. Anything more than that is just silly
    return {'errors': errors[:1000], 'warnings': warnings[:1000], 'tokens': smap.index}


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
        return self.render('report.html', self.validate(request))

    def validate_json(self, request):
        callback = request.GET.get('callback')
        try:
            data = self.validate(request)
            # We can't encode the tokens, nor do we care
            try:
                del data['report']['tokens']
            except KeyError:
                pass
            return self.json(data, callback=callback)
        except ValidationError as e:
            return self.json({'error': e}, callback=callback)

    def validate(self, request):
        url = request.GET.get('url')
        smap = None
        sources = {}
        try:
            smap = sourcemap_from_url(url)
            sources = sources_from_index(smap, url)
            report = generate_report(url, smap, sources)
        except ValidationError as e:
            report = {
                'errors': [e],
                'warnings': [],
            }
            report['index'] = getattr(smap, 'index', None)

        sources = sources.keys()
        prefix = commonprefix(sources)
        if len(prefix) > 0:
            sources = [s[len(prefix):] for s in sources]
        context = {
            'url': url,
            'report': report,
            'sources_prefix': prefix,
            'sources': sources,
            'sourcemap_url': getattr(smap, 'url', None),
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
        from gevent.pool import Pool
        from gevent import monkey
        monkey.patch_all()
        WSGIServer(('', port), app, spawn=Pool(50)).serve_forever()
