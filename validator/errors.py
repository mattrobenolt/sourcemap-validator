class ValidationError(Exception):
    resolutions = ()


class UnableToFetchSource(ValidationError):
    resolutions = (
        'Is your url correct?',
    )
    def __init__(self, url):
        message = "Unable to fetch '%s'" % url
        super(UnableToFetchSource, self).__init__(message)


class UnableToFetchSourceMap(UnableToFetchSource):
    resolutions = (
        'SourceMap declaration found, but could not load the file.',
    )


class SourceMapNotFound(ValidationError):
    resolutions = (
        '//@ sourceMappingURL=',
        'SourceMap header'
    )
    def __init__(self, url):
        message = "Unable to locate a SourceMap in '%s'" % url
        super(SourceMapNotFound, self).__init__(message)


class InvalidSourceMapFormat(ValidationError):
    resolutions = (
        'Everything is broken. Is this really a sourcemap?',
    )
    def __init__(self, url):
        message = "Invalid SourceMap format '%s'" % url
        super(InvalidSourceMapFormat, self).__init__(message)
