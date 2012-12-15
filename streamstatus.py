import urllib2
import HTMLParser
import MultiDict
import logging
import config
from urllib2 import HTTPError
import manager


def get_listener_count(server_name='stream'):
    with manager.MySQLCursor() as cur:
        cur.execute("SELECT * FROM `relays` WHERE `relay_name`=%s;", (server_name,))
        if cur.rowcount == 1:
            row = cur.fetchone()
            port = row['port']
            mount = row['mount']
            url = 'http://{server}.r-a-d.io:{port}/status.xsl'.format(server=server_name,port=port)
        else:
            raise KeyError("unknown relay \"" + server_name + "\"")
    try:
        result = urllib2.urlopen(urllib2.Request(url,
                                            headers={'User-Agent': 'Mozilla'}), timeout=2)
    except:
        #logging.exception("Could not get listener count for server {server}".format(server=server_name))
        with manager.MySQLCursor() as cur:
            cur.execute("UPDATE `relays` SET listeners=0, active=0 WHERE relay_name=%s;", (server_name,))
        raise
    else:
        parser = StatusParser()
        for line in result:
            parser.feed(line)
        parser.close()
        result = parser.result
        if mount in result:
            if 'Current Listeners' in result[mount]:
                listeners = int(result[mount]['Current Listeners'])
                with manager.MySQLCursor() as cur:
                    cur.execute("UPDATE `relays` SET listeners=%s, active=1 WHERE relay_name=%s;", (listeners, server_name))
                return listeners
        else:
            with manager.MySQLCursor() as cur:
                cur.execute("UPDATE `relays` SET listeners=0, active=0 WHERE relay_name=%s;", (server_name,))
            return -1
    logging.debug('Could not get listener count for server ' + server_name)
    return -1

timeout = {}
def get_all_listener_count():
    import time
    counts = {}
    with manager.MySQLCursor() as cur:
        cur.execute("SELECT * FROM `relays`;")
        for row in cur:
            name = row['relay_name']
            count = 0
            if name in timeout and (time.time() - timeout[name]) < 10*60:
                count = -1
            else:
                if name in timeout:
                    del timeout[name]
                try:
                    count = get_listener_count(name)
                except urllib2.HTTPError as err:
                    pass # fuck this
                except urllib2.URLError as err:
                    if 'timed out' in err.reason:
                        timeout[name] = time.time()
                    count = -1
                except:
                    count = -1
            counts[name] = count
    return counts


def get_status(icecast_server):
    try:
        result = urllib2.urlopen(urllib2.Request(icecast_server,
                                            headers={'User-Agent': 'Mozilla'}))
    except HTTPError as e:
        if e.code == 403: #assume it's a full server
            logging.warning("Can't connect to status page; Assuming listener limit reached")
            f_fallback = MultiDict.OrderedMultiDict()
            f_fallback['Stream Title'] = 'Fallback at R/a/dio'
            f_fallback['Stream Description'] = 'Sorry we are currently down'
            f_fallback['Content Type'] = 'audio/mpeg'
            f_fallback['Mount started'] = 'Thu, 08 Mar 2012 00:20:07 +0100'
            f_fallback['Bitrate'] = '192'
            f_fallback['Current Listeners'] = '0'
            f_fallback['Peak Listeners'] = '200'
            f_fallback['Stream Genre'] = 'ZTS'
            f_fallback['Stream URL'] = 'http://r-a-d.io'
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
            f_main['Stream URL'] = 'http://r-a-d.io'
            f_main['Current Song'] = 'Unknown'
            return {'/fallback.mp3': f_fallback, '/main.mp3': f_main}
        else:
            logging.exception("HTTPError occured in status retrieval")
    except:
        # catching all why????
        logging.exception("Can't connect to status page")
    else:
        parser = StatusParser()
        for line in result:
            parser.feed(line)
        parser.close()
        result = parser.result
        if config.icecast_mount in result:
            all_listeners = get_all_listener_count()
            total_count = reduce(lambda x,y: x+y if x > 0 and y > 0 else x, all_listeners.values())
            result[config.icecast_mount]['Current Listeners'] = str(total_count)
        return parser.result or {}
    return {}
def get_listeners():
    listeners = {}
    with manager.MySQLCursor() as cur:
        cur.execute("SELECT * FROM `relays` WHERE listeners > 0 AND admin_auth != '';")
        for row in cur:
            server = row['relay_name']
            port = row['port']
            mount= row['mount']
            auth = row['admin_auth']
            url = 'http://{server}.r-a-d.io:{port}'.format(server=server,port=port)
            try:
                result = urllib2.urlopen(urllib2.Request(url+'/admin/listclients.xsl?mount='+mount,
                                                                    headers={'User-Agent': 'Mozilla',
                                                                    'Authorization': 'Basic ' + auth,
                                                                    'Referer': url+'/admin/'}))
            except:
                continue
            parser = ListenersParser()
            for line in result:
                parser.feed(line)
            parser.close()
            listeners.update(dict((l['ip'], l) for l in parser.result))
    listeners = listeners.values()
    return listeners

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

class ListenersParser(HTMLParser.HTMLParser):
    def __init__(self):
        HTMLParser.HTMLParser.__init__(self)
        self.result = []
        self._values = {}
        self._td = None
        self._tablefound = False
    def handle_starttag(self, tag, attrs):
        attrs = MultiDict.OrderedMultiDict(attrs)
        if (tag == "table" and "bordercolor" in attrs and attrs['bordercolor'] == "#C0C0C0"):
            self._tablefound = True
        elif (tag == "td"):
            self._td = Tag(attrs)            
    def handle_endtag(self, tag):
        if tag == "td" and self._td:
            self._td = None
        elif tag == "table" and self._tablefound:
            self._tablefound = False
    def handle_data(self, data):
        if self._tablefound and self._td:
            if "align" in self._td.attr and "center" in self._td.getall("align"):
                l = len(self._values)
                if (l==0): # it's ip
                    self._values['ip'] = str(data)
                elif (l==1): # it's time
                    self._values['time'] = int(data)
                elif (l==2): # it's player
                    self._values['player'] = str(data)
                elif (l==3): # it's kick
                    self.result.append(self._values)
                    self._values = {}


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