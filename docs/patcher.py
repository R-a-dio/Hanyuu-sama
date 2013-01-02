"""
Module to patch the hanyuu package so it is suitable for extracting
documentation.
"""
import sys

class Mock(object):
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return Mock()

    @classmethod
    def __getattr__(cls, name):
        if name in ('__file__', '__path__'):
            return '/dev/null'
        elif name[0] == name[0].upper():
            mockType = type(name, (), {})
            mockType.__module__ = __name__
            return mockType
        else:
            return Mock()

MOCK_MODULES = ['flup', 'flup.server', 'flup.server.fcgi',
                'pylibshout', 'pylibmc', 'audiotools']
for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = Mock()
    
    
import tests # This patches the configuration module

# Pop the first path value because the `tests` import adds something.
sys.path.pop(0)

import hanyuu.utils

# Monkey patch the instance decorator to just return the class.
# This prevents the actual class objects to disappear from the
# view of sphinx.
hanyuu.utils.instance_decorator = lambda cls: cls