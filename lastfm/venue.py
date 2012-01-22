#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

from lastfm.base import LastfmBase
from lastfm.mixin import mixin
from lastfm.decorators import cached_property, depaginate

@mixin("crawlable", "searchable", "cacheable", "property_adder")
class Venue(LastfmBase):
    """A class representing a venue of an event"""
    
    class Meta(object):
        properties = ["id", "name", "location", "url"]
        
    def init(self, api, **kwargs):
        if not isinstance(api, Api):
            raise InvalidParametersError("api reference must be supplied as an argument")
        self._api = api
        super(Venue, self).init(**kwargs)

    @cached_property
    def events(self):
        params = self._default_params({'method': 'venue.getEvents'})
        data = self._api._fetch_data(params).find('events')

        return [
                Event.create_from_data(self._api, e)
                for e in data.findall('event')
                ]
        
    @depaginate
    def get_past_events(self, limit = None, page = None):
        params = self._default_params({'method': 'venue.getPastEvents'})
        if limit is not None:
            params.update({'limit': limit})
        if page is not None:
            params.update({'page': page})

        data = self._api._fetch_data(params).find('events')
        total_pages = int(data.attrib['totalPages'])
        yield total_pages

        for e in data.findall('event'):
            yield Event.create_from_data(self._api, e)

    @cached_property
    def past_events(self):
        return self.get_past_events()
    
    @staticmethod
    def _get_all(seed_venue):
        def gen():
            for event in Event.get_all(seed_venue.past_events[0]):
                yield event.venue
        
        return (seed_venue, ['id'], lambda api, hsh: gen())

    
    def _default_params(self, extra_params = {}):
        if not self.id:
            raise InvalidParametersError("venue id has to be provided.")
        params = {'venue': self.id}
        params.update(extra_params)
        return params
    
    @staticmethod
    def _search_yield_func(api, venue):
        latitude = venue.findtext('location/{%s}point/{%s}lat' % ((Location.XMLNS,)*2))
        longitude = venue.findtext('location/{%s}point/{%s}long' % ((Location.XMLNS,)*2))
        
        return Venue(
                     api,
                     id = int(venue.findtext('id')),
                     name = venue.findtext('name'),
                     location = Location(
                                         api,
                                         city = venue.findtext('location/city'),
                                         country = Country(
                                            api,
                                            name = venue.findtext('location/country')
                                            ),
                                         street = venue.findtext('location/street'),
                                         postal_code = venue.findtext('location/postalcode'),
                                         latitude = (latitude.strip()!= '') and float(latitude) or None,
                                         longitude = (longitude.strip()!= '') and float(longitude) or None,
                                       ),
                     url = venue.findtext('url')
                     )
    
    @staticmethod
    def _hash_func(*args, **kwds):
        try:
            return hash(kwds['url'])
        except KeyError:
            raise InvalidParametersError("url has to be provided for hashing")

    def __hash__(self):
        return self.__class__._hash_func(url = self.url)

    def __eq__(self, other):
        return self.url == other.url

    def __lt__(self, other):
        return self.name < other.name

    def __repr__(self):
        return "<lastfm.geo.Venue: %s, %s>" % (self.name, self.location.city)
    
from lastfm.api import Api
from lastfm.event import Event
from lastfm.geo import Location, Country
from lastfm.error import InvalidParametersError