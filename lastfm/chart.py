#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

from functools import reduce
from lastfm.base import LastfmBase
from lastfm.mixin import mixin
from lastfm.util import logging
from operator import xor

@mixin("cacheable", "property_adder")
class Chart(LastfmBase):
    """The base class for all the chart classes"""
    class Meta(object):
        properties = ["subject", "start", "end", "stats"]

    def init(self, subject, start, end, stats = None):
        self._subject = subject
        self._start = start
        self._end = end
        self._stats = stats
    
    @staticmethod
    def _check_chart_params(params, subject, start = None, end = None):
        if xor(start is None, end is None):
            raise InvalidParametersError("both start and end have to be provided.")
        if start is not None and end is not None:
            if not (isinstance(start, datetime) and isinstance(end, datetime)):
                raise InvalidParametersError("start and end must be datetime.datetime instances")
            params.update({
                           'from': int(calendar.timegm(start.timetuple())),
                           'to': int(calendar.timegm(end.timetuple()))
                           })
        return params
    
    @staticmethod
    def _hash_func(*args, **kwds):
        try:
            return hash("%s%s%s%s" % (
                                      kwds['subject'].__class__.__name__,
                                      kwds['subject'].name,
                                      kwds['start'],
                                      kwds['end']
                               ))
        except KeyError:
            raise InvalidParametersError("subject, start and end have to be provided for hashing")
        
    def __hash__(self):
        return self.__class__._hash_func(
            subject = self.subject,
            start = self.start,
            end = self.end
        )
    
    def __eq__(self, other):
        return self.subject == other.subject and \
                self.start == other.start and \
                self.end == other.end
    
    def __lt__(self, other):
        if self.subject == other.subject:
            if self.start == other.start:
                return self.end < other.end
            else:
                return self.start < other.start
        else:
            return self.subject < other.subject
    
    def __repr__(self):
        return "<lastfm.%s: for %s:%s from %s to %s>" % \
            (
             self.__class__.__name__,
             self.subject.__class__.__name__,
             self.subject.name,
             self.start.strftime("%x"),
             self.end.strftime("%x"),
            )

@mixin("property_adder")
class AlbumChart(Chart):
    class Meta(object):
        properties = ["albums"]
        
    def init(self, subject, start, end, stats, albums):
        super(AlbumChart, self).init(subject, start, end, stats)
        self._albums = albums
    
@mixin("property_adder")
class ArtistChart(Chart):
    class Meta(object):
        properties = ["artists"]
        
    def init(self, subject, start, end, stats, artists):
        super(ArtistChart, self).init(subject, start, end, stats)
        self._artists = artists
    
@mixin("property_adder")
class TrackChart(Chart):
    class Meta(object):
        properties = ["tracks"]
        
    def init(self, subject, start, end, tracks, stats):
        super(TrackChart, self).init(subject, start, end, stats)
        self._tracks = tracks

@mixin("property_adder")
class TagChart(Chart):
    class Meta(object):
        properties = ["tags"]
        
    def init(self, subject, start, end, tags, stats):
        super(TagChart, self).init(subject, start, end, stats)
        self._tags = tags
    
class WeeklyChart(Chart):
    """A class for representing the weekly charts"""
    @staticmethod
    def create_from_data(api, subject, data):
        return WeeklyChart(
                     subject = subject,
                     start = datetime.utcfromtimestamp(int(data.attrib['from'])),
                     end = datetime.utcfromtimestamp(int(data.attrib['to']))
                     )
        
    @staticmethod
    def _check_chart_params(params, subject, start = None, end = None):
        params = Chart._check_chart_params(params, subject, start, end)
        if start is not None and end is not None:
            wcl = subject.weekly_chart_list
            is_valid = False
            for wc in wcl:
                if wc.start == start and wc.end == end:
                    is_valid = True
            if not is_valid:
                raise InvalidParametersError("%s - %s chart dates are invalid" % (start, end))
        return params       

class WeeklyAlbumChart(AlbumChart, WeeklyChart):
    """A class for representing the weekly album charts"""
    @staticmethod
    def create_from_data(api, subject, data):
        w = WeeklyChart(
                        subject = subject,
                        start = datetime.utcfromtimestamp(int(data.attrib['from'])),
                        end = datetime.utcfromtimestamp(int(data.attrib['to'])),
                        )
        return WeeklyAlbumChart(
            subject = subject,
            start = datetime.utcfromtimestamp(int(data.attrib['from'])),
            end = datetime.utcfromtimestamp(int(data.attrib['to'])),
            stats = Stats(
                subject = subject,
                playcount = reduce(
                    lambda x,y:(
                        x + int(y.findtext('playcount'))
                    ),
                    data.findall('album'),
                    0
                )
            ),
            albums = [
                Album(
                      api,
                      subject = w,
                      name = a.findtext('name'),
                      mbid = a.findtext('mbid'),
                      artist = Artist(
                          api,
                          subject = w,
                          name = a.findtext('artist'),
                          mbid = a.find('artist').attrib['mbid'],
                          ),
                      stats = Stats(
                          subject = a.findtext('name'),
                          rank = int(a.attrib['rank']),
                          playcount = int(a.findtext('playcount')),
                          ),
                      url = a.findtext('url'),
                      )
                for a in data.findall('album')
                ]
            )
    
class WeeklyArtistChart(ArtistChart, WeeklyChart):
    """A class for representing the weekly artist charts"""
    @staticmethod
    def create_from_data(api, subject, data):
        w = WeeklyChart(
                        subject = subject,
                        start = datetime.utcfromtimestamp(int(data.attrib['from'])),
                        end = datetime.utcfromtimestamp(int(data.attrib['to'])),
                        )
        count_attribute = data.find('artist').findtext('playcount') and 'playcount' or 'weight'
        def get_count_attribute(artist):
            return {count_attribute: int(eval(artist.findtext(count_attribute)))}
        def get_count_attribute_sum(artists):
            return {count_attribute: reduce(
                        lambda x, y:(x + int(eval(y.findtext(count_attribute)))), artists, 0
                    )}
            
        return WeeklyArtistChart(
            subject = subject,
            start = datetime.utcfromtimestamp(int(data.attrib['from'])),
            end = datetime.utcfromtimestamp(int(data.attrib['to'])),
            stats = Stats(
                          subject = subject,
                          **get_count_attribute_sum(data.findall('artist'))
                    ),
            artists = [
                      Artist(
                            api,
                            subject = w,
                            name = a.findtext('name'),
                            mbid = a.findtext('mbid'),
                            stats = Stats(
                                          subject = a.findtext('name'),
                                          rank = int(a.attrib['rank']),
                                          **get_count_attribute(a)
                                          ),
                            url = a.findtext('url'),
                            )
                      for a in data.findall('artist')
                      ]
            )
    
class WeeklyTrackChart(TrackChart, WeeklyChart):
    """A class for representing the weekly track charts"""
    @staticmethod
    def create_from_data(api, subject, data):
        w = WeeklyChart(
            subject = subject,
            start = datetime.utcfromtimestamp(int(data.attrib['from'])),
            end = datetime.utcfromtimestamp(int(data.attrib['to'])),
            )
        return WeeklyTrackChart(
            subject = subject,
            start = datetime.utcfromtimestamp(int(data.attrib['from'])),
            end = datetime.utcfromtimestamp(int(data.attrib['to'])),
            stats = Stats(
                subject = subject,
                playcount = reduce(
                                   lambda x,y:(
                                               x + int(y.findtext('playcount'))
                                               ),
                                   data.findall('track'),
                                   0
                )
            ),
            tracks = [
                      Track(
                            api,
                            subject = w,
                            name = t.findtext('name'),
                            mbid = t.findtext('mbid'),
                            artist = Artist(
                                            api,
                                            name = t.findtext('artist'),
                                            mbid = t.find('artist').attrib['mbid'],
                                            ),
                            stats = Stats(
                                          subject = t.findtext('name'),
                                          rank = int(t.attrib['rank']),
                                          playcount = int(t.findtext('playcount')),
                                          ),
                            url = t.findtext('url'),
                            )
                      for t in data.findall('track')
                     ]
           )
        
class WeeklyTagChart(TagChart, WeeklyChart):
    """A class for representing the weekly tag charts"""
    @staticmethod
    def create_from_data(api, subject, start, end):
        w = WeeklyChart(
                        subject = subject,
                        start = start,
                        end = end,
                        )
        max_tag_count = 3
        global_top_tags = api.get_global_top_tags()
        from collections import defaultdict

        wac = subject.get_weekly_artist_chart(start, end)
        all_tags = defaultdict(lambda:0)
        tag_weights = defaultdict(lambda:0)
        total_playcount = 0
        artist_count = 0
        for artist in wac.artists:
            artist_count += 1
            total_playcount += artist.stats.playcount
            tag_count = 0
            for tag in artist.top_tags:
                if tag not in global_top_tags: continue
                if tag_count >= max_tag_count: break
                all_tags[tag] += 1
                tag_count += 1
                
            artist_pp = artist.stats.playcount/float(wac.stats.playcount)
            cumulative_pp = total_playcount/float(wac.stats.playcount)
            if (cumulative_pp > 0.75 or artist_pp < 0.01) and artist_count > 10:
                break
        
        for artist in wac.artists[:artist_count]:
            artist_pp = artist.stats.playcount/float(wac.stats.playcount)
            tf = 1/float(max_tag_count)
            tag_count = 0
            weighted_tfidfs = {}
            for tag in artist.top_tags:
                if tag not in global_top_tags: continue
                if tag_count >= max_tag_count: break            
                
                df = all_tags[tag]/float(artist_count)
                tfidf = tf/df
                weighted_tfidf = float(max_tag_count - tag_count)*tfidf
                weighted_tfidfs[tag.name] = weighted_tfidf
                tag_count += 1
                
            sum_weighted_tfidfs = sum(weighted_tfidfs.values())
            for tag in weighted_tfidfs:
                tag_weights[tag] += weighted_tfidfs[tag]/sum_weighted_tfidfs*artist_pp            
            
            artist_pp = artist.stats.playcount/float(wac.stats.playcount)
                
        tag_weights_sum = sum(tag_weights.values())
        tag_weights = tag_weights.items()
        tag_weights.sort(key=lambda x:x[1], reverse=True)
        for i in xrange(len(tag_weights)):
            tag, weight = tag_weights[i]
            tag_weights[i] = (tag, weight, i+1)
        
        wtc = WeeklyTagChart(
           subject = subject,
           start = wac.start,
           end = wac.end,
           stats = Stats(
                         subject = subject,
                         playcount = 1000
                         ),
           tags = [
                     Tag(
                           api,
                           subject = w,
                           name = tag,
                           stats = Stats(
                                         subject = tag,
                                         rank = rank,
                                         count = int(round(1000*weight/tag_weights_sum)),
                                         )
                           )
                     for (tag, weight, rank) in tag_weights
                     ]
           )
        wtc._artist_spectrum_analyzed = 100*total_playcount/float(wac.stats.playcount)
        return wtc

class RollingChart(Chart):
    """Base class for the rolling charts classes"""
    @classmethod
    def _check_chart_params(cls, params, subject, start = None, end = None):
        duration = cls._period['duration']
        params = Chart._check_chart_params(params, subject, start, end)
        if start is not None and end is not None:
            mcl = MonthlyChart.get_chart_list(subject)
            is_valid = False
            for i in xrange(len(mcl)-(duration-1)):
                if mcl[i].start == start and mcl[i+(duration-1)].end == end:
                    is_valid = True
            if not is_valid:
                raise InvalidParametersError("%s - %s chart dates are invalid" % (start, end))
        return params

    @classmethod
    def create_from_data(cls, subject, key_func,
                         start = None, end = None):
        chart_type = cls.mro()[0]._chart_type
        period = cls.mro()[3]._period
        globals()["%slyChart" % period['name'].title().replace(' ','')]._check_chart_params({}, subject, start, end)
        mcl = MonthlyChart.get_chart_list(subject)
        if start is None and end is None:
            start = mcl[-period['duration']].start
            end = mcl[-1].end
        wcl = subject.weekly_chart_list
        period_wcl = [wc for wc in wcl
            if start < wc.start < end or start < wc.end < end]
        period_wacl = []
        for wc in period_wcl:
            try:
                period_wacl.append(
                    getattr(subject, "get_weekly_%s_chart" % chart_type)(wc.start, wc.end))
            except LastfmError as ex:
                logging.log_silenced_exceptions(ex)
        stats_dict = period_wacl[0].__dict__["_%ss" % chart_type][0].stats.__dict__
        count_attribute = [k for k in stats_dict.keys()
                           if stats_dict[k] is not None and k not in ['_rank', '_subject']][0]
        items = {}
        for wac in period_wacl:
            for item in wac.__dict__["_%ss" % chart_type]:
                key = key_func(item)
                mw_start = max(wac.start, start)
                mw_end = min(wac.end, end)
                count = item.stats.__dict__[count_attribute] * (mw_end - mw_start).days / 7.0
                if key in items:
                    items[key].stats.__dict__[count_attribute] += count
                else:
                    items[key] = item
                    items[key].stats.__dict__[count_attribute] = count
        items = items.values()
        items = [a for a in items if a.stats.__dict__[count_attribute] >= 1]
        items.sort(key = lambda a: a.stats.__dict__[count_attribute], reverse=True)
        for i,item in enumerate(items):
            item.stats._rank = i + 1
            item.stats.__dict__[count_attribute] = int(item.stats.__dict__[count_attribute])
        return globals()[
            "%sly%sChart" % (
                period['name'].title().replace(' ',''),
                chart_type.capitalize()
            )](
            subject = subject,
            start = start,
            end = end,
            stats = Stats(
                subject = subject,
                **{count_attribute[1:]: sum(a.stats.__dict__[count_attribute] for a in items)}
            ),
            **{"%ss" % chart_type: items}
        )

class RollingAlbumChart(AlbumChart):
    @classmethod
    def create_from_data(cls, subject, start = None, end = None):
        key_func = lambda album: "::".join((album.name, album.artist.name))
        return super(cls.mro()[3], cls).create_from_data(
            subject, key_func, start, end)

class RollingArtistChart(ArtistChart):
    @classmethod
    def create_from_data(cls, subject, start = None, end = None):
        key_func = lambda artist: artist.name
        return super(cls.mro()[3], cls).create_from_data(
            subject, key_func, start, end)

class RollingTrackChart(TrackChart):
    @classmethod
    def create_from_data(cls, subject, start = None, end = None):
        key_func = lambda track: "::".join((track.name, track.artist.name))
        return super(cls.mro()[3], cls).create_from_data(
            subject, key_func, start, end)

class RollingTagChart(TagChart):
    @classmethod
    def create_from_data(cls, subject, start = None, end = None):
        key_func = lambda tag: tag.name
        chart = super(cls.mro()[3], cls).create_from_data(
            subject, key_func, start, end)
        count_sum = sum(t.stats.count for t in chart.tags)
        for t in chart.tags:
            t.stats.__dict__['_count'] /= count_sum
        return chart 

class MonthlyChart(RollingChart):
    """A class for representing the monthly charts"""
    _period = {'name': 'month', 'duration': 1}
    
    @staticmethod
    def get_chart_list(subject):
        wcl = subject.weekly_chart_list
        months = set()
        for l in wcl:
            months.add(l.start.replace(day=1, hour=12, minute=0, second=0))
        months = list(months)
        months.sort()
        months[0] = wcl[0].start.replace(hour=12, minute=0, second=0)
        months.append(wcl[-1].end.replace(hour=12, minute=0, second=0))

        return [MonthlyChart(
                    subject=subject,
                    start=months[i],
                    end=months[i+1]
                )
               for i in xrange(len(months)-1)]
        
class MonthlyAlbumChart(RollingAlbumChart, MonthlyChart):
    """A class for representing the monthly album charts"""
    _chart_type = "album"
        
class MonthlyArtistChart(RollingArtistChart, MonthlyChart):
    """A class for representing the monthly artist charts"""
    _chart_type = "artist"

class MonthlyTrackChart(RollingTrackChart, MonthlyChart):
    """A class for representing the monthly track charts"""
    _chart_type = "track"

class MonthlyTagChart(RollingTagChart, MonthlyChart):
    """A class for representing the monthly tag charts"""
    _chart_type = "tag"

class QuaterlyChart(RollingChart):
    """A class for representing the three monthly charts"""
    _period = {'name': 'quater', 'duration': 3}

class QuaterlyAlbumChart(RollingAlbumChart, QuaterlyChart):
    """A class for representing the three monthly album charts"""
    _chart_type = "album"

class QuaterlyArtistChart(RollingArtistChart, QuaterlyChart):
    """A class for representing the three monthly artist charts"""
    _chart_type = "artist"

class QuaterlyTrackChart(RollingTrackChart, QuaterlyChart):
    """A class for representing the three monthly track charts"""
    _chart_type = "track"

class QuaterlyTagChart(RollingTagChart, QuaterlyChart):
    """A class for representing the three monthly tag charts"""
    _chart_type = "tag"

class HalfYearlyChart(RollingChart):
    """A class for representing the six monthly charts"""
    _period = {'name': 'half year', 'duration': 6}

class HalfYearlyAlbumChart(RollingAlbumChart, HalfYearlyChart):
    """A class for representing the six monthly album charts"""
    _chart_type = "album"

class HalfYearlyArtistChart(RollingArtistChart, HalfYearlyChart):
    """A class for representing the six monthly artist charts"""
    _chart_type = "artist"

class HalfYearlyTrackChart(RollingTrackChart, HalfYearlyChart):
    """A class for representing the six monthly track charts"""
    _chart_type = "track"

class HalfYearlyTagChart(RollingTagChart, HalfYearlyChart):
    """A class for representing the six monthly tag charts"""
    _chart_type = "tag"

class YearlyChart(RollingChart):
    """A class for representing the yearly charts"""
    _period = {'name': 'year', 'duration': 12}

class YearlyAlbumChart(RollingAlbumChart, YearlyChart):
    """A class for representing the yearly album charts"""
    _chart_type = "album"

class YearlyArtistChart(RollingArtistChart, YearlyChart):
    """A class for representing the yearly artist charts"""
    _chart_type = "artist"

class YearlyTrackChart(RollingTrackChart, YearlyChart):
    """A class for representing the yearly track charts"""
    _chart_type = "track"

class YearlyTagChart(RollingTagChart, YearlyChart):
    """A class for representing the yearly tag charts"""
    _chart_type = "tag"

__all__ = [
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
from datetime import datetime
import calendar

from lastfm.album import Album
from lastfm.artist import Artist
from lastfm.error import InvalidParametersError, LastfmError
from lastfm.stats import Stats
from lastfm.track import Track
from lastfm.tag import Tag