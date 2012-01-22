#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

from lastfm.base import LastfmBase
from lastfm.mixin import mixin

@mixin("property_adder")
class Stats(LastfmBase):
    """A class representing the stats of an artist."""
    
    class Meta(object):
        properties = ["listeners", "playcount",
            "tagcount", "count", "match", "rank",
            "weight", "attendance", "reviews"]
        
    def __init__(self, subject, **kwargs):
        self._subject = subject
        super(Stats, self).init(**kwargs)

    @property
    def subject(self):
        """subject of the stats"""
        return self._subject

    def __repr__(self):
        if hasattr(self._subject, 'name'):
            return "<lastfm.Stats: for '%s'>" % self._subject.name
        else:
            return "<lastfm.Stats: for '%s'>" % self._subject
    