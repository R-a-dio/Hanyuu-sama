#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm.mixin"

from lastfm.mixin._cacheable import cacheable
from lastfm.mixin._searchable import searchable
from lastfm.mixin._sharable import sharable
from lastfm.mixin._shoutable import shoutable
from lastfm.mixin._taggable import taggable
from lastfm.mixin._chartable import chartable
from lastfm.mixin._crawlable import crawlable
from lastfm.mixin._propertyadder import property_adder

def mixin(*mixins):
    def wrapper(cls):
        for m in reversed(mixins):
            if m in __all__:
                cls = eval(m)(cls)
        return cls
    return wrapper

__all__ = ['cacheable', 'searchable', 'sharable', 'shoutable', 'taggable'
           'chartable','crawlable', 'property_adder']