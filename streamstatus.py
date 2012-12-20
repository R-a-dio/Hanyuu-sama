import urllib2
import HTMLParser
import MultiDict
import logging
import config
from urllib2 import HTTPError
import manager
import xmltodict


def get_listener_count(server_name, mount, port):
    url = "http://" + server_name + ".r-a-d.io:" + str(port) + mount # HURR I LIKE TO DO 12 MYSQL QUERIES EVERY FEW SECONDS
    # tip: you just did select * from relays;. You do not need to then individually query every server_name...
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
        try:
            result = parser.parse(result.read(), mount)
            listeners = int(result[server_name]['Current Listeners'])
            with manager.MySQLCursor() as cur:
                cur.execute("UPDATE `relays` SET listeners=%s, active=1 WHERE relay_name=%s;", (listeners, server_name))
            return listeners
        except:
            with manager.MySQLCursor() as cur:
                cur.execute("UPDATE `relays` SET listeners=0, active=0 WHERE relay_name=%s;", (server_name,))
    logging.debug('Could not get listener count for server ' + server_name)
    return -1

timeout = {}
dns_spamfilter = bootstrap.Switch(True)
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
                    count = get_listener_count(name, row["mount"], row["port"])
                except urllib2.HTTPError as err:
                    if err.code == 403: # incorrect login
                        if not dns_spamfilter:
                            logging.warning("HTTPError to {}. sudo rndc flush if it is correct, and update DNS".format(name))
                            dns_spamfilter.reset()
                    else:
                        #logging.warning("HTTPError on {}".format(name))
                        pass
                except urllib2.URLError as err:
                    if 'timed out' in err.reason:
                        timeout[name] = time.time()
                    count = -1
                except:
                    count = -1
            counts[name] = count
    return counts


def get_status(icecast_server, server_name):
    try:
        result = urllib2.urlopen(urllib2.Request(icecast_server,
                                            headers={'User-Agent': 'Mozilla'}))
    except HTTPError as e:
        if e.code == 403: #assume it's a full server
            if not dns_spamfilter:
                logging.warning("Can't connect to mountpoint; Assuming listener limit reached")
                dns_spamfilter.reset()
        else:
            logging.exception("HTTPError occured in status retrieval")
    except:
        # catching all why????
        logging.exception("Can't connect to status page")
    else:
        parser = StatusParser()
        result = parser.parse(result.read(), server_name)
        all_listeners = get_all_listener_count()
        total_count = reduce(lambda x,y: x+y if x > 0 and y > 0 else x, all_listeners.values())
        result[server_name]['Current Listeners'] = str(total_count) # WHYYYYYYYYYYYYY DID YOU DO THIS
        return result or {}
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
                result = urllib2.urlopen(urllib2.Request(url+'/admin/listclients?mount='+mount,
                                                                    headers={'User-Agent': 'Mozilla',
                                                                    'Authorization': 'Basic ' + auth,
                                                                    'Referer': url+'/admin/'}))
            except:
                continue
            parser = ListenersParser()
            parser.parse(result)
            listeners.update(dict((l['ip'], l) for l in parser.result()))
    return listeners.values()

class StatusParser(object):
    def __init__(self):
        self.result = {}
        self._current_mount = None
        self._mount = False
    def parse(self, xml, server_name):
        try:
            xml_dict = xmltodict.parse(xml, xml_attribs=False, cdata_separator="\n")
            # cdata is a multiline block (Icecast)
            # fetch annotation
            xml_dict = xml_dict["playlist"]["trackList"]["track"] # remove the useless stuff
            annotations = xml_dict["annotation"]["#text"].split("\n")
            self.result[server_name] = {}
            for annotation in annotations:
                tmp = annotation.split(":", 1)
                self.result[server_name][tmp[0]] = tmp[1] # herp
            self.result[server_name]["Current Song"] =  xml_dict["title"]["#text"] # unicode strings yay!
        except:
            logging.error("Failed to parse XML Status data.")
            raise
        return self.result       
        
class ListenersParser(object):
    def __init__(self):
        """
        value keys:
        ['ip']
        ['time']
        ['player']
        """
        self._result = []
        self._values = {}
    def parse(self, xml):
        try:
            xml_dict = xmltodict(xml, xml_attribs=False)
            xml_dict = xml_dict["icestats"]["source"]["listener"]
            for listener in xml_dict:
                self._values['ip'] = listener['IP']
                self._values['player'] = listener['UserAgent']
                self._values['time'] = listener['Connected']
                self.result.append(self._values)
        except:
            logging.warning("Couldn't parse listener XML - ListenersParser")
    def result(self):
        return self.result

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
    self._start_time, ed_time)
"""
