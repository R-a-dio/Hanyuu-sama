from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import time as _time
import contextlib


class MockMemcachePool(object):
    """
    A simple not-full-featured-and-not-actually-pooling-thread-safe mock
    version of the pylibmc.ClientPool class to use in testing.
    
    .. warning::
        Please take the comment above serious. This implementation really does
        no actual thinking about thread safety or pooling at all.
    """
    def __init__(self, mc=None, n_slots=None):
        super(MockMemcachePool, self).__init__()
        self.mc = mc
        self.slots = n_slots
        self.used_slots = 0

    def fill(self, mc, n_slots):
        self.mc = mc
        self.slots = n_slots

    @contextlib.contextmanager
    def reserve(self):
        self.used_slots += 1
        if self.used_slots > self.slots:
            print("WARNING: Mocked Memcache Pool went over available slots.")
        yield self.mc
        self.used_slots -= 1


class MockMemcacheClient(object):
    """
    A simple not-full-featured-and-not-thread-safe mock version of the
    pylibmc.Client class to use in testing.
    """
    def __init__(self, *args, **kwargs):
        super(MockMemcacheClient, self).__init__()
        self.keys = dict()

    def get(self, key):
        result = self.keys.get(key)
        if result:
            value, expire = result
            if expire > 0 and expire < int(_time.time()):
                value = None
            return value
        return None

    def get_multi(self, keys, key_prefix=None):
        if key_prefix:
            old_keys = {key_prefix + key for key in keys}
        else:
            old_keys = set(keys)
        intersection = self.keys.viewkeys() & old_keys
        result = dict()
        for key in intersection:
            value = self.get(key)
            if key_prefix and key:
                result[key.lstrip(key_prefix)] = value
            else:
                result[key] = value
        return result

    def set(self, key, value, time=0, min_compress_len=0):
        if time > 0:
            expire = int(_time.time()) + time
        else:
            expire = 0
        self.keys[key] = (value, expire)

    def set_multi(self, mapping, time=0, key_prefix=None):
        if time > 0:
            expire = int(_time.time()) + time
        else:
            expire = 0
        if key_prefix:
            mapping = {(key_prefix + k, (v, expire)) for k, v in mapping.iteritems()}
        self.keys.update(mapping)

    def replace(self, key, value, time=0, min_compress_len=0):
        if self.get(key) is None:
            return
        self.set(key, value, time, min_compress_len)

    def add(self, key, value, time=0, min_compress_len=0):
        if self.get(key) is not None:
            return
        self.set(key, value, time, min_compress_len)

    def clone(self):
        return self
