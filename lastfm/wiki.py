#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

from lastfm.mixin import mixin

@mixin("property_adder")
class Wiki(object):
    """A class representing the information from the wiki of the subject."""
    
    class Meta(object):
        properties = ["subject", "published", "summary", "content"]
        
    def __init__(self,
                 subject,
                 published = None,
                 summary = None,
                 content = None):
        self._subject = subject
        self._published = published
        self._summary = summary
        self._content = content

    def __repr__(self):
        return "<lastfm.Wiki: for %s '%s'>" % (self.subject.__class__.__name__, self.subject.name)