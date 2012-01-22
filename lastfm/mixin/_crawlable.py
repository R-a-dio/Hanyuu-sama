#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm.mixin"

from lastfm.util import lazylist

def crawlable(cls):
    _get_all = cls._get_all
    @staticmethod
    def get_all(seed):
        seed, hash_attrs, spider_func = _get_all(seed)
        @lazylist
        def gen(lst):
            seen = []
            api = seed._api
            
            def hash_dict(item):
                return dict((a, getattr(item, a)) for a in hash_attrs)
            
            seen.append(hash_dict(seed))
            yield seed
            for hsh in seen:
                for n in spider_func(api, hsh):
                    if hash_dict(n) not in seen:
                        seen.append(hash_dict(n))
                        yield n
        return gen()
    
    cls.get_all = get_all
    delattr(cls, '_get_all')
        
    if not hasattr(cls, '_mixins'):
        cls._mixins = []
    cls._mixins.append('get_all')
    return cls