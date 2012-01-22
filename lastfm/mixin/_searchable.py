#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm.mixin"

from lastfm.decorators import depaginate

def searchable(cls):
    @classmethod
    @depaginate
    def search(cls,
               api,
               search_item,
               limit = None,
               page = None,
               **kwds):
        from lastfm.api import Api
        cls_name = cls.__name__.lower()
        params = {
                  'method': '%s.search'%cls_name,
                  cls_name: search_item
                  }
        for kwd in kwds:
            if kwds[kwd] is not None:
                params[kwd] = kwds[kwd]

        if limit:
            params.update({'limit': limit})
        if page is not None:
            params.update({'page': page})
        
        data = api._fetch_data(params).find('results')
        total_pages = int(data.findtext("{%s}totalResults" % Api.SEARCH_XMLNS))/ \
                            int(data.findtext("{%s}itemsPerPage" % Api.SEARCH_XMLNS)) + 1
        yield total_pages
        for a in data.findall('%smatches/%s'%(cls_name, cls_name)):
            yield cls._search_yield_func(api, a)

    @staticmethod
    def _search_yield_func(api, search_term):
        raise NotImplementedError("the subclass should implement this method")
    
    cls.search = search
    if not hasattr(cls, '_search_yield_func'):
        cls._search_yield_func = _search_yield_func
        
    if not hasattr(cls, '_mixins'):
            cls._mixins = []
    cls._mixins.append('search')
        
    return cls
