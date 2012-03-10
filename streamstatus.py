import urllib2
import HTMLParser
import MultiDict
import logging

def get_status(icecast_server):
    try:
        result = urllib2.urlopen(urllib2.Request(icecast_server,
                                            headers={'User-Agent': 'Mozilla'}))
    except HTTPError as e:
        if e.code == 403: #assume it's a full server
            logging.warning("Can't connect to status page; listener count reached")
            f_fallback = MultiDict.OrderedMultiDict()
            f_fallback['Stream Title'] = 'Fallback at R/a/dio'
            f_fallback['Stream Description'] = 'Sorry we are currently down'
            f_fallback['Content Type'] = 'audio/mpeg'
            f_fallback['Mount started'] = 'Thu, 08 Mar 2012 00:20:07 +0100'
            f_fallback['Bitrate'] = '192'
            f_fallback['Current Listeners'] = '0'
            f_fallback['Peak Listeners'] = '200'
            f_fallback['Stream Genre'] = 'ZTS'
            f_fallback['Stream URL'] = 'http://r-a-dio.com'
            f_fallback['Current Song'] = 'fallback'
            f_main = MultiDict.OrderedMultiDict()
            f_main['Stream Title'] = 'r/a/dio'
            f_main['Stream Description'] = 'listener maxed, placeholder'
            f_main['Content Type'] = 'audio/mpeg'
            f_main['Mount started'] = 'Thu, 08 Mar 2012 00:20:07 +0100'
            f_main['Bitrate'] = '192'
            f_main['Current Listeners'] = '500'
            f_main['Peak Listeners'] = '500'
            f_main['Stream Genre'] = 'Weeaboo'
            f_main['Stream URL'] = 'http://r-a-dio.com'
            f_main['Current Song'] = 'Unknown'
            return {'/fallback.mp3': f_fallback, '/main.mp3': f_main}
    except:
        # catching all why????
        logging.exception("Can't connect to status page")
    else:
        parser = StatusParser()
        for line in result:
            parser.feed(line)
        parser.close()
        return parser.result
        
class StatusParser(HTMLParser.HTMLParser):
    def __init__(self):
        HTMLParser.HTMLParser.__init__(self)
        self._current_mount = None
        self.result = {}
        self._td = False
        self._mount = False
        self._enter = False
    def handle_starttag(self, tag, attrs):
        attrs = MultiDict.OrderedMultiDict(attrs)
        if (tag == "td"):
            self._td = Tag(attrs)
            self._td['class'] = None
        elif (tag == "h3") and (self._td):
            self._mount = Tag(attrs)
    def handle_endtag(self, tag):
        if (tag == "td"):
            self._td = None
        elif (tag == "h3") and (self._td):
            self._mount = None
        elif (tag == "table") and (self._current_mount):
            if (self._enter):
                self._enter = False
            else:
                self._enter = True
    def handle_data(self, data):
        if (self._mount) and (self._td):
            self._current_mount = data.split(" ")[2]
            self.result[self._current_mount] = MultiDict.OrderedMultiDict()
        elif (self._enter) and (self._td) and (self._current_mount):
            if ("streamdata" in self._td.getall("class")):
                self.result[self._current_mount][self._type] = data
            else:
                self._type = data[:-1]
            
class Tag(object):
    attr = MultiDict.OrderedMultiDict()
    def __init__(self, attrs):
        self.attr = attrs
    def __getattr__(self, name):
        return getattr(self.attr, name)
    def __setitem__(self, name, value):
        self.attr[name] = value
"""
                    webcom.send_nowplaying(None, self.djid,
                    self.listeners, self.bitrate, self.isafk(),
                    self._start_time, ed_time)"""