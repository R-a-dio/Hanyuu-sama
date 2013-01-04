from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import


# Mock the memcache server to a test server
from .. import mock
try:
    import pylibmc
except ImportError:
    # We don't have the actual pylibmc installed so mock it even uglier.
    class Mocker(object):
        pass
    pylibmc = Mocker()
    import sys
    sys.modules['pylibmc'] = pylibmc

    print("WARNING: Using mocked pylibmc with reduced functionality instead.")

pylibmc.Client = mock.MockMemcacheClient
