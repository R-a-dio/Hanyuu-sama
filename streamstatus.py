import requests
import logging
import config
import manager
import xmltodict
import itertools
from bootstrap import Switch

dns_spamfilter = Switch(True)  # 15 second resetting spamfilter
timeout = {}


def get_status(server_name):
    """
    Gets the current status of the master server, and the listener counts of all of the
    slave relays, aggregating them, filtering negative, and summing them to give an
    artificial Master server listener count used by Hanyuu in every StatusUpdate call.
    """
    result = {"Online": False}
    # Pointless but easier to type. Also makes more sense.
    try:
            result = requests.get(config.icecast_status,
                headers={'User-Agent': 'Mozilla'}, timeout=2)
    except requests.HTTPError as e:  # rare, mostly 403
        if not dns_spamfilter:
           logging.warning(
               "Can't connect to mountpoint; Assuming listener limit reached")
           dns_spamfilter.reset()
        else:
            logging.exception("HTTPError occured in status retrieval")
    except requests.ConnectionError:
        logging.exception("Connection interrupted to master server")
    except:
        logging.exception(
            "Can't connect to master status page. Is Icecast running?")
    else:
            result = parse_status(result.content)  # bytestring

    return result


def parse_status(xml):
    """
    Function to parse the XML returned from a mountpoint.
    Input must be a bytestring as to avoid UnicodeDecodeError from stopping
    Parsing. The only meaningful result is "Current Listeners".

    Logic behind returning an explicit "Online" key is readability
    """
    result = {"Online": False}  # Assume False by default
    try:
        xml_dict = xmltodict.parse(
            xml,
            xml_attribs=False,
            cdata_separator="\n")  # CDATA required
        try:
            xml_dict = xml_dict.get(
                'playlist',
                {}).get('trackList',
                        {}).get('track',
                                None)
        except AttributeError:  # No mountpoint it seems, just ditch an empty result
            return result
        else:
            if xml_dict is None:  # We got none returned from the get anyway
                return result
        annotations = xml_dict.get("annotation", False)
        if not annotations:  # edge case for having nothing...
            return result
        annotations = annotations.split("\n")
        for annotation in annotations:
            tmp = annotation.split(":", 1)
            if len(tmp) > 1:
                result[tmp[0]] = tmp[
                    1].strip()  # no need whatsoever to decode anything here. It's not needed by NP()
        result["Online"] = True
        if xml_dict["title"] is None:
            result["Current Song"] = u""  # /shrug
        else:
            result["Current Song"] = xml_dict.get("title", u"")
    except UnicodeDecodeError:  # we have runes, but we know we are online. This should not even be possible (requests.get.content)
        result["Online"] = True
        result[
            "Current Song"] = u""  # Erase the bad stuff. However, keep in mind stream title can do this (anything user input...)
    except:
        logging.exception("Failed to parse XML Status data.")
    return result  # cleaner and easier to read falling back to original function scope (instead of 5 returns)


def parse_listeners(xml):
    """
    parses the XML produced by icecast using xmltodict, acting like it is
    really JSON, or a python dict, to make it much easier to handle.
    xml should be a string, not a url!
    (while it supports filenames, it doesnt support urls)
    """
    skip_following = False
    result = []
    try:
        xml_dict = xmltodict.parse(xml, xml_attribs=False)
        xml_dict = xml_dict["icestats"]["source"]["listener"]
        for listener in xml_dict:
            if not isinstance(listener, dict):
                # This is a bug fix, when there is only one listener the
                # returned xml_dict is a single dict with just the one
                # listener in it.
                if skip_following:
                    continue
                listener = xml_dict
                # Set a variable so we skip the rest of the entries.
                skip_following = True
            _tmp = {}
            _tmp['ip'] = listener['IP']
            _tmp['player'] = listener['UserAgent']
            _tmp['time'] = listener['Connected']
            result.append(_tmp)
        return result
    except:
        logging.exception("Couldn't parse listener XML - ListenersParser")
        return []


def get_listeners():
    """
    Used by player_stats (internal) to generate listener statistics and graphs
    """
    listeners = []
    url = "http://localhost:8000"
    mount = "/main.mp3"
    try:
        result = requests.get(
        '{url}/admin/listclients?mount={mount}'.format(url=url,
                                                       mount=mount), headers={'User-Agent': 'Mozilla',
                                                                              'Referer':
                                                                              '{url}/admin/'.format(
                                                                              url=url),
                                                                              'Authorization': 'Basic {}'.format(auth)}, timeout=2)
        result.raise_for_status()  # None if normal
    except:
        logging.exception("get_listeners")
    else:
        listeners.extend(list(parse_listeners(result.content)))
    return listeners
