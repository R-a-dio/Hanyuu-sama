#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm.util"

from lastfm.util import Wormhole
    
_registry = {}

class ObjectCache(object):
    """The registry to contain all the entities"""
    keys = ['Album', 'Artist', 'Event', 'Location', 'Country', 'Group', 
            'Playlist', 'Shout', 'Tag', 'Track', 'User', 'Venue',
            'WeeklyChart',
            'WeeklyAlbumChart', 'WeeklyArtistChart', 'WeeklyTrackChart', 'WeeklyTagChart',
            'MonthlyChart',
            'MonthlyAlbumChart', 'MonthlyArtistChart', 'MonthlyTrackChart', 'MonthlyTagChart',
            'QuaterlyChart',
            'QuaterlyAlbumChart', 'QuaterlyArtistChart', 'QuaterlyTrackChart', 'QuaterlyTagChart',
            'HalfYearlyChart',
            'HalfYearlyAlbumChart', 'HalfYearlyArtistChart', 'HalfYearlyTrackChart', 'HalfYearlyTagChart',
            'YearlyChart',
            'YearlyAlbumChart', 'YearlyArtistChart', 'YearlyTrackChart', 'YearlyTagChart'
            ]
    
    @staticmethod
    @Wormhole.entrance('lfm-obcache-register')
    def register(ob, key):
        cls_name = ob.__class__.__name__
        if not cls_name in _registry:
            _registry[cls_name] = WeakValueDictionary()
        if key in _registry[cls_name]:
            ob = _registry[cls_name][key]
            #print "already registered: %s" % repr(ob)
            return (ob, True)
        else:
            #print "not already registered: %s" % ob.__class__
            _registry[cls_name][key] = ob
            return (ob, False)

    @property
    def stats(self):
        counts = {}
        for k in ObjectCache.keys:
            if k in _registry:
                counts[k] = len(_registry[k])
            else:
                counts[k] = 0
        return counts
    
    def __getitem__(self, name):
        if name not in ObjectCache.keys:
            raise InvalidParametersError("Key does not correspond to a valid class")
        else:
            if name in _registry:
                return sorted(_registry[name].values())
            else:
                return []
            
    def __repr__(self):
        return "<lastfm.ObjectCache: %s object(s) in cache>" % sum(self.stats.values())

from weakref import WeakValueDictionary
from lastfm.error import InvalidParametersError