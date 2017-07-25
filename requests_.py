import logging
import config
import time
import json
import threading
from flup.server.fcgi import WSGIServer
import MySQLdb
import manager
import bot
from multiprocessing.managers import BaseManager
import bootstrap
import hashlib
import hmac

debug = True

def songdelay(val):
    """Gives the time delay in seconds for a specific song
    request count.
    """
    import math
    if val > 30:
        val = 30
    # return int(29145 * math.exp(0.0476 * val) + 0.5)
    # return int(0.1791*val**4 - 17.184*val**3 + 557.07*val**2 - 3238.9*val + 30687 + 0.5)
    # return int(25133*math.exp(0.1625*val)+0.5)
    # return int(-123.82*val**3 + 3355.2*val**2 + 10110*val + 51584 + 0.5)
    if 0 <= val <= 7:
        cd = -11057 * val ** 2 + 172954 * val + 81720
    else:
        cd = int(599955 * math.exp(0.0372 * val) + 0.5)
    return cd / 2


def check_hmac(value, hash):
    key = config.request_key
    signature = hmac.new(key, value, hashlib.sha256).hexdigest()
    return hash == signature

def extract_ip_address(environ):
    """
    Extracts the correct address to use from an wsgi environ.
    """
    if "HTTP_X_RADIO_CLIENT" in environ:
        if check_hmac(environ["HTTP_X_RADIO_CLIENT"], environ["HTTP_X_RADIO_AUTH"]):
            ip = environ["HTTP_X_RADIO_CLIENT"]
        else:
            ip = environ["REMOTE_ADDR"]
    else:
        ip = environ["REMOTE_ADDR"]

    return ip


class FastCGIServer(object):

    """Starts a fastcgi server that handles our requests,
    runs in a separate process, supply a problem_handler
    and it will be called when the process shuts down.

    DO NOTE that the handler is called in the separate process"""
    __metaclass__ = bootstrap.Singleton

    def __init__(self, problem_handler=lambda: None, queue=None):
        # Thread.__init__(self)
        object.__init__(self)
        bootstrap.logging_setup()
        self.handler = problem_handler
        # Setup manager classes we need
        self.queue = manager.Queue()
        self.status = manager.Status()

        self.server = WSGIServer(self.external_request,
                                 bindAddress=config.fastcgi_socket,
                                 umask=0)

        self.lock = threading.Lock()

        # self.name = "Request FastCGI Server"
        # self.daemon = 1
        # self.start()

    def run(self):
        """Internal"""
        logging.info("Started FastCGI")
        try:
            self.server.run()
        finally:
            self.handler()
        logging.info("Stopped FastCGI")

    def shutdown(self):
        self.server._exit()

    def lock(f):
        def lock(self, environ, start_response):
            with self.lock:
                return f(self, environ, start_response)
        return lock

    @lock
    def external_request(self, environ, start_response):
        if (self.status.requests_enabled):
            def is_int(num):
                try:
                    int(num)
                    return True
                except:
                    return False
            try:
                postdata = environ['wsgi.input']\
                    .read(int(environ['CONTENT_LENGTH']))
            except:
                postdata = ""
            splitdata = postdata.split('=')
            sitetext = ""
            if len(splitdata) == 2 and splitdata[0] == 'songid' \
                    and is_int(splitdata[1]):
                trackid = int(splitdata[1])
                canrequest_ip = False
                canrequest_song = False

                if debug:
                    print "Extracting environ info"

                ip = extract_ip_address(environ)

                if debug:
                    print "Extracted IP: ", ip

                with manager.MySQLCursor(cursortype=MySQLdb.cursors.Cursor) as cur:
                    # SQL magic
                    query = ("SELECT UNIX_TIMESTAMP(time) AS time FROM requesttime WHERE ip="
                            "%s LIMIT 1;")
                    cur.execute(query, (ip,))
                    for iptime, in cur:
                        has_requesttime_entry = True
                        break
                    else:
                        has_requesttime_entry = False
                        iptime = 0

                    if debug:
                        print "Extracted iptime of: ", iptime

                    now = int(time.time())
                    if now - iptime > 3600*2:
                        canrequest_ip = True

                    if debug:
                        print "IP requestable: ", canrequest_ip

                    cur.execute("SELECT usable, UNIX_TIMESTAMP(lastrequested) as lr, "
                                "requestcount, UNIX_TIMESTAMP(lastplayed) as lp "
                                "FROM `tracks` WHERE `id`=%s LIMIT 1;", (trackid,))

                    for usable, lrtime, rc, lptime in cur:
                        canrequest_song = ((now - lrtime) > songdelay(rc) and
                                           (now - lptime) > songdelay(rc))

                    if debug:
                        print "Song requestable: ", canrequest_song

                    if not canrequest_ip or not canrequest_song or not usable:
                        if not canrequest_ip:
                            sitetext = "You need to wait longer before requesting again."
                        elif not canrequest_song:
                            sitetext = "You need to wait longer before requesting this song."
                        elif not usable:
                            sitetext = "This song can't be requested yet."
                    else:
                        sitetext = "Thank you for making your request!"
                        # SQL magic
                        if has_requesttime_entry:
                            cur.execute(
                                "UPDATE requesttime SET time=NOW() WHERE ip=%s;",
                                (ip,),
                            )
                        else:
                            cur.execute(
                                "INSERT INTO requesttime (ip) VALUES (%s);", 
                                (ip,),
                            )

                        n = cur.execute(
                            "UPDATE tracks SET lastrequested=NOW(), requestcount=requestcount+2,priority=priority+1 WHERE id=%s;",
                            (trackid,),
                        )

                        print "finishing up request of: ", trackid
                        song = manager.Song(trackid)
                        try:
                            self.queue.append_request(song)
                        except:
                            logging.exception("QUEUE PROBLEMS BLAME VIN")

                        # Website search index update
                        song.update_index()

                        # Silly IRC announce
                        bot.request_announce(song.id)

            else:
                sitetext = "Invalid parameter."
        else:
            sitetext = "You can't request songs at the moment."

        print sitetext

        start_response('200 OK', [('Content-Type', 'application/json')])
        yield json.dumps(dict(response=sitetext))


if __name__ == "__main__":
    server = FastCGIServer()
    server.run()
