from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import requests
import xmltodict
import itertools
import pylibmc
from . import logger, Status
from .. import utils
from ..db import models


dns_spamfilter = utils.Switch(True) # 15 second resetting spamfilter
timeout = {}



def relay_listeners(server_name, mount=None, port=None):
    """
    Gets the individual listener count for a given relay.
    If given just a name, looks up details using the name
    """
    if mount is None:
        result = models.Relay.select().where(models.Relay.subdomain == server_name)
        if result.count() == 1:
            port = result[0].port
            mount = result[0].mountpoint
        else:
            raise KeyError("Unknown relay {}".format(server_name))
    url = "http://{name}.r-a-d.io:{port}{mount}.xspf".format(name=server_name,
                                            port=port, mount=mount)
    try:
        result = requests.get(url, headers={'User-Agent': 'Mozilla'}, timeout=2)
        result.raise_for_status() # raise exception if status code is abnormal
    except requests.ConnectionError:
        models.Relay.update(listeners=0, active=0)\
                    .where(models.Relay.subdomain == server_name)
        models.Relay.save()
    except requests.HTTPError:
        # why not listeners here too?
        models.Relay.update(active=0)\
                    .where(models.Relay.subdomain == server_name)
        models.Relay.save()
    else:
        try:
            result = parse_status(result.content)
            listeners = int(result.get('Current Listeners', 0))
            models.Relay.update(listeners=listeners, active=1)\
                        .where(models.Relay.subdomain == server_name)
            models.Relay.save()
            return listeners
        except:
            models.Relay.update(listeners=0, active=0)\
                        .where(models.Relay.subdomain == server_name)
            models.Relay.save()
            logger.exception("Could not parse listener count for {}")\
                .format(server_name)
    return -1

def get_listener_count():
    """
    Gets a list of all current relay's listeners and filters inactive relays.
    It then returns the total number of listeners on all relays combined.
    """
    import time
    counts = {}
    result = models.Relay.select()
    for relay in result:
        name = relay.subdomain
        count = 0
        if name in timeout and (time.time() - timeout[name]) < 10*60:
            count = -1
        else:
            if name in timeout:
                del timeout[name]
            try:
                count = relay_listeners(name, relay.mountpoint, relay.port)
            except (requests.HTTPError,
                    requests.ConnectionError) as e: # rare
                if not dns_spamfilter:
                    logger.warning(\
                    "Connection error to {}. sudo rndc flush if it is correct, and update DNS"\
                    .format(name))
                    dns_spamfilter.reset()
            except requests.exceptions.Timeout:
                timeout[name] = time.time()
                count = -1
            except:
                logger.exception("Unknown exception when getting all listeners")
                count = -1
        counts[name] = count
    return counts

def get_status(server_name='stream0'):
    """
    Gets the current status of the master server, and the listener counts of all of the
    slave relays, aggregating them, filtering negative, and summing them to give an
    artificial Master server listener count used by Hanyuu in every StatusUpdate call.
    """
    result = { "Online" : False } # Pointless but easier to type. Also makes more sense.
    master = models.Relay.select()\
                         .where(models.Relay.subdomain == server_name)
    if master.count() == 1:
        port = master[0].port
        mount = master[0].mountpoint
    else:
        logger.critical("Master server is not in the config or database and get_status failed.")
    try:
        result = requests.get("http://{server}.r-a-d.io:{port}{mount}.xspf".format(
                                server=server_name, port=port, mount=mount),
                                            headers={'User-Agent': 'Mozilla'}, timeout=2)
    except requests.HTTPError as e: # rare, mostly 403
        if not dns_spamfilter:
            logger.warning("Can't connect to mountpoint; Assuming listener limit reached")
            dns_spamfilter.reset()
        else:
            logger.exception("HTTPError occured in status retrieval")
    except requests.ConnectionError:
        logger.exception("Connection interrupted to master server")
    except:
        logger.exception("Can't connect to master status page. Is Icecast running?")
    else:
        result = parse_status(result.content) # bytestring
        if result:
            all_listeners = get_listener_count()
            total_count = sum(itertools.ifilter(lambda x: x>=0, all_listeners.values()))
            result["Current Listeners"] = total_count
    return result

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
        annotations = xml_dict.get("annotation", False)
        if not annotations: # edge case for having nothing...
            return result
        annotations = annotations.split("\n")
        for annotation in annotations:
            tmp = annotation.split(":", 1)
            result[tmp[0]] = tmp[1].strip() # no need whatsoever to decode anything here. It's not needed by NP()
        result["Online"] = True
        if xml_dict["title"] is None:
            result["Current Song"] = u"" # /shrug
        else:
            result["Current Song"] = xml_dict.get("title", u"")
    except UnicodeDecodeError: # we have runes, but we know we are online. This should not even be possible (requests.get.content)
        result["Online"] = True
        result["Current Song"] = u"" # Erase the bad stuff. However, keep in mind stream title can do this (anything user input...)
    except:
        logger.exception("Failed to parse XML Status data.") 
    return result # cleaner and easier to read falling back to original function scope (instead of 5 returns)
        

def parse_listeners(xml):
    """
    parses the XML produced by icecast using xmltodict, acting like it is
    really JSON, or a python dict, to make it much easier to handle.
    xml should be a string, not a url!
    (while it supports filenames, it doesnt support urls)
    """
    result = []
    try:
        xml_dict = xmltodict.parse(xml, xml_attribs=False)
        xml_dict = xml_dict["icestats"]["source"]["listener"]
        for listener in xml_dict:
            _tmp = {}
            _tmp['ip'] = listener['IP']
            _tmp['player'] = listener['UserAgent']
            _tmp['time'] = listener['Connected']
            result.append(_tmp)
        return result
    except:
        logger.exception("Couldn't parse listener XML - ListenersParser")
        return []
        
def get_listeners():
    """
    Used by player_stats (internal) to generate listener statistics and graphs
    """
    listeners = {}
    result = models.Relay.select()\
                         .where(models.Relay.listeners > 0,
                                models.Relay.passcode != '')
    for relay in result:
        server = relay.subdomain
        port = relay.port
        mount= relay.mountpoint
        auth = relay.passcode
        url = 'http://{server}.r-a-d.io:{port}'.format(server=server,port=port)
        try:
            result = requests.get('{url}/admin/listclients?mount={mount}'.format(url=url,
                                    mount=mount), headers={'User-Agent': 'Mozilla',
                                    'Referer': '{url}/admin/'.format(url=url),
                                    'Authorization': 'Basic {}'.format(auth)}, timeout=2)
            result.raise_for_status() # None if normal
        except:
            logger.exception("get_listeners")
        listeners.update(dict((l['ip'], l) for l in parse_listeners(result.content)))
    return listeners.values()

def main():
    """
    Main method for the status updater.
    """
    import time
    #TODO this probably needs some kind of aborting function
    while(True):
        status = get_status('stream0')
        Status.online = status.get('Online', False)
        Status.listeners = status.get('Current Listeners', 0)
        Status.peak_listeners = status.get('Peak Listeners', 0)
        
        time.sleep(8)
        
            