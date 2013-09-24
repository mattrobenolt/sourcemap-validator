import simplejson
from werkzeug.wrappers import Request, Response
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.urls import url_decode
from jinja2 import Environment, FileSystemLoader


def json_encoder(o):
    if hasattr(o, '__json__'):
        return o.__json__()
    return None


class Application(object):
    def __init__(self, template_path):
        self.jinja_env = Environment(loader=FileSystemLoader(template_path), autoescape=True)

        self.routes = self.get_urls()

    def render(self, template_name, context=None):
        context = context or {}
        t = self.jinja_env.get_template(template_name)
        return Response(t.render(context), mimetype='text/html')

    def json(self, data, callback=None):
        data = simplejson.dumps(data, default=json_encoder)
        if callback:
            data = '%s(%s)'% (callback, data)
        return Response(data, mimetype='application/json')

    def error_404(self):
        response = self.render('404.html')
        response.status_code = 404
        return response

    def dispatch_request(self, request):
        adapter = self.routes.bind_to_environ(request.environ)
        request.GET = url_decode(request.environ['QUERY_STRING'])
        try:
            endpoint, values = adapter.match()
            return getattr(self, endpoint)(request, **values)
        except NotFound as e:
            return self.error_404()
        except HTTPException as e:
            return e

    def __call__(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)
