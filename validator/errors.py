class ValidationError(Exception):
    resolutions = ()

    def __json__(self):
        return {'message': self.message, 'resolutions': self.resolutions}


class UnableToFetch(ValidationError):
    def __init__(self, url):
        message = "Unable to fetch <code>%s</code>" % url
        super(UnableToFetch, self).__init__(message)


class UnableToFetchMinified(UnableToFetch):
    resolutions = (
        'Is your url correct?',
    )


class UnableToFetchSourceMap(UnableToFetch):
    resolutions = (
        'SourceMap declaration found, but could not load the file.',
    )


class UnableToFetchSources(ValidationError):
    def __init__(self, smap_url, urls):
        message = "Unable to fetch sources in <code>%s</code>" % smap_url
        resolutions = [
            "Error: <a href='%s'>%s</a> (%d)" % (u.url, u.url, u.status_code)
            for u in urls]
        self.resolutions = tuple(resolutions)
        super(UnableToFetchSources, self).__init__(message)


class SourceMapNotFound(ValidationError):
    resolutions = (
        'Add a <code>//# sourceMappingURL=</code> declaration',
        'Add a SourceMap HTTP response header'
    )

    def __init__(self, url):
        message = "Unable to locate a SourceMap in <code>%s</code>" % url
        super(SourceMapNotFound, self).__init__(message)


class InvalidSourceMapFormat(ValidationError):
    resolutions = (
        'Everything is broken. Is this really a SourceMap?',
    )

    def __init__(self, url):
        message = "Invalid SourceMap format <code>%s</code>" % url
        super(InvalidSourceMapFormat, self).__init__(message)


class BrokenComment(ValidationError):
    resolutions = (
        'Don\'t insert a comment at the top of the minified file after the SourceMap is generated.',
        'It\'s only safe to append to the bottom.',
    )

    def __init__(self, token):
        message = "Broken Minification"
        super(BrokenComment, self).__init__(message)


class UnknownSourceMapError(ValidationError):
    resolutions = (
        'Something is really broken, and I can\'t provide any advice. :(',
    )

    def __init__(self, url=None):
        message = "Your SourceMap is really broken."
        super(UnknownSourceMapError, self).__init__(message)


class InvalidLines(ValidationError):
    resolutions = (
        'Your sourcemap is referencing a line that does not exist.',
    )

    def __init__(self, token):
        message = "SourceMap thinks that line %d of <code>%s</code> is a thing, but it's not." % (token.src_line + 1, token.src)
        super(InvalidLines, self).__init__(message)
