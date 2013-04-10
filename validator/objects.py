class BadToken(object):
    def __init__(self, token, expected, line, pre, post):
        self.token = token
        self.expected = expected
        self.line = line
        self.pre = pre
        self.post = post

    def __json__(self):
        json = self.__dict__.copy()
        del json['token']
        return json


class SourceMap(object):
    def __init__(self, url, index):
        self.url, self.index = url, index

    def __json__(self):
        return self.__dict__
