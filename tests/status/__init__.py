from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import


# Mock the memcache server to a test server
from ..mocking import memcache
try:
    import pylibmc
except ImportError:
    # We don't have the actual pylibmc installed so mock it even uglier.
    # We use a class as module fake here because pylibmc requires C libraries.
    class Mocker(object):
        ClientPool = memcache.MockMemcachePool
    pylibmc = Mocker()


    # Add our fake to the modules list so it gets imported by others
    import sys
    sys.modules['pylibmc'] = pylibmc

    print("WARNING: Using mocked pylibmc with reduced functionality instead.")

# Since we mock both the real and the already mocked Client class we do it here.
pylibmc.Client = memcache.MockMemcacheClient
