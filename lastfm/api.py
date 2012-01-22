#!/usr/bin/env python
"""The last.fm web service API access functionalities"""

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

from threading import Lock
from lastfm.util import Wormhole, logging
from lastfm.decorators import cached_property, async_callback
_lock = Lock()

class Api(object):
    """The class representing the last.fm web services API."""

    DEFAULT_CACHE_TIMEOUT = 3600 # cache for 1 hour
    """Default file cache timeout, in seconds"""
    
    API_ROOT_URL = "http://ws.audioscrobbler.com/2.0/"
    """URL of the webservice API root"""
    
    FETCH_INTERVAL = 1
    """The minimum interval between successive HTTP request, in seconds"""
    
    SEARCH_XMLNS = "http://a9.com/-/spec/opensearch/1.1/"
    
    DEBUG_LEVELS = {
        'LOW': 1,
        'MEDIUM': 2,
        'HIGH': 3
    }

    def __init__(self,
                 api_key,
                 secret = None,
                 session_key = None,
                 input_encoding=None,
                 request_headers=None,
                 no_cache = False,
                 debug = None,
                 logfile = None):
        """
        Create an Api object to access the last.fm webservice API. Use this object as a
        starting point for accessing all the webservice methods.
        
        @param api_key:            last.fm API key
        @type api_key:             L{str}
        @param secret:             last.fm API secret (optional, required only for
                                   authenticated webservice methods)
        @type secret:              L{str}
        @param session_key:        session key for the authenticated session (optional,
                                   required only for authenticated webservice methods)
        @type session_key:         L{str}
        @param input_encoding:     encoding of the input data (optional)
        @type input_encoding:      L{str}
        @param request_headers:    HTTP headers for the requests to last.fm webservices
                                   (optional)
        @type request_headers:     L{dict}
        @param no_cache:           flag to switch off file cache (optional)
        @type no_cache:            L{bool}
        @param debug:              flag to switch on debugging (optional)
        @type debug:               L{bool}
        """
        self._api_key = api_key
        self._secret = secret
        self._session_key = session_key
        self._cache = FileCache()
        self._urllib = urllib2
        self._cache_timeout = Api.DEFAULT_CACHE_TIMEOUT
        self._initialize_request_headers(request_headers)
        self._initialize_user_agent()
        self._input_encoding = input_encoding
        self._no_cache = no_cache
        self._logfile = logfile
        self._last_fetch_time = datetime.now()
        
        if debug is not None:
            if debug in Api.DEBUG_LEVELS:
                self._debug = Api.DEBUG_LEVELS[debug]
            else:
                raise InvalidParametersError("debug parameter must be one of the keys in Api.DEBUG_LEVELS dict")
        else:
            self._debug = None
        if self._debug is not None:
            Wormhole.enable()
        logging.set_api(self)

    @property
    def api_key(self):
        """
        The last.fm API key
        @rtype: L{str}
        """
        return self._api_key

    @property
    def secret(self):
        """
        The last.fm API secret
        @rtype: L{str}
        """
        return self._secret
    
    def set_secret(self, secret):
        """
        Set the last.fm API secret.
        
        @param secret:    the secret
        @type secret:     L{str}
        """
        self._secret = secret

    @property
    def session_key(self):
        """
        Session key for the authenticated session
        @rtype: L{str}
        """
        return self._session_key

    def set_session_key(self, session_key = None):
        """
        Set the session key for the authenticated session.
        
        @param session_key: the session key for authentication (optional). If not provided then
                            a new one is fetched from last.fm
        @type session_key: L{str}
        
        @raise lastfm.AuthenticationFailedError: Either session_key should be provided or 
                                                 API secret must be present.
        """
        if session_key is not None:
            self._session_key = session_key
        else:
            with _lock:
                params = {'method': 'auth.getSession', 'token': self.auth_token}
                self._session_key = self._fetch_data(params, sign = True).findtext('session/key')
                self._auth_token = None

    @cached_property
    def auth_token(self):
        """
        The authentication token for the authenticated session.
        @rtype: L{str}
        """
        params = {'method': 'auth.getToken'}
        return self._fetch_data(params, sign = True).findtext('token')

    @cached_property
    def auth_url(self):
        """
        The authentication URL for the authenticated session.
        @rtype: L{str}
        """
        return "http://www.last.fm/api/auth/?api_key=%s&token=%s" % (self.api_key, self.auth_token)

    def set_cache(self, cache):
        """
        Override the default cache.  Set to None to prevent caching.
        
        @param cache: an instance that supports the same API as the L{FileCache}
        @type cache: L{FileCache}
        """
        self._cache = cache

    def set_urllib(self, urllib):
        """
        Override the default urllib implementation.

        @param urllib: an instance that supports the same API as the urllib2 module
        @type urllib: urllib2
        """
        self._urllib = urllib

    def set_cache_timeout(self, cache_timeout):
        """
        Override the default cache timeout.

        @param cache_timeout: time, in seconds, that responses should be reused
        @type cache_timeout: L{int}
        """
        self._cache_timeout = cache_timeout

    def set_user_agent(self, user_agent):
        """
        Override the default user agent.

        @param user_agent: a string that should be send to the server as the User-agent
        @type user_agent: L{str}
        """
        self._request_headers['User-Agent'] = user_agent

    @async_callback
    def get_album(self,
                 album = None,
                 artist = None,
                 mbid = None,
                 callback = None):
        """
        Get an album object.
        
        @param album:    the album name
        @type album:     L{str}
        @param artist:   the album artist name 
        @type artist:    L{str} OR L{Artist}
        @param mbid:     MBID of the album
        @type mbid:      L{str}
        @param callback: callback function for asynchronous invocation (optional)
        @type callback:  C{function}
        
        @return:         an Album object corresponding the provided album name
        @rtype:          L{Album}
        
        @raise lastfm.InvalidParametersError: Either album and artist parameters or 
                                              mbid parameter has to be provided. 
                                              Otherwise exception is raised.
                                              
        @see:            L{Album.get_info}
        @see:            L{async_callback}
        """
        if isinstance(artist, Artist):
            artist = artist.name
        return Album.get_info(self, artist, album, mbid)

    @async_callback
    def search_album(self, album, limit = None, callback = None):
        """
        Search for an album by name.
        
        @param album:     the album name
        @type album:      L{str}
        @param limit:     maximum number of results returned (optional)
        @type limit:      L{int}
        @param callback:  callback function for asynchronous invocation (optional)
        @type callback:   C{function}
        
        @return:          matches sorted by relevance
        @rtype:           L{lazylist} of L{Album}
        
        @see:             L{Album.search}
        @see:             L{async_callback}
        """
        return Album.search(self, search_item = album, limit = limit)

    @async_callback
    def get_artist(self, artist = None, mbid = None, callback = None):
        """
        Get an artist object.
        
        @param artist:    the artist name
        @type artist:     L{str}
        @param mbid:      MBID of the artist
        @type mbid:       L{str}
        @param callback:  callback function for asynchronous invocation (optional)
        @type callback:   C{function}
        
        @return:         an Artist object corresponding the provided artist name
        @rtype:          L{Artist}
        
        @raise lastfm.InvalidParametersError: either artist or mbid parameter has
                                              to be provided. Otherwise exception is raised.
                                              
        @see:            L{Artist.get_info}
        @see:            L{async_callback}
        """
        return Artist.get_info(self, artist, mbid)
    
    @async_callback
    def search_artist(self, artist, limit = None, callback = None):
        """
        Search for an artist by name.
        
        @param artist:    the artist name
        @type artist:     L{str}
        @param limit:     maximum number of results returned (optional)
        @type limit:      L{int}
        @param callback:  callback function for asynchronous invocation (optional)
        @type callback:   C{function}
        
        @return:          matches sorted by relevance
        @rtype:           L{lazylist} of L{Artist}
        
        @see:             L{Artist.search}
        @see:             L{async_callback}
        """
        return Artist.search(self, search_item = artist, limit = limit)

    @async_callback
    def get_event(self, event, callback = None):
        """
        Get an event object.
        
        @param event:     the event id
        @type event:      L{int}
        @param callback:  callback function for asynchronous invocation (optional)
        @type callback:   C{function}
        
        @return:          an event object corresponding to the event id provided
        @rtype:           L{Event}
        
        @raise InvalidParametersError: Exception is raised if an invalid event id is supplied.
        
        @see:             L{Event.get_info}
        @see:             L{async_callback}
        """
        return Event.get_info(self, event)
    
    @async_callback
    def get_location(self, city, callback = None):
        """
        Get a location object.
        
        @param city:        the city name
        @type city:         L{str}
        @param callback:    callback function for asynchronous invocation (optional)
        @type callback:     C{function}
        
        @return:        a location object corresponding to the city name provided
        @rtype:         L{Location}
        
        @see:           L{async_callback}
        """
        return Location(self, city = city)

    @async_callback
    def get_country(self, name, callback = None):
        """
        Get a country object.
        
        @param name:        the country name
        @type name:         L{str}
        @param callback:    callback function for asynchronous invocation (optional)
        @type callback:     C{function}
        
        @return:        a country object corresponding to the country name provided
        @rtype:         L{Country}
        
        @see:           L{async_callback}
        """
        return Country(self, name = name)
    
    @async_callback
    def get_group(self, name, callback = None):
        """
        Get a group object.
        
        @param name:        the group name
        @type name:         L{str}
        @param callback:    callback function for asynchronous invocation (optional)
        @type callback:     C{function}
        
        @return:        a group object corresponding to the group name provided
        @rtype:         L{Group}
        
        @see:           L{async_callback}
        """
        return Group(self, name = name)

    @async_callback
    def get_playlist(self, url, callback = None):
        """
        Get a playlist object.
        
        @param url:        lastfm url of the playlist
        @type url:         L{str}
        @param callback:   callback function for asynchronous invocation (optional)
        @type callback:    C{function}
        
        @return:        a playlist object corresponding to the playlist url provided
        @rtype:         L{Playlist}
        
        @see:           L{Playlist.fetch}
        @see:           L{async_callback}
        """
        return Playlist.fetch(self, url)
    
    @async_callback
    def get_tag(self, name, callback = None):
        """
        Get a tag object.
        
        @param name:        the tag name
        @type name:         L{str}
        @param callback:    callback function for asynchronous invocation (optional)
        @type callback:     C{function}
        
        @return:        a tag object corresponding to the tag name provided
        @rtype:         L{Tag}
        
        @see:           L{async_callback}
        """
        return Tag(self, name = name)

    @async_callback
    def get_global_top_tags(self, callback = None):
        """
        Get the top global tags on Last.fm, sorted by popularity (number of times used).
        
        @param callback: callback function for asynchronous invocation (optional)
        @type callback:  C{function}
        
        @return:        a list of top global tags
        @rtype:         L{list} of L{Tag}
        
        @see:           L{async_callback}
        """
        return Tag.get_top_tags(self)

    @async_callback
    def search_tag(self, tag, limit = None, callback = None):
        """
        Search for a tag by name.
        
        @param tag:       the tag name
        @type tag:        L{str}
        @param limit:     maximum number of results returned (optional)
        @type limit:      L{int}
        @param callback:  callback function for asynchronous invocation (optional)
        @type callback:   C{function}
        
        @return:          matches sorted by relevance
        @rtype:           L{lazylist} of L{Tag}
        
        @see:             L{Tag.search}
        @see:             L{async_callback}
        """
        return Tag.search(self, search_item = tag, limit = limit)

    @async_callback
    def compare_taste(self,
                     type1, type2,
                     value1, value2,
                     limit = None,
                     callback = None):
        """
        Get a Tasteometer score from two inputs, along with a list of
        shared artists. If the input is a User or a Myspace URL, some 
        additional information is returned. 
        
        @param type1:    'user' OR 'artists' OR 'myspace'
        @type type1:     L{str}  
        @param type2:    'user' OR 'artists' OR 'myspace'
        @type type2:     L{str}
        @param value1:   Last.fm username OR Comma-separated artist names OR MySpace profile URL
        @type value1:    L{str}
        @param value2:   Last.fm username OR Comma-separated artist names OR MySpace profile URL 
        @type value2:    L{str}
        @param limit:    maximum number of results returned (optional)
        @type limit:     L{int}
        @param callback: callback function for asynchronous invocation (optional)
        @type callback:  C{function}
        
        @return:         the taste-o-meter score for the inputs
        @rtype:          L{Tasteometer}
        
        @see:            L{Tasteometer.compare}
        @see:            L{async_callback}
        """
        return Tasteometer.compare(self, type1, type2, value1, value2, limit)

    @async_callback
    def get_track(self,
                  track,
                  artist = None,
                  mbid = None,
                  callback = None):
        """
        Get a track object.
        
        @param track:    the track name
        @type track:     L{str}
        @param artist:   the track artist
        @type artist:    L{str} OR L{Artist}
        @param mbid:     MBID of the track
        @type mbid:      L{str}
        @param callback: callback function for asynchronous invocation (optional)
        @type callback:  C{function}
        
        @return:         a track object corresponding to the track name provided
        @rtype:          L{Track}
        
        @raise lastfm.InvalidParametersError: either artist or mbid parameter has
                                              to be provided. Otherwise exception is raised.
                                              
        @see:            L{Track.get_info}
        @see:            L{async_callback}
        """
        if isinstance(artist, Artist):
            artist = artist.name
        return Track.get_info(self, artist, track, mbid)
    
    @async_callback
    def search_track(self,
                     track, 
                     artist = None, 
                     limit = None, 
                     callback = None):
        """
        Search for a track by name.
        
        @param track:     the track name
        @type track:      L{str}
        @param artist:    the track artist (optional)
        @type artist:     L{str} OR L{Artist}  
        @param limit:     maximum number of results returned (optional)
        @type limit:      L{int}
        @param callback:  callback function for asynchronous invocation (optional)
        @type callback:   C{function}
        
        @return:          matches sorted by relevance
        @rtype:           L{lazylist} of L{Track}
        
        @see:             L{Track.search}
        @see:             L{async_callback}
        """
        if isinstance(artist, Artist):
            artist = artist.name
        return Track.search(self, search_item = track, limit = limit, artist = artist)

    @async_callback
    def get_user(self, name, callback = None):
        """
        Get an user object.
        
        @param name:        the last.fm user name
        @type name:         L{str}
        @param callback:    callback function for asynchronous invocation (optional)
        @type callback:     C{function}
        
        @return:        an user object corresponding to the user name provided
        @rtype:         L{User}
        
        @raise InvalidParametersError: Exception is raised if an invalid user name is supplied.
        
        @see:           L{User.get_info}
        @see:           L{async_callback}
        """
        return User.get_info(self, name = name)

    @async_callback
    def get_authenticated_user(self, callback = None):
        """
        Get the currently authenticated user.
        
        @param callback: callback function for asynchronous invocation (optional)
        @type callback: C{function}
        
        @return:     The currently authenticated user if the session is authenticated
        @rtype:      L{User}
        
        @see:        L{User.get_authenticated_user}
        @see:        L{async_callback}
        """
        if self.session_key is not None:
            return User.get_authenticated_user(self)
        else:
            raise AuthenticationFailedError("session key must be present to call this method")
    
    @async_callback
    def get_venue(self, venue, callback = None):
        """
        Get a venue object.
        
        @param venue:        the venue name
        @type venue:         L{str}
        @param callback:     callback function for asynchronous invocation (optional)
        @type callback:      C{function}
        
        @return:         a venue object corresponding to the venue name provided
        @rtype:          L{Venue}
        
        @raise InvalidParametersError: Exception is raised if an non-existant venue name is supplied.
        
        @see:            L{search_venue}
        @see:            L{async_callback}
        """
        try:
            return self.search_venue(venue)[0]
        except IndexError:
            raise InvalidParametersError("No such venue exists")
    
    @async_callback
    def search_venue(self, 
                     venue, 
                     limit = None, 
                     country = None,
                     callback = None):
        """
        Search for a venue by name.
        
        @param venue:     the venue name
        @type venue:      L{str}
        @param country:   filter the results by country. Expressed as an ISO 3166-2 code.
                          (optional)
        @type country:    L{str}  
        @param limit:     maximum number of results returned (optional)
        @type limit:      L{int}
        @param callback:  callback function for asynchronous invocation (optional)
        @type callback:   C{function}
        
        @return:          matches sorted by relevance
        @rtype:           L{lazylist} of L{Venue}
        
        @see:             L{Venue.search}
        @see:             L{async_callback}
        """
        return Venue.search(self, search_item = venue, limit = limit, country = country)

    @Wormhole.entrance('lfm-api-url')
    def _build_url(self, url, path_elements=None, extra_params=None):
        # Break url into consituent parts
        (scheme, netloc, path, params, query, fragment) = urlparse.urlparse(url)
        path = path.replace(' ', '+')

        # Add any additional path elements to the path
        if path_elements:
            # Filter out the path elements that have a value of None
            p = [i for i in path_elements if i]
            if not path.endswith('/'):
                path += '/'
                path += '/'.join(p)

        # Add any additional query parameters to the query string
        if extra_params and len(extra_params) > 0:
            extra_query = self._encode_parameters(extra_params)
            # Add it to the existing query
            if query:
                query += '&' + extra_query
            else:
                query = extra_query

        # Return the rebuilt URL
        return urlparse.urlunparse((scheme, netloc, path, params, query, fragment))

    def _initialize_request_headers(self, request_headers):
        if request_headers:
            self._request_headers = request_headers
        else:
            self._request_headers = {}

    def _initialize_user_agent(self):
        user_agent = 'Python-urllib/%s (python-lastfm/%s)' % \
                     (self._urllib.__version__, __version__)
        self.set_user_agent(user_agent)

    def _get_opener(self, url):
        opener = self._urllib.build_opener()
        if self._urllib._opener is not None:
            opener = self._urllib.build_opener(*self._urllib._opener.handlers)
        opener.addheaders = self._request_headers.items()
        return opener

    def _encode(self, s):
        if self._input_encoding:
            return unicode(s, self._input_encoding).encode('utf-8')
        else:
            return unicode(s).encode('utf-8')

    def _encode_parameters(self, parameters):
        if parameters is None:
            return None
        else:
            keys = parameters.keys()
            keys.sort()
            return urllib.urlencode([(k, self._encode(parameters[k])) for k in keys if parameters[k] is not None])

    def _read_url_data(self, opener, url, data = None):
        with _lock:
            now = datetime.now()
            delta = now - self._last_fetch_time
            delta = delta.seconds + float(delta.microseconds)/1000000
            if delta < Api.FETCH_INTERVAL:
                time.sleep(Api.FETCH_INTERVAL - delta)
            url_data = opener.open(url, data).read()
            self._last_fetch_time = datetime.now()
        return url_data

    @Wormhole.entrance('lfm-api-raw-data')
    def _fetch_url(self, url, parameters = None, no_cache = False):
        # Add key/value parameters to the query string of the url
        url = self._build_url(url, extra_params=parameters)
        # Get a url opener that can handle basic auth
        opener = self._get_opener(url)

        # Open and return the URL immediately if we're not going to cache
        if no_cache or not self._cache or not self._cache_timeout:
            try:
                url_data = self._read_url_data(opener, url)
            except urllib2.HTTPError, e:
                url_data = e.read()
        else:
            # Unique keys are a combination of the url and the username
            key = url.encode('utf-8')

            # See if it has been cached before
            last_cached = self._cache.GetCachedTime(key)

            # If the cached version is outdated then fetch another and store it
            if not last_cached or time.time() >= last_cached + self._cache_timeout:
                try:
                    url_data = self._read_url_data(opener, url)
                except urllib2.HTTPError, e:
                    url_data = e.read()
                self._cache.Set(key, url_data)
            else:
                url_data = self._cache.Get(key)

        # Always return the latest version
        return url_data

    @Wormhole.entrance('lfm-api-processed-data')
    def _fetch_data(self,
                   params,
                   sign = False,
                   session = False,
                   no_cache = False):
        params = params.copy()
        params['api_key'] = self.api_key

        if session:
            if self.session_key is not None:
                params['sk'] = self.session_key
            else:
                raise AuthenticationFailedError("session key must be present to call this method")

        if sign:
            params['api_sig'] = self._get_api_sig(params)

        xml = self._fetch_url(Api.API_ROOT_URL, params, no_cache = self._no_cache or no_cache)
        return self._check_xml(xml)

    @Wormhole.entrance('lfm-api-raw-data')
    def _post_url(self,
                 url,
                 parameters):
        url = self._build_url(url)
        data = self._encode_parameters(parameters)
        opener = self._get_opener(url)
        url_data = self._read_url_data(opener, url, data)
        return url_data

    @Wormhole.entrance('lfm-api-processed-data')
    def _post_data(self, params):
        params['api_key'] = self.api_key

        if self.session_key is not None:
            params['sk'] = self.session_key
        else:
            raise AuthenticationFailedError("session key must be present to call this method")

        params['api_sig'] = self._get_api_sig(params)
        xml = self._post_url(Api.API_ROOT_URL, params)
        return self._check_xml(xml)

    def _get_api_sig(self, params):
        if self.secret is not None:
            keys = params.keys()[:]
            keys.sort()
            sig = unicode()
            for name in keys:
                if name == 'api_sig': continue
                sig += ("%s%s" % (name, params[name]))
            sig += self.secret
            hashed_sig = md5hash(sig)
            return hashed_sig
        else:
            raise AuthenticationFailedError("api secret must be present to call this method")

    def _check_xml(self, xml):
        data = None
        try:
            data = ElementTree.XML(xml)
        except SyntaxError, e:
            raise OperationFailedError("Error in parsing XML: %s" % e)
        if data.get('status') != "ok":
            code = int(data.find("error").get('code'))
            message = data.findtext('error')
            if code in error_map.keys():
                raise error_map[code](message, code)
            else:
                raise LastfmError(message, code)
        return data

    def __repr__(self):
        return "<lastfm.Api: %s>" % self._api_key

from datetime import datetime
import sys
import time
import urllib
import urllib2
import urlparse

from lastfm.album import Album
from lastfm.artist import Artist
from lastfm.error import error_map, LastfmError, OperationFailedError, AuthenticationFailedError,\
    InvalidParametersError
from lastfm.event import Event
from lastfm.util import FileCache
from lastfm.geo import Location, Country
from lastfm.group import Group
from lastfm.playlist import Playlist
from lastfm.tag import Tag
from lastfm.tasteometer import Tasteometer
from lastfm.track import Track
from lastfm.user import User
from lastfm.venue import Venue

if sys.version < '2.6':
    import md5
    def md5hash(string):
        return md5.new(string).hexdigest()
else:
    from hashlib import md5
    def md5hash(string):
        return md5(string).hexdigest()
    
if sys.version_info >= (2, 5):
    import xml.etree.cElementTree as ElementTree
else:
    try:
        import cElementTree as ElementTree
    except ImportError:
        try:
            import ElementTree
        except ImportError:
            raise LastfmError("Install ElementTree package for using python-lastfm")
