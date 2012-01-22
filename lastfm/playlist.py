#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

from lastfm.base import LastfmBase
from lastfm.mixin import mixin
from lastfm.decorators import cached_property

@mixin("cacheable", "property_adder")
class Playlist(LastfmBase):
    """A class representing an XPSF playlist."""
    
    class Meta(object):
        properties = ["url"]
    
    def init(self, api, url, **kwargs):
        self._api = api
        self._data = None
        self._url = url

    @cached_property
    def data(self):
        """playlist's data"""
        params = {'method': 'playlist.fetch', 'playlistURL': self._url}
        tmp = StringIO.StringIO()
        ElementTree.ElementTree(self._api._fetch_data(params)[0]).write(tmp)
        return tmp.getvalue()
    
    @staticmethod
    def fetch(api, url):
        return Playlist(api, url = url)
    
    @staticmethod
    def _hash_func(*args, **kwds):
        try:
            return hash(kwds['url'])
        except KeyError:
            raise InvalidParametersError("url has to be provided for hashing")
        
    def __hash__(self):
        return self.__class__._hash_func(url = self.url)
    
    def __eq__(self, other):
        return self.url == other.url
    
    def __lt__(self, other):
        return self.url < other.url
    
    def __repr__(self):
        return "<lastfm.Playlist: %s>" % self.url

import StringIO
import sys
from lastfm.error import InvalidParametersError

if sys.version_info >= (2, 5):
    import xml.etree.cElementTree as ElementTree
else:
    try:
        import cElementTree as ElementTree
    except ImportError:
        try:
            import ElementTree
        except ImportError:
            from error import LastfmError
            raise LastfmError("Install ElementTree package for using python-lastfm")