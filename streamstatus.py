import requests
import logging
import config
import manager
import xmltodict
import itertools
from bootstrap import Switch

dns_spamfilter = Switch(True) # 15 second resetting spamfilter
timeout = {}

def relay_listeners(server_name, mount=None, port=None):
    """
    Gets the individual listener count for each given relay.
    If given just a name, looks up details using the name
    """
    if mount is None: # assume not port, too. naivity at its best.
    # (if you dont have one, it's useless anyway)
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
    try:
        result = requests.get(url, headers={'User-Agent': 'Mozilla'}, timeout=2)
        result.raise_for_status() # raise exception if status code is abnormal
    except requests.ConnectionError:
        with manager.MySQLCursor() as cur:
            cur.execute("UPDATE `relays` SET listeners=0, active=0 WHERE relay_name=%s;",
                                                (server_name,))
    except requests.HTTPError:
        with manager.MySQLCursor() as cur:
            cur.execute("UPDATE `relays` SET active=0 WHERE relay_name=%s;",
                                                (server_name,))
    else:
        try:
            result = parse_status(result)
            listeners = int(result.get('Current Listeners', 0))
            with manager.MySQLCursor() as cur:
                cur.execute("UPDATE `relays` SET listeners=%s, active=1 WHERE relay_name=%s;",
                                                (listeners, server_name))
            return listeners
        except:
            with manager.MySQLCursor() as cur:
                cur.execute("UPDATE `relays` SET listeners=0, active=0 WHERE relay_name=%s;",
                                                (server_name,))
            logging.exception("get listener count")
    return -1

def get_listener_count():
    """
    Gets a list of all current relay's listeners and filters inactive relays.
    It then returns the total number of listeners on all relays combined.
    This is reported to manager.Status().listeners
    """
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
                    count = relay_listeners(name, row["mount"], row["port"])
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
                    logging.exception("get all listener count")
                    count = -1
            counts[name] = count
    return counts


def get_status(server_name):
    """
    Gets the current status of the master server, and the listener counts of all of the
    slave relays, aggregating them, filtering negative, and summing them to give an
    artificial Master server listener count used by Hanyuu in every StatusUpdate call.
    """
    offline = { "Online" : False } # Pointless but easier to type. Also makes more sense.
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
        except requests.ConnectionError:
            logging.exception("Connection interrupted to master server")
        except:
            logging.exception("Can't connect to master status page. Is Icecast running?")
        else:
            result = parse_status(result.content) # bytestring
            if result:
                all_listeners = get_listener_count()
                total_count = sum(itertools.ifilter(lambda x: x>=0, all_listeners.values()))
                result["Current Listeners"] = total_count
            return result
        return offline # returned in all of the things above that do not return.
    logging.warning("Something just went horribly wrong in get_status; someone yell at Hiroto")
    return offline # impossible event.
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
                logging.exception("get_listeners")
            parser = ListenersParser()
            parser.parse(result.content)
            listeners.update(dict((l['ip'], l) for l in parser.result))
    return listeners.values()

def parse_status(xml):
    """
    Function to parse the XML returned from a mountpoint.
    Input must be a bytestring as to avoid UnicodeDecodeError from stopping
    Parsing. The only meaningful result is "Current Listeners".
    
    Logic behind returning an explicit "Online" key is readability
    """
    result = { "Online" : False } # Assume False by default
    try:
        xml_dict = xmltodict.parse(xml, xml_attribs=False, cdata_separator="\n") # CDATA required
        try:
            xml_dict = xml_dict.get('playlist', {}).get('trackList', {}).get('track', None)
        except AttributeError: # No mountpoint it seems, just ditch an empty result
            return result
        else:
            if xml_dict is None: # We got none returned from the get anyway
                return result
        annotations = xml_dict["annotation"].split("\n")
        for annotation in annotations:
            result[tmp[0]] = tmp[1].strip() # no need whatsoever to decode anything here. It's not needed by NP()
        result["Online"] = True
    except UnicodeDecodeError: # we have runes, but we know we are online. This should not even be possible (requests.get.content)
        result["Online"] = True
        result["Current Song"] = u"" # Erase the bad stuff. However, keep in mind stream title can do this (anything user input...)
    except:
        logging.exception("Failed to parse XML Status data.") 
    return result # cleaner and easier to read falling back to original function scope (instead of 5 returns)
        
class ListenersParser(object): # NB: Not converting this to a function because it would break the thing that uses it.
    def __init__(self):
        self.result = []
    def parse(self, xml):
        """
        parses the XML produced by icecast using xmltodict, acting like it is
        really JSON, or a python dict, to make it much easier to handle.
        xml should be a string, not a url!
        (while it supports filenames, it doesnt support urls)
        """
        if isinstance(xml, unicode):
            xml = xml.encode('utf-8') # This line shouldnt be called, because the input should be a bytestring anyway...
        try:
            xml_dict = xmltodict.parse(xml, xml_attribs=False)
            xml_dict = xml_dict["icestats"]["source"]["listener"]
            for listener in xml_dict:
                _tmp = {}
                _tmp['ip'] = listener['IP']
                _tmp['player'] = listener['UserAgent']
                _tmp['time'] = listener['Connected']
                self.result.append(_tmp)
        except:
            logging.exception("Couldn't parse listener XML - ListenersParser")

