#!/usr/bin/env python
"""Module for calling Group related last.fm web services API methods"""

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

from lastfm.base import LastfmBase
from lastfm.mixin import mixin, chartable
from lastfm.decorators import cached_property, depaginate

@chartable('album', 'artist', 'track', 'tag')
@mixin("cacheable", "property_adder")
class Group(LastfmBase):
    """A class representing a group on last.fm."""
    
    class Meta(object):
        properties = ["name"]
    
    def init(self, api, **kwargs):
        """
        Create a Group object by providing all the data related to it.
        
        @param api:    an instance of L{Api}
        @type api:     L{Api}
        @param name:   name of the group on last.fm
        @type name:    L{str}
        
        @raise InvalidParametersError: If an instance of L{Api} is not provided as the first
                                       parameter then an Exception is raised.
        """
        if not isinstance(api, Api):
            raise InvalidParametersError("api reference must be supplied as an argument")
         
        self._api = api
        super(Group, self).init(**kwargs)

    @cached_property
    @depaginate
    def members(self, page = None):
        """
        members of the group
        @rtype: L{lazylist} of L{User}
        """
        params = self._default_params({'method': 'group.getMembers'})
        if page is not None:
            params.update({'page': page})
        data = self._api._fetch_data(params).find('members')
        total_pages = int(data.attrib['totalPages'])
        yield total_pages
        for u in data.findall('user'):
            yield User(
                self._api,
                name = u.findtext('name'),
                real_name = u.findtext('realname'),
                image = dict([(i.get('size'), i.text) for i in u.findall('image')]),
                url = u.findtext('url')
            )
        
    def _default_params(self, extra_params = None):
        if not self.name:
            raise InvalidParametersError("group has to be provided.")
        params = {'group': self.name}
        if extra_params is not None:
            params.update(extra_params)
        return params
    
    @staticmethod
    def _hash_func(*args, **kwds):
        try:
            return hash(kwds['name'])
        except KeyError:
            raise InvalidParametersError("name has to be provided for hashing")

    def __hash__(self):
        return self.__class__._hash_func(name = self.name)

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.name < other.name

    def __repr__(self):
        return "<lastfm.Group: %s>" % self.name

from lastfm.api import Api
from lastfm.error import InvalidParametersError
from lastfm.user import User