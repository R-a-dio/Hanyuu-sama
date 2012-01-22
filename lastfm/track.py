#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

from lastfm.base import LastfmBase
from lastfm.mixin import mixin
from lastfm.decorators import cached_property, top_property

@mixin("crawlable", "sharable", "taggable",
    "searchable", "cacheable", "property_adder")
class Track(LastfmBase):
    """A class representing a track."""
    class Meta(object):
        properties = ["id", "name", "mbid", "url", "duration",
            "artist", "image", "stats", "played_on", "loved_on",
            "subject"]
        fillable_properties = ["streamable", "full_track",
            "album", "position", "wiki"]
        
    def init(self, api, **kwargs):
        if not isinstance(api, Api):
            raise InvalidParametersError("api reference must be supplied as an argument")
        self._api = api
        super(Track, self).init(**kwargs)
        self._stats = hasattr(self, "_stats") and Stats(
                             subject = self,
                             match = self._stats.match,
                             playcount = self._stats.playcount,
                             rank = self._stats.rank,
                             listeners = self._stats.listeners,
                            ) or None
        self._wiki = hasattr(self, "_wiki") and Wiki(
                         subject = self,
                         published = self._wiki.published,
                         summary = self._wiki.summary,
                         content = self._wiki.content
                        ) or None
    
    @property
    def wiki(self):
        """wiki of the track"""
        if self._wiki == "na":
            return None
        if self._wiki is None:
            self._fill_info()
        return self._wiki

    @cached_property
    def similar(self):
        """tracks similar to this track"""
        params = Track._check_params(
            {'method': 'track.getSimilar'},
            self.artist.name,
            self.name,
            self.mbid
        )
        data = self._api._fetch_data(params).find('similartracks')
        return [
                Track(
                      self._api,
                      subject = self,
                      name = t.findtext('name'),
                      artist = Artist(
                                      self._api,
                                      subject = self,
                                      name = t.findtext('artist/name'),
                                      mbid = t.findtext('artist/mbid'),
                                      url = t.findtext('artist/url')
                                      ),
                      mbid = t.findtext('mbid'),
                      stats = Stats(
                                    subject = t.findtext('name'),
                                    match = float(t.findtext('match'))
                                    ),
                      streamable = (t.findtext('streamable') == '1'),
                      full_track = (t.find('streamable').attrib['fulltrack'] == '1'),
                      image = dict([(i.get('size'), i.text) for i in t.findall('image')]),
                      )
                for t in data.findall('track')
                ]

    @top_property("similar")
    def most_similar(self):
        """track most similar to this track"""
        pass

    @cached_property
    def top_fans(self):
        """top fans of the track"""
        params = Track._check_params(
                                    {'method': 'track.getTopFans'},
                                    self.artist.name,
                                    self.name,
                                    self.mbid
                                    )
        data = self._api._fetch_data(params).find('topfans')
        return [
                User(
                     self._api,
                     subject = self,
                     name = u.findtext('name'),
                     url = u.findtext('url'),
                     image = dict([(i.get('size'), i.text) for i in u.findall('image')]),
                     stats = Stats(
                                   subject = u.findtext('name'),
                                   weight = int(u.findtext('weight'))
                                   )
                     )
                for u in data.findall('user')
                ]

    @top_property("top_fans")
    def top_fan(self):
        """topmost fan of the track"""
        pass

    @cached_property
    def top_tags(self):
        """top tags for the track"""
        params = Track._check_params(
                                    {'method': 'track.getTopTags'},
                                    self.artist.name,
                                    self.name,
                                    self.mbid
                                    )
        data = self._api._fetch_data(params).find('toptags')
        return [
                Tag(
                    self._api,
                    subject = self,
                    name = t.findtext('name'),
                    url = t.findtext('url'),
                    stats = Stats(
                                  subject = t.findtext('name'),
                                  count = int(t.findtext('count')),
                                  )
                    )
                for t in data.findall('tag')
                ]

    @top_property("top_tags")
    def top_tag(self):
        """topmost tag for the track"""
        pass

    def love(self):
        params = self._default_params({'method': 'track.love'})
        self._api._post_data(params)

    def ban(self):
        params = self._default_params({'method': 'track.ban'})
        self._api._post_data(params)

    @staticmethod
    def get_info(api,
                artist = None,
                track = None,
                mbid = None):
        data = Track._fetch_data(api, artist, track, mbid)
        t = Track(
                  api,
                  name = data.findtext('name'),
                  artist = Artist(
                                  api,
                                  name = data.findtext('artist/name'),
                                  ),
                  )
        t._fill_info()
        return t
    
    @staticmethod
    def _get_all(seed_track):
        def gen():
            for artist in Artist.get_all(seed_track.artist):
                for track in artist.top_tracks:
                    yield track
                    
        return (seed_track, ['name', 'artist'], lambda api, hsh: gen())

    def _default_params(self, extra_params = None):
        if not (self.artist and self.name):
            raise InvalidParametersError("artist and track have to be provided.")
        params = {'artist': self.artist.name, 'track': self.name}
        if extra_params is not None:
            params.update(extra_params)
        return params

    @staticmethod
    def _search_yield_func(api, track):
        return Track(
                     api,
                     name = track.findtext('name'),
                     artist = Artist(
                                     api,
                                     name=track.findtext('artist')
                                     ),
                    url = track.findtext('url'),
                    stats = Stats(
                                  subject=track.findtext('name'),
                                  listeners=int(track.findtext('listeners'))
                                  ),
                    streamable = (track.findtext('streamable') == '1'),
                    full_track = (track.find('streamable').attrib['fulltrack'] == '1'),
                    image = dict([(i.get('size'), i.text) for i in track.findall('image')]),
                    )

    @staticmethod
    def _fetch_data(api,
                artist = None,
                track = None,
                mbid = None):
        params = Track._check_params({'method': 'track.getInfo'}, artist, track, mbid)
        return api._fetch_data(params).find('track')

    def _fill_info(self):
        data = Track._fetch_data(self._api, self.artist.name, self.name)
        self._id = int(data.findtext('id'))
        self._mbid = data.findtext('mbid')
        self._url = data.findtext('url')
        self._duration = int(data.findtext('duration'))
        self._streamable = (data.findtext('streamable') == '1')
        self._full_track = (data.find('streamable').attrib['fulltrack'] == '1')

        self._image = dict([(i.get('size'), i.text) for i in data.findall('image')])
        self._stats = Stats(
                       subject = self,
                       listeners = int(data.findtext('listeners')),
                       playcount = int(data.findtext('playcount')),
                       )
        self._artist = Artist(
                        self._api,
                        name = data.findtext('artist/name'),
                        mbid = data.findtext('artist/mbid'),
                        url = data.findtext('artist/url')
                        )
        if data.find('album') is not None:
            self._album = Album(
                                 self._api,
                                 artist = self._artist,
                                 name = data.findtext('album/title'),
                                 mbid = data.findtext('album/mbid'),
                                 url = data.findtext('album/url'),
                                 image = dict([(i.get('size'), i.text) for i in data.findall('album/image')])
                                 )
            self._position = data.find('album').attrib['position'].strip() \
                and int(data.find('album').attrib['position'])
        if data.find('wiki') is not None:
            self._wiki = Wiki(
                         self,
                         published = datetime(*(time.strptime(
                                                              data.findtext('wiki/published').strip(),
                                                              '%a, %d %b %Y %H:%M:%S +0000'
                                                              )[0:6])),
                         summary = data.findtext('wiki/summary'),
                         content = data.findtext('wiki/content')
                         )
        else:
            self._wiki = 'na'

    @staticmethod
    def _check_params(params,
                      artist = None,
                      track = None,
                      mbid = None):
        if not ((artist and track) or mbid):
            raise InvalidParametersError("either (artist and track) or mbid has to be given as argument.")

        if artist and track:
            params.update({'artist': artist, 'track': track})
        elif mbid:
            params.update({'mbid': mbid})
        return params

    @staticmethod
    def _hash_func(*args, **kwds):
        try:
            return hash("%s%s" % (kwds['name'], hash(kwds['artist'])))
        except KeyError:
            raise InvalidParametersError("name and artist have to be provided for hashing")

    def __hash__(self):
        return self.__class__._hash_func(name = self.name, artist = self.artist)

    def __eq__(self, other):
        if self.mbid and other.mbid:
            return self.mbid == other.mbid
        if self.url and other.url:
            return self.url == other.url
        if (self.name and self.artist) and (other.name and other.artist):
            return (self.name == other.name) and (self.artist == other.artist)
        return super(Track, self).__eq__(other)

    def __lt__(self, other):
        return self.name < other.name

    def __repr__(self):
        return "<lastfm.Track: '%s' by %s>" % (self.name, self.artist.name)

import time
from datetime import datetime

from lastfm.api import Api
from lastfm.artist import Artist
from lastfm.album import Album
from lastfm.error import InvalidParametersError
from lastfm.stats import Stats
from lastfm.tag import Tag
from lastfm.user import User
from lastfm.wiki import Wiki
