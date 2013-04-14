class BadToken(object):
    def __init__(self, token, expected, line, pre, post):
        self.token = token
        self.expected = expected
        self.line = line
        self.pre = pre
        self.post = post
        self.start = max(0, token.src_line - len(pre))

    def __json__(self):
        json = self.__dict__.copy()
        del json['token']
        return json


class SourceMap(object):
    def __init__(self, minified, url, index):
        self.minified, self.url, self.index = minified, url, index

    def __json__(self):
        json = self.__dict__.copy()
        del json['minified']
        return json
