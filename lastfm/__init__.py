#!/usr/bin/env python
"""
A python interface to the last.fm web services API at
U{http://ws.audioscrobbler.com/2.0}.
See U{the official documentation<http://www.last.fm/api/intro>}
of the web service API methods for more information.
"""

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lastfm.album import Album
from lastfm.api import Api
from lastfm.artist import Artist
from lastfm.error import LastfmError
from lastfm.event import Event
from lastfm.geo import Location, Country
from lastfm.group import Group
from lastfm.playlist import Playlist
from lastfm.util import ObjectCache
from lastfm.tag import Tag
from lastfm.tasteometer import Tasteometer
from lastfm.track import Track
from lastfm.user import User
from lastfm.venue import Venue
from lastfm.shout import Shout

__all__ = ['LastfmError', 'Api', 'Album', 'Artist', 'Event',
           'Location', 'Country', 'Group', 'Playlist', 'Tag',
           'Tasteometer', 'Track', 'User', 'Venue', 'ObjectCache']