class ValidationError(Exception):
    resolutions = ()

    def __json__(self):
        return {'message': self.message, 'resolutions': self.resolutions}


class UnableToFetchSource(ValidationError):
    resolutions = (
        'Is your url correct?',
    )

    def __init__(self, url):
        message = "Unable to fetch <code>%s</code>" % url
        super(UnableToFetchSource, self).__init__(message)


class UnableToFetchSourceMap(UnableToFetchSource):
    resolutions = (
        'SourceMap declaration found, but could not load the file.',
    )


class SourceMapNotFound(ValidationError):
    resolutions = (
        'Add a <code>//@ sourceMappingURL=</code> declaration',
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
