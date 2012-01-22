#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

from lastfm.base import LastfmBase
from lastfm.mixin import mixin
from lastfm.decorators import cached_property

@mixin("cacheable", "property_adder")
class Shout(LastfmBase):
    """A class representing a shout."""
    
    class Meta(object):
        properties = ["body", "author", "date"]
        
    def init(self, **kwargs):
        super(Shout, self).init(**kwargs)
        
    @staticmethod
    def _hash_func(*args, **kwds):
        try:
            return hash("%s%s" % (kwds['body'], kwds['author']))
        except KeyError:
            raise InvalidParametersError("body and author have to be provided for hashing")

    def __hash__(self):
        return self.__class__._hash_func(body = self.body, author = self.author)

    def __eq__(self, other):
        return (
                self.body == other.body and
                self.author == other.author
            )

    def __lt__(self, other):
        if self.author != other.author:
            return self.author < other.author
        else:
            if self.date != other.date:
                return self.date < other.date
            else:
                return self.body < other.body

    def __repr__(self):
        return "<lastfm.Shout: '%s' by %s>" % (self.body, self.author.name)
    
from lastfm.error import InvalidParametersError
    