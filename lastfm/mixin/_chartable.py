#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm.mixin"

from lastfm.util import lazylist, logging
from lastfm.decorators import cached_property

def chartable(*chart_types):
    def wrapper(cls):
        @cached_property
        def weekly_chart_list(self):
            """
            a list of available weekly charts for this group
            @rtype: L{list} of L{WeeklyChart}
            """
            from lastfm.chart import WeeklyChart
            params = self._default_params(
                {'method': '%s.getWeeklyChartList' % self.__class__.__name__.lower()})
            data = self._api._fetch_data(params).find('weeklychartlist')
            return [
                    WeeklyChart.create_from_data(self._api, self, c)
                    for c in data.findall('chart')
                    ]
    
        @cached_property
        def monthly_chart_list(self):
            from lastfm.chart import MonthlyChart
            return MonthlyChart.get_chart_list(self)
        
        def _default_params(self, extra_params = None):
            if extra_params is not None:
                return extra_params
            else:
                return {}
        
        def get_weekly_album_chart(self, start = None, end = None):
            """
            Get an album chart for the group, for a given date range.
            If no date range is supplied, it will return the most 
            recent album chart for the group. 
            
            @param start:    the date at which the chart should start from (optional)
            @type start:     C{datetime.datetime}
            @param end:      the date at which the chart should end on (optional)
            @type end:       C{datetime.datetime}
            
            @return:         an album chart for the group
            @rtype:          L{WeeklyAlbumChart}
            
            @raise InvalidParametersError: Both start and end parameter have to be either
                                           provided or not provided. Providing only one of
                                           them will raise an exception.
            """
            from lastfm.chart import WeeklyChart, WeeklyAlbumChart
            params = self._default_params(
                {'method': '%s.getWeeklyAlbumChart' % self.__class__.__name__.lower()})
            params = WeeklyChart._check_chart_params(params, self, start, end)
            data = self._api._fetch_data(params).find('weeklyalbumchart')
            return WeeklyAlbumChart.create_from_data(self._api, self, data)
    
        @cached_property
        def recent_weekly_album_chart(self):
            """
            most recent album chart for the group
            @rtype: L{WeeklyAlbumChart}
            """
            return self.get_weekly_album_chart()
    
        @cached_property
        def weekly_album_chart_list(self):
            """
            a list of all album charts for this group in reverse-chronological
            order. (that means 0th chart is the most recent chart)
            @rtype: L{lazylist} of L{WeeklyAlbumChart}
            """
            wcl = list(self.weekly_chart_list)
            wcl.reverse()
            @lazylist
            def gen(lst):
                for wc in wcl:
                    try:
                        yield self.get_weekly_album_chart(wc.start, wc.end)
                    except LastfmError as ex:
                        logging.log_silenced_exceptions(ex)
            return gen()
        
        def get_monthly_album_chart(self, start = None, end = None):
            from lastfm.chart import MonthlyAlbumChart
            return MonthlyAlbumChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_monthly_album_chart(self):
            return self.get_monthly_album_chart()
        
        @cached_property
        def monthly_album_chart_list(self):
            mcl = list(self.monthly_chart_list)
            mcl.reverse()
            @lazylist
            def gen(lst):
                for mc in mcl:
                    try:
                        yield self.get_monthly_album_chart(mc.start, mc.end)
                    except LastfmError as ex:
                        logging.log_silenced_exceptions(ex)
            return gen()
    
        def get_quaterly_album_chart(self, start = None, end = None):
            from lastfm.chart import QuaterlyAlbumChart
            return QuaterlyAlbumChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_quaterly_album_chart(self):
            return self.get_quaterly_album_chart()
        
        def get_half_yearly_album_chart(self, start = None, end = None):
            from lastfm.chart import HalfYearlyAlbumChart
            return HalfYearlyAlbumChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_half_yearly_album_chart(self):
            return self.get_half_yearly_album_chart()
        
        def get_yearly_album_chart(self, start = None, end = None):
            from lastfm.chart import YearlyAlbumChart
            return YearlyAlbumChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_yearly_album_chart(self):
            return self.get_yearly_album_chart()
    
        def get_weekly_artist_chart(self, start = None, end = None):
            """
            Get an artist chart for the group, for a given date range.
            If no date range is supplied, it will return the most 
            recent artist chart for the group. 
            
            @param start:    the date at which the chart should start from (optional)
            @type start:     C{datetime.datetime}
            @param end:      the date at which the chart should end on (optional)
            @type end:       C{datetime.datetime}
            
            @return:         an artist chart for the group
            @rtype:          L{WeeklyArtistChart}
            
            @raise InvalidParametersError: Both start and end parameter have to be either
                                           provided or not provided. Providing only one of
                                           them will raise an exception.
            """
            from lastfm.chart import WeeklyChart, WeeklyArtistChart
            params = self._default_params(
                {'method': '%s.getWeeklyArtistChart' % self.__class__.__name__.lower()})
            params = WeeklyChart._check_chart_params(params, self, start, end)
            data = self._api._fetch_data(params).find('weeklyartistchart')
            return WeeklyArtistChart.create_from_data(self._api, self, data)
    
        @cached_property
        def recent_weekly_artist_chart(self):
            """
            most recent artist chart for the group
            @rtype: L{WeeklyArtistChart}
            """
            return self.get_weekly_artist_chart()
    
        @cached_property
        def weekly_artist_chart_list(self):
            """
            a list of all artist charts for this group in reverse-chronological
            order. (that means 0th chart is the most recent chart)
            @rtype: L{lazylist} of L{WeeklyArtistChart}
            """
            wcl = list(self.weekly_chart_list)
            wcl.reverse()
            @lazylist
            def gen(lst):
                for wc in wcl:
                    try:
                        yield self.get_weekly_artist_chart(wc.start, wc.end)
                    except LastfmError as ex:
                        logging.log_silenced_exceptions(ex)
            return gen()
        
        def get_monthly_artist_chart(self, start = None, end = None):
            from lastfm.chart import MonthlyArtistChart
            return MonthlyArtistChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_monthly_artist_chart(self):
            return self.get_monthly_artist_chart()
        
        @cached_property
        def monthly_artist_chart_list(self):
            mcl = list(self.monthly_chart_list)
            mcl.reverse()
            @lazylist
            def gen(lst):
                for mc in mcl:
                    try:
                        yield self.get_monthly_artist_chart(mc.start, mc.end)
                    except LastfmError as ex:
                        logging.log_silenced_exceptions(ex)
            return gen()
    
        def get_quaterly_artist_chart(self, start = None, end = None):
            from lastfm.chart import QuaterlyArtistChart
            return QuaterlyArtistChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_quaterly_artist_chart(self):
            return self.get_quaterly_artist_chart()
        
        def get_half_yearly_artist_chart(self, start = None, end = None):
            from lastfm.chart import HalfYearlyArtistChart
            return HalfYearlyArtistChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_half_yearly_artist_chart(self):
            return self.get_half_yearly_artist_chart()
        
        def get_yearly_artist_chart(self, start = None, end = None):
            from lastfm.chart import YearlyArtistChart
            return YearlyArtistChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_yearly_artist_chart(self):
            return self.get_yearly_artist_chart()
    
        def get_weekly_track_chart(self, start = None, end = None):
            """
            Get a track chart for the group, for a given date range.
            If no date range is supplied, it will return the most 
            recent artist chart for the group. 
            
            @param start:    the date at which the chart should start from (optional)
            @type start:     C{datetime.datetime}
            @param end:      the date at which the chart should end on (optional)
            @type end:       C{datetime.datetime}
            
            @return:         a track chart for the group
            @rtype:          L{WeeklyTrackChart}
            
            @raise InvalidParametersError: Both start and end parameter have to be either
                                           provided or not provided. Providing only one of
                                           them will raise an exception.
            """
            from lastfm.chart import WeeklyChart, WeeklyTrackChart
            params = self._default_params(
                {'method': '%s.getWeeklyTrackChart' % self.__class__.__name__.lower()})
            params = WeeklyChart._check_chart_params(params, self, start, end)
            data = self._api._fetch_data(params).find('weeklytrackchart')
            return WeeklyTrackChart.create_from_data(self._api, self, data)
    
        @cached_property
        def recent_weekly_track_chart(self):
            """
            most recent track chart for the group
            @rtype: L{WeeklyTrackChart}
            """
            return self.get_weekly_track_chart()
    
        @cached_property
        def weekly_track_chart_list(self):
            """
            a list of all track charts for this group in reverse-chronological
            order. (that means 0th chart is the most recent chart)
            @rtype: L{lazylist} of L{WeeklyTrackChart}
            """
            wcl = list(self.weekly_chart_list)
            wcl.reverse()
            @lazylist
            def gen(lst):
                for wc in wcl:
                    try:
                        yield self.get_weekly_track_chart(wc.start, wc.end)
                    except LastfmError as ex:
                        logging.log_silenced_exceptions(ex)
            return gen()
        
        def get_monthly_track_chart(self, start = None, end = None):
            from lastfm.chart import MonthlyTrackChart
            return MonthlyTrackChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_monthly_track_chart(self):
            return self.get_monthly_track_chart()
        
        @cached_property
        def monthly_track_chart_list(self):
            mcl = list(self.monthly_chart_list)
            mcl.reverse()
            @lazylist
            def gen(lst):
                for mc in mcl:
                    try:
                        yield self.get_monthly_track_chart(mc.start, mc.end)
                    except LastfmError as ex:
                        logging.log_silenced_exceptions(ex)
            return gen()
    
        def get_quaterly_track_chart(self, start = None, end = None):
            from lastfm.chart import QuaterlyTrackChart
            return QuaterlyTrackChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_quaterly_track_chart(self):
            return self.get_quaterly_track_chart()
        
        def get_half_yearly_track_chart(self, start = None, end = None):
            from lastfm.chart import HalfYearlyTrackChart
            return HalfYearlyTrackChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_half_yearly_track_chart(self):
            return self.get_half_yearly_track_chart()
        
        def get_yearly_track_chart(self, start = None, end = None):
            from lastfm.chart import YearlyTrackChart
            return YearlyTrackChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_yearly_track_chart(self):
            return self.get_yearly_track_chart()
    
        def get_weekly_tag_chart(self, start = None, end = None):
            """
            Get a tag chart for the group, for a given date range.
            If no date range is supplied, it will return the most 
            recent tag chart for the group. 
            
            @param start:    the date at which the chart should start from (optional)
            @type start:     C{datetime.datetime}
            @param end:      the date at which the chart should end on (optional)
            @type end:       C{datetime.datetime}
            
            @return:         a tag chart for the group
            @rtype:          L{WeeklyTagChart}
            
            @raise InvalidParametersError: Both start and end parameter have to be either
                                           provided or not provided. Providing only one of
                                           them will raise an exception.
                                           
            @note: This method is a composite method. It is not provided directly by the
                   last.fm API. It uses other methods to collect the data, analyzes it and
                   creates a chart. So this method is a little heavy to call, as it does
                   mulitple calls to the API. 
            """
            from lastfm.chart import WeeklyChart, WeeklyTagChart
            WeeklyChart._check_chart_params({}, self, start, end)
            return WeeklyTagChart.create_from_data(self._api, self, start, end)
    
        @cached_property
        def recent_weekly_tag_chart(self):
            """
            most recent tag chart for the group
            @rtype: L{WeeklyTagChart}
            """
            return self.get_weekly_tag_chart()
    
        @cached_property
        def weekly_tag_chart_list(self):
            """
            a list of all tag charts for this group in reverse-chronological
            order. (that means 0th chart is the most recent chart)
            @rtype: L{lazylist} of L{WeeklyTagChart}
            """
            wcl = list(self.weekly_chart_list)
            wcl.reverse()
            @lazylist
            def gen(lst):
                for wc in wcl:
                    try:
                        yield self.get_weekly_tag_chart(wc.start, wc.end)
                    except LastfmError as ex:
                        logging.log_silenced_exceptions(ex)
            return gen()
        
        def get_monthly_tag_chart(self, start = None, end = None):
            from lastfm.chart import MonthlyTagChart
            return MonthlyTagChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_monthly_tag_chart(self):
            return self.get_monthly_tag_chart()
        
        @cached_property
        def monthly_tag_chart_list(self):
            mcl = list(self.monthly_chart_list)
            mcl.reverse()
            @lazylist
            def gen(lst):
                for mc in mcl:
                    try:
                        yield self.get_monthly_tag_chart(mc.start, mc.end)
                    except LastfmError as ex:
                        logging.log_silenced_exceptions(ex)
            return gen()
        
        def get_quaterly_tag_chart(self, start = None, end = None):
            from lastfm.chart import QuaterlyTagChart
            return QuaterlyTagChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_quaterly_tag_chart(self):
            return self.get_quaterly_tag_chart()
        
        def get_half_yearly_tag_chart(self, start = None, end = None):
            from lastfm.chart import HalfYearlyTagChart
            return HalfYearlyTagChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_half_yearly_tag_chart(self):
            return self.get_half_yearly_tag_chart()
        
        def get_yearly_tag_chart(self, start = None, end = None):
            from lastfm.chart import YearlyTagChart
            return YearlyTagChart.create_from_data(self, start, end)
    
        @cached_property
        def recent_yearly_tag_chart(self):
            return self.get_yearly_tag_chart()
        
        cls.weekly_chart_list = weekly_chart_list
        cls.monthly_chart_list = monthly_chart_list
        
        if not hasattr(cls, '_default_params'):
            cls._default_params = _default_params
        
        if not hasattr(cls, '_mixins'):
            cls._mixins = []
        cls._mixins.extend(['weekly_chart_list', 'monthly_chart_list'])
        
        method_names = [
            'get_weekly_%s_chart', 'recent_weekly_%s_chart', 'weekly_%s_chart_list',
            'get_monthly_%s_chart', 'recent_monthly_%s_chart', 'monthly_%s_chart_list',
            'get_quaterly_%s_chart', 'recent_quaterly_%s_chart',
            'get_half_yearly_%s_chart', 'recent_half_yearly_%s_chart',
            'get_yearly_%s_chart', 'recent_yearly_%s_chart'
        ]    
        for chart_type in chart_types:
            for method_name in method_names:
                setattr(cls, method_name % chart_type, locals()[method_name % chart_type])
                cls._mixins.append(method_name % chart_type)
        
        return cls
    return wrapper

from lastfm.error import LastfmError
    