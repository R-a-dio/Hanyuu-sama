import requests
import logging
import re
import config
import manager
import itertools
import bs4
from bootstrap import Switch

dns_spamfilter = Switch(True)  # 15 second resetting spamfilter
timeout = {}
error_regex = re.compile("<b>(?P<err>[a-z ]+)<\/b>", re.IGNORECASE)

def get_relay_listeners(relay_url):
    try:
        r1 = requests.get(relay_url, timeout=2)
    except:
        pass
    else:
        try:
            if r1.status_code == 200:
                for line in r1.text.split('\n'):
                    if 'Current Listeners' in line:
                        return int(line.split(' ')[2].strip())
        except:
            pass
    return 0

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
        #print 'ERROR'
        #logging.exception("Could not connect to load balancer status")
        pass # not a big deal right now
    else:
        if lb.status_code == 200:
            lb = lb.json()
            if 'listeners' in lb:
                result['listeners'] = lb['listeners']

    #for relay in ['https://relay1.r-a-d.io/a.mp3.xspf', 'https://relay3.dorks.io/main.mp3.xspf', 'https://relay4.dorks.io/main.mp3.xspf']:
    #    if 'listeners' in result:
    #        result['listeners'] += get_relay_listeners(relay)

#    try:
#        r1 = requests.get("https://relay1.r-a-d.io/a.mp3.xspf", timeout=2)
#    except:
#        pass
#    else:
#        if r1.status_code == 200:
#            for line in r1.text.split('\n'):
#                if 'Current Listeners' in line:
#                    result['listeners'] += int(line.split(' ')[2].strip())
#                    break
    return result


def parse_status(result):
    status = icecast_json(result, config.icecast_mountpoint)

    if status:
        status["online"] = 'stream_start' in status
        return status

    return {"online": False}


def get_listeners():
    """
    Used by player_stats (internal) to generate listener statistics and graphs
    """
    try:
        result = requests.get(
            '{url}/admin/listclients?mount={mount}'.format(
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
        return parse_listeners(result.text, config.icecast_mount)

def parse_listeners(result, mount):
    parser = bs4.BeautifulSoup(result, "lxml-xml")
    mounts = parser.findAll('source', {'mount': mount})
    if not mounts:
        return []

    results = []
    for listener in mounts[0].findAll('listener'):
        results.append({
            "ip": listener.IP.string,
            "player": listener.UserAgent.string,
            "time": int(listener.Connected.string),
        })

    return results


def icecast_json(result, mount):
    """
    Parse out json from an icecast endpoint.
    """
    if result.status_code == 200:
        result = result.json()
        if "icestats" in result and "source" in result["icestats"]:
            if isinstance(result["icestats"]["source"], dict):
                return result["icestats"]["source"]

            for m in result["icestats"]["source"]:
                _, url = m["listenurl"].rsplit("/", 1)
                if url != mount:
                    continue
                return m

            return {}
        return {}


    if result.status_code == 400:
        error = error_regex.match(result.content)
        if error:
            logging.warning("Icecast API - mount unavailable ({})".format(error.group('err')))
        else:
            logging.warning("Icecast API - Unknown error: {}".format(result.content))
    else:
        logging.warning("Icecast API - Unknown error: {}".format(result.content))


