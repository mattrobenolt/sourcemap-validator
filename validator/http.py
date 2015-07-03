from collections import namedtuple
import sys
import simplejson
import requests
from bs4 import BeautifulSoup


UrlResult = namedtuple('UrlResult', ['url', 'headers', 'body', 'status_code'])


def fetch_url(url):
    headers = {'User-Agent': 'THE SourceMap Validator/0.0'}

    try:
        response = requests.get(url, headers=headers)
    except Exception:
        return UrlResult(url, None, None, 0)

    if response.status_code != 200:
        return UrlResult(url, None, None, response.status_code)
    return UrlResult(url, response.headers, response.text, response.status_code)


def fetch_urls(urls):
    if 'gevent' in sys.modules:
        gevent = sys.modules['gevent']
        jobs = [gevent.spawn(fetch_url, url) for url in urls]
        gevent.joinall(jobs)
        return [job.value for job in jobs]
    return map(fetch_url, urls)


def fetch_libs():
    if 'gevent' in sys.modules:
        gevent = sys.modules['gevent']
        jobs = [gevent.spawn(get_cdnjs_libs), gevent.spawn(get_google_libs)]
        gevent.joinall(jobs)
        cdnjs = jobs[0].value
        google = jobs[1].value
    else:
        cdnjs = get_cdnjs_libs()
        google = get_google_libs()
    return [
        {
            'title': 'Google CDN',
            'libs': google,
            'url': 'https://developers.google.com/speed/libraries/devguide',
        },
        {
            'title': 'cdnjs.com',
            'libs': cdnjs,
            'url': 'http://cdnjs.com/',
        }
    ]


def get_cdnjs_libs():
    packages = simplejson.loads(fetch_url('http://cdnjs.com/packages.json').body)['packages']
    packages = filter(lambda pkg: pkg.get('filename', '').endswith('.js'), packages)
    make_url = lambda pkg: (pkg['name'], 'http://cdnjs.cloudflare.com/ajax/libs/%(name)s/%(version)s/%(filename)s' % pkg)
    return map(make_url, packages)


def get_google_libs():
    soup = BeautifulSoup(fetch_url('https://developers.google.com/speed/libraries/devguide').body)
    packages = soup.find_all('dl')[3:]
    make_url = lambda pkg: (pkg.dt.text, 'http:' + BeautifulSoup(pkg.dd.code.text).script['src'])
    return map(make_url, packages)
