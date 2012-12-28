from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import time as _time


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