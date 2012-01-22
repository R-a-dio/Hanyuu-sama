#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

class Tasteometer(object):
    """A class representing a tasteometer."""
    def __init__(self,
                 score = None,
                 matches = None,
                 artists = None):
        self._score = score
        self._matches = matches
        self._artists = artists

    @property
    def score(self):
        """score of the comparison"""
        return self._score

    @property
    def matches(self):
        """matches for the comparison"""
        return self._matches

    @property
    def artists(self):
        """artists for the comparison"""
        return self._artists
    
    @staticmethod
    def compare(api,
                type1, type2,
                value1, value2,
                limit = None):
        params = {
                  'method': 'tasteometer.compare',
                  'type1': type1,
                  'type2': type2,
                  'value1': value1,
                  'value2': value2
                  }
        if limit is not None:
            params.update({'limit': limit})
        data = api._fetch_data(params).find('comparison/result')
        return Tasteometer(
                           score = float(data.findtext('score')),
                           matches = int(data.find('artists').attrib['matches']),
                           artists = [
                                      Artist(
                                              api,
                                              name = a.findtext('name'),
                                              url = a.findtext('url'),
                                              image = dict([(i.get('size'), i.text) for i in a.findall('image')]),
                                              )
                                      for a in data.findall('artists/artist')
                                      ]
                           )
        
            
    
    def __repr__(self):
        return "<lastfm.Tasteometer: %s%% match>" % (self.score*100)
        
from lastfm.artist import Artist