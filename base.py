from werkzeug.wrappers import Request, Response
from werkzeug.exceptions import HTTPException, NotFound
from jinja2 import Environment, FileSystemLoader


class Application(object):
    def __init__(self, template_path):
        self.jinja_env = Environment(loader=FileSystemLoader(template_path), autoescape=True)

        self.routes = self.get_urls()

    def render(self, template_name, context=None):
        context = context or {}
        t = self.jinja_env.get_template(template_name)
        return Response(t.render(context), mimetype='text/html')

    def error_404(self):
        response = self.render('404.html')
        response.status_code = 404
        return response

    def dispatch_request(self, request):
        adapter = self.routes.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, endpoint)(request, **values)
        except NotFound, e:
            return self.error_404()
        except HTTPException, e:
            return e

    def __call__(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)
