#!/usr/bin/env python
"""Module for calling Artist related last.fm web services API methods"""

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

from lastfm.base import LastfmBase
from lastfm.mixin import mixin
from lastfm.decorators import cached_property, top_property

@mixin("crawlable", "shoutable", "sharable",
    "taggable", "searchable", "cacheable", "property_adder")
class Artist(LastfmBase):
    """A class representing an artist."""
    class Meta(object):
        properties = ["name", "similar", "top_tags"]
        fillable_properties = ["mbid", "url", "image",
            "streamable", "stats", "bio"]
        
    def init(self, api, subject = None, **kwargs):
        """
        Create an Artist object by providing all the data related to it.
        
        @param api:             an instance of L{Api}
        @type api:              L{Api}
        @param name:            the artist name
        @type name:             L{str}
        @param mbid:            MBID of the artist
        @type mbid:             L{str}
        @param url:             URL of the artist on last.fm
        @type url:              L{str}
        @param image:           the images of the artist in various sizes
        @type image:            L{dict}
        @param streamable:      flag indicating if the artist is streamable from last.fm
        @type streamable:       L{bool}
        @param stats:           the artist statistics
        @type stats:            L{Stats}
        @param similar:         artists similar to the provided artist
        @type similar:          L{list} of L{Artist}
        @param top_tags:        top tags for the artist
        @type top_tags:         L{list} of L{Tag}
        @param bio:             biography of the artist
        @type bio:              L{Wiki}
        @param subject:         the subject to which this instance belongs to
        @type subject:          L{User} OR L{Artist} OR L{Tag} OR L{Track} OR L{WeeklyChart}
        
        @raise InvalidParametersError: If an instance of L{Api} is not provided as the first
                                       parameter then an Exception is raised.
        """
        if not isinstance(api, Api):
            raise InvalidParametersError("api reference must be supplied as an argument")
        
        self._api = api
        super(Artist, self).init(**kwargs)
        self._stats = hasattr(self, "_stats") and Stats(
            subject = self,
            listeners = self._stats.listeners,
            playcount = self._stats.playcount,
            weight = self._stats.weight,
            match = self._stats.match,
            rank = self._stats.rank
        ) or None
        self._bio = hasattr(self, "_bio") and Wiki(
            subject = self,
            published = self._bio.published,
            summary = self._bio.summary,
            content = self._bio.content
        ) or None
        self._subject = subject

    def get_similar(self, limit = None):
        """
        Get the artists similar to this artist.
        
        @param limit: the number of artists returned (optional)
        @type limit:  L{int}
        
        @return:      artists similar to this artist
        @rtype:       L{list} of L{Artist}
        """
        params = self._default_params({'method': 'artist.getSimilar'})
        if limit is not None:
            params.update({'limit': limit})
        data = self._api._fetch_data(params).find('similarartists')
        self._similar = [
                          Artist(
                                 self._api,
                                 subject = self,
                                 name = a.findtext('name'),
                                 mbid = a.findtext('mbid'),
                                 stats = Stats(
                                               subject = a.findtext('name'),
                                               match = float(a.findtext('match')),
                                               ),
                                 url = 'http://' + a.findtext('url'),
                                 image = {'large': a.findtext('image')}
                                 )
                          for a in data.findall('artist')
                          ]
        return self._similar[:]

    @property
    def similar(self):
        """
        artists similar to this artist
        @rtype: L{list} of L{Artist}
        """
        if not hasattr(self, "_similar") or self._similar is None or len(self._similar) < 6:
            return self.get_similar()
        return self._similar[:]

    @top_property("similar")
    def most_similar(self):
        """
        artist most similar to this artist
        @rtype: L{Artist}
        """
        pass

    @property
    def top_tags(self):
        """
        top tags for the artist
        @rtype: L{list} of L{Tag}
        """
        if not hasattr(self, "_top_tags") or self._top_tags is None or len(self._top_tags) < 6:
            params = self._default_params({'method': 'artist.getTopTags'})
            data = self._api._fetch_data(params).find('toptags')
            self._top_tags = [
                              Tag(
                                  self._api,
                                  subject = self,
                                  name = t.findtext('name'),
                                  url = t.findtext('url')
                                  )
                              for t in data.findall('tag')
                              ]
        return self._top_tags[:]

    @top_property("top_tags")
    def top_tag(self):
        """
        top tag for the artist
        @rtype: L{Tag}
        """
        pass

    @cached_property
    def events(self):
        """
        events for the artist
        @rtype: L{lazylist} of L{Event}
        """
        params = self._default_params({'method': 'artist.getEvents'})
        data = self._api._fetch_data(params).find('events')

        return [
                Event.create_from_data(self._api, e)
                for e in data.findall('event')
                ]

    @cached_property
    def top_albums(self):
        """
        top albums of the artist
        @rtype: L{list} of L{Album}
        """
        params = self._default_params({'method': 'artist.getTopAlbums'})
        data = self._api._fetch_data(params).find('topalbums')

        return [
                Album(
                     self._api,
                     subject = self,
                     name = a.findtext('name'),
                     artist = self,
                     mbid = a.findtext('mbid'),
                     url = a.findtext('url'),
                     image = dict([(i.get('size'), i.text) for i in a.findall('image')]),
                     stats = Stats(
                                   subject = a.findtext('name'),
                                   playcount = int(a.findtext('playcount')),
                                   rank = int(a.attrib['rank'])
                                   )
                     )
                for a in data.findall('album')
                ]

    @top_property("top_albums")
    def top_album(self):
        """
        top album of the artist
        @rtype: L{Album}
        """
        pass

    @cached_property
    def top_fans(self):
        """
        top fans of the artist
        @rtype: L{list} of L{User}
        """
        params = self._default_params({'method': 'artist.getTopFans'})
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
        """
        top fan of the artist
        @rtype: L{User}"""
        pass

    @cached_property
    def top_tracks(self):
        """
        top tracks of the artist
        @rtype: L{list} of L{Track}
        """
        params = self._default_params({'method': 'artist.getTopTracks'})
        data = self._api._fetch_data(params).find('toptracks')
        return [
                Track(
                      self._api,
                      subject = self,
                      name = t.findtext('name'),
                      artist = self,
                      mbid = t.findtext('mbid'),
                      stats = Stats(
                                    subject = t.findtext('name'),
                                    playcount = int(t.findtext('playcount')),
                                    rank = int(t.attrib['rank'])
                                    ),
                      streamable = (t.findtext('streamable') == '1'),
                      full_track = (t.find('streamable').attrib['fulltrack'] == '1'),
                      image = dict([(i.get('size'), i.text) for i in t.findall('image')]),
                      )
                for t in data.findall('track')
                ]

    @top_property("top_tracks")
    def top_track(self):
        """
        topmost track of the artist
        @rtype: L{Track}
        """
        pass

    @staticmethod
    def get_info(api, artist = None, mbid = None):
        """
        Get the data for the artist.
        
        @param api:      an instance of L{Api}
        @type api:       L{Api}
        @param artist:   the name of the artist
        @type artist:    L{str}
        @param mbid:     MBID of the artist
        @type mbid:      L{str}
        
        @return:         an Artist object corresponding the provided artist name
        @rtype:          L{Artist}
        
        @raise lastfm.InvalidParametersError: Either artist or mbid parameter has to 
                                              be provided. Otherwise exception is raised.
        
        @note: Use the L{Api.get_artist} method instead of using this method directly.
        """
        data = Artist._fetch_data(api, artist, mbid)

        a = Artist(api, name = data.findtext('name'))
        a._fill_info()
        return a
    
    @staticmethod
    def _get_all(seed_artist):
        return (seed_artist, ['name'],
            lambda api, hsh: Artist(api, **hsh).similar)

    def _default_params(self, extra_params = None):
        if not self.name:
            raise InvalidParametersError("artist has to be provided.")
        params = {'artist': self.name}
        if extra_params is not None:
            params.update(extra_params)
        return params

    @staticmethod
    def _fetch_data(api,
                artist = None,
                mbid = None):
        params = {'method': 'artist.getInfo'}
        if not (artist or mbid):
            raise InvalidParametersError("either artist or mbid has to be given as argument.")
        if artist:
            params.update({'artist': artist})
        elif mbid:
            params.update({'mbid': mbid})
        return api._fetch_data(params).find('artist')

    def _fill_info(self):
        data = Artist._fetch_data(self._api, self.name)
        self._name = data.findtext('name')
        self._mbid = data.findtext('mbid')
        self._url = data.findtext('url')
        self._image = dict([(i.get('size'), i.text) for i in data.findall('image')])
        self._streamable = (data.findtext('streamable') == 1)
        if not self._stats:
            self._stats = Stats(
                             subject = self,
                             listeners = int(data.findtext('stats/listeners')),
                             playcount = int(data.findtext('stats/playcount'))
                             )
#        self._similar = [
#                          Artist(
#                                 self._api,
#                                 subject = self,
#                                 name = a.findtext('name'),
#                                 url = a.findtext('url'),
#                                 image = dict([(i.get('size'), i.text) for i in a.findall('image')])
#                                 )
#                          for a in data.findall('similar/artist')
#                          ]
        self._top_tags = [
                          Tag(
                              self._api,
                              subject = self,
                              name = t.findtext('name'),
                              url = t.findtext('url')
                              )
                          for t in data.findall('tags/tag')
                          ]
        self._bio = Wiki(
                         self,
                         published = data.findtext('bio/published').strip() and
                                        datetime(*(time.strptime(
                                                              data.findtext('bio/published').strip(),
                                                              '%a, %d %b %Y %H:%M:%S +0000'
                                                              )[0:6])),
                         summary = data.findtext('bio/summary'),
                         content = data.findtext('bio/content')
                         )

    @staticmethod
    def _search_yield_func(api, artist):
        return Artist(
                      api,
                      name = artist.findtext('name'),
                      mbid = artist.findtext('mbid'),
                      url = artist.findtext('url'),
                      image = dict([(i.get('size'), i.text) for i in artist.findall('image')]),
                      streamable = (artist.findtext('streamable') == '1'),
                      )
    @staticmethod
    def _hash_func(*args, **kwds):
        try:
            return hash(kwds['name'].lower())
        except KeyError:
            try:
                return hash(args[1].lower())
            except IndexError:
                raise InvalidParametersError("name has to be provided for hashing")

    def __hash__(self):
        return self.__class__._hash_func(name = self.name)

    def __eq__(self, other):
        if self.mbid and other.mbid:
            return self.mbid == other.mbid
        if self.url and other.url:
            return self.url == other.url
        return self.name == other.name

    def __lt__(self, other):
        return self.name < other.name

    def __repr__(self):
        return "<lastfm.Artist: %s>" % self._name

from datetime import datetime
import time

from lastfm.album import Album
from lastfm.api import Api
from lastfm.error import InvalidParametersError
from lastfm.event import Event
from lastfm.stats import Stats
from lastfm.tag import Tag
from lastfm.track import Track
from lastfm.user import User
from lastfm.wiki import Wiki
