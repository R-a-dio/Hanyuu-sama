from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import


# Mock the memcache server to a test server
from .. import mock
import pylibmc
pylibmc.Client = mock.MockMemcacheClient