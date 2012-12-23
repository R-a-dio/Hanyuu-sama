import requests
import logging
import config
import manager
import xmltodict
import itertools
from bootstrap import Switch

dns_spamfilter = Switch(True)

def get_listener_count(server_name, mount=None, port=None):
    if mount is None: # assume not port, too. naivity at its best.
        with manager.MySQLCursor() as cur:
            cur.execute("SELECT port, mount FROM `relays` WHERE `relay_name`=%s;",
                            (server_name,))
            if cur.rowcount == 1:
                row = cur.fetchone()
                port = row['port']
                mount = row['mount']
            else:
                raise KeyError("Unknown relay {}".format(server_name))
    url = "http://{name}.r-a-d.io:{port}{mount}.xspf".format(name=server_name,
                                            port=port, mount=mount)
    # tip: you just did select * from relays;.
    try:
        result = requests.get(url, headers={'User-Agent': 'Mozilla'}, timeout=2)
        result.raise_for_status() # raise exception if status code is abnormal
    except requests.ConnectionError:
        #logging.exception("Could not get listener count for server {server}"
        #.format(server=server_name))
        with manager.MySQLCursor() as cur:
            cur.execute("UPDATE `relays` SET listeners=0, active=0 WHERE relay_name=%s;",
                                                (server_name,))
    except requests.HTTPError:
        logging.info("HTTP Error, L35, get_listener_count")
    else:
        parser = StatusParser()
        try:
            result = parser.parse(result.text)
            listeners = int(result['Current Listeners'])
            with manager.MySQLCursor() as cur:
                cur.execute("UPDATE `relays` SET listeners=%s, active=1 WHERE relay_name=%s;",
                                                (listeners, server_name))
            return listeners
        except:
            with manager.MySQLCursor() as cur:
                cur.execute("UPDATE `relays` SET listeners=0, active=0 WHERE relay_name=%s;",
                                                (server_name,))
            logging.exception()
    logging.debug('Could not get listener count for server {}'.format(server_name))
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
                    count = get_listener_count(name, row["mount"], row["port"])
                except (requests.HTTPError,
                        requests.ConnectionError) as e: # rare
                    if not dns_spamfilter:
                        logging.warning(\
                        "Connection Error to {}. sudo rndc flush if it is correct, and update DNS"\
                        .format(name))
                        dns_spamfilter.reset()
                    else:
                        #logging.warning("HTTPError on {}".format(name))
                        pass
                except requests.exceptions.Timeout:
                    timeout[name] = time.time()
                    count = -1
                except:
                    logging.exception()
                    count = -1
            counts[name] = count
    return counts


def get_status(server_name):
    """
    Gets the current status of the master server, and the listener counts of all of the
    slave relays, aggregating them, filtering negative, and summing them to give an
    artificial Master server listener count used by Hanyuu in every StatusUpdate call.
    """
    with manager.MySQLCursor() as cur:
        cur.execute("SELECT port, mount FROM `relays` WHERE relay_name=%s;", (server_name,))
        if cur.rowcount == 1:
                row = cur.fetchone()
                port = row['port']
                mount = row['mount']
        else:
            logging.critical("Master server is not in the config or database and get_status failed.")
        try:
            result = requests.get("http://{server}.r-a-d.io:{port}{mount}.xspf".format(
                                    server=server_name, port=port, mount=mount),
                                                headers={'User-Agent': 'Mozilla'}, timeout=2)
        except requests.HTTPError as e: # rare, mostly 403
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
            parser.parse(result.text)
            result = parser.result
            all_listeners = get_all_listener_count()
            total_count = sum(itertools.ifilter(lambda x: x>=0, all_listeners.values()))
            result['Current Listeners'] = total_count # WHYYYYYYYYYYYYY DID YOU DO THIS
            return result
    return {}
def get_listeners():
    """
    Used by player_stats (internal) to generate listener statistics and graphs
    """
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
                result = requests.get('{url}/admin/listclients?mount={mount}'.format(url=url,
                                        mount=mount), headers={'User-Agent': 'Mozilla',
                                        'Referer': '{url}/admin/'.format(url=url),
                                        'Authorization': 'Basic {}'.format(auth)}, timeout=2)
                result.raise_for_status() # None if normal
            except:
                logging.exception()
            parser = ListenersParser()
            parser.parse(result.text)
            listeners.update(dict((l['ip'], l) for l in parser.result))
    return listeners.values()

class StatusParser(object):
    def __init__(self):
        self.result = {}
    def parse(self, xml):
        try:
            xml_dict = xmltodict.parse(xml, xml_attribs=False, cdata_separator="\n")
            # cdata is a multiline block (Icecast)
            # fetch annotation
            xml_dict = xml_dict["playlist"]["trackList"]["track"] # remove the useless stuff
            annotations = xml_dict["annotation"].split("\n")
            for annotation in annotations:
                tmp = annotation.split(":", 1)
                self.result[tmp[0]] = tmp[1].strip() # herp
            self.result["Current Song"] =  xml_dict["title"] # unicode strings yay!
        except:
            logging.exception("Failed to parse XML Status data.")
            raise       
        
class ListenersParser(object):
    def __init__(self):
        self.result = []
        self._values = {}
    def parse(self, xml):
        """
        parses the XML produced by icecast using xmltodict, acting like it is
        really JSON, or a python dict, to make it much easier to handle.
        xml should be a string, not a url!
        (while it supports filenames, it doesnt support urls)
        """
        try:
            xml_dict = xmltodict.parse(xml, xml_attribs=False)
            xml_dict = xml_dict["icestats"]["source"]["listener"]
            for listener in xml_dict:
                self._values['ip'] = listener['IP']
                self._values['player'] = listener['UserAgent']
                self._values['time'] = listener['Connected']
                self.result.append(self._values)
        except:
            logging.exception("Couldn't parse listener XML - ListenersParser")

