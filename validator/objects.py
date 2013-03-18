from collections import namedtuple


BadToken = namedtuple('BadToken', ['token', 'expected', 'line', 'pre', 'post'])
