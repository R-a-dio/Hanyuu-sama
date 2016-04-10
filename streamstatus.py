import requests
import logging
import re
import config
import manager
import json
import itertools
from bootstrap import Switch

dns_spamfilter = Switch(True)  # 15 second resetting spamfilter
timeout = {}
error_regex = re.compile("<b>(?P<err>[a-z ]+)<\/b>", re.IGNORECASE)

def get_status(server_name):
    """
    Gets the current status of the master server, and the listener counts of all of the
    slave relays, aggregating them, filtering negative, and summing them to give an
    artificial Master server listener count used by Hanyuu in every StatusUpdate call.
    """
    result = {"online": False}
    try:
            response = requests.get(config.icecast_status,
                headers={
                    'User-Agent': 'Mozilla'
                },
                timeout=2
            )
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
            result = parse_status(response)  # bytestring

    # let's get the real listener count from the LB endpoint
    try:
        lb = requests.get(config.lb_endpoint, timeout=2)
    except:
        #logging.exception("Could not connect to load balancer status")
        pass # not a big deal right now
    else:
        if lb.status_code == 200:
            lb = lb.json()
            if 'listeners' in lb:
                result['listeners'] = lb['listeners']
    return result


def parse_status(result):
    """
    SO I MADE ICECAST INTERPRET .json AS .xsl FOR SCIENCE


    IT WORKED. I'M GOING TO HELL BUT IT WORKED.
    """
    status = icecast_json(result)


    if status:
        stats = status.get(config.icecast_mount, False)

        # if we're offline, icecast now says it's offline!
        if stats:
            return stats

    return {"online": False}



def parse_listeners(result):
    clients = icecast_json(result)
    results = []

    if clients and clients.get(config.icecast_mount, False):
        for listener in clients[config.icecast_mount]["listeners"]:
            results.append({
                "ip": listener["ip"],
                "player": listener["user_agent"],
                "time": listener["connected_seconds"],
            })

    return results

def get_listeners():
    """
    Used by player_stats (internal) to generate listener statistics and graphs
    """
    try:
        result = requests.get(
            '{url}/admin/listeners.json?mount={mount}'.format(
                url=config.icecast_server,
                mount=config.icecast_mount
            ),
            headers={
                'User-Agent': 'Mozilla',
                'Referer': '{url}/admin/'.format(url=config.icecast_server),
                'Authorization': 'Basic {}'.format(config.stream_admin_auth)
            },
            timeout=2)
    except:
        logging.exception("get_listeners")
    else:
        return parse_listeners(result)

        


def icecast_json(result):
    """
    Parse out json from an icecast endpoint.
    """
    if result.status_code == 200:
        # we have json, fun
        result = result.json()
        
        if "mounts" in result:
            return result["mounts"]

        return result


    if result.status_code == 400:
        error = error_regex.match(result.content)
        if error:
            logging.warning("Icecast API - mount unavailable ({})".format(error.group('err')))
        else:
            logging.warning("Icecast API - Unknown error: {}".format(result.content))
    else:
        logging.warning("Icecast API - Unknown error: {}".format(result.content))


