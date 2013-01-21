from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
#from ... import config
import logging
import time
from threading import Thread
from flup.server.fcgi import WSGIServer
#import manager
#import irc
from multiprocessing.managers import BaseManager
#import bootstrap


logger = logging.getLogger('hanyuu.requests.servers.fastcgi')


# TODO: Reworked to cleaner code. (Don't bother till abstraction is done)
class FastCGIServer(object):
    """Starts a fastcgi server that handles our requests,
    runs in a separate process, supply a problem_handler
    and it will be called when the process shuts down.
    
    DO NOTE that the handler is called in the separate process"""
    __metaclass__ = bootstrap.Singleton
    def __init__(self, problem_handler=lambda: None, queue=None):
        #Thread.__init__(self)
        object.__init__(self)
        bootstrap.logging_setup()
        self.handler = problem_handler
        # Setup manager classes we need
        self.queue = manager.Queue()
        self.status = manager.Status()
        
        self.server = WSGIServer(self.external_request,
                bindAddress=config.fastcgi_socket,
                umask=0)
        
        #self.name = "Request FastCGI Server"
        #self.daemon = 1
        #self.start()
    
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
                with manager.MySQLCursor() as cur:
                    # SQL magic
                    cur.execute("SELECT * FROM `requesttime` WHERE \
                    `ip`=%s LIMIT 1;", (environ["REMOTE_ADDR"],))
                    ipcount = cur.rowcount
                    if cur.rowcount >= 1:
                        try:
                            iptime = int(
                                time.mktime(
                                    time.strptime(
                                        str(
                                            cur.fetchone()["time"]
                                            ),
                                            "%Y-%m-%d %H:%M:%S")
                                            )
                                         )
                        except:
                            iptime = 0
                    else:
                        iptime = 0
                    now = int(time.time())
                    if now - iptime > 3600:
                        canrequest_ip = True
                    
                    
                    cur.execute("SELECT * FROM `tracks` WHERE \
                    `id`=%s LIMIT 1;", (trackid,))
                    if cur.rowcount >= 1:
                        row = cur.fetchone()
                        try:
                            lptime = int(time.mktime(time.strptime(
                                        str(row["lastrequested"]),
                                        "%Y-%m-%d %H:%M:%S")))
                        except:
                            lptime = 0
                        if now - lptime > songdelay(row['requestcount']):
                            canrequest_song = True
                        
                        try:
                            lptime = int(time.mktime(time.strptime(
                                        str(row["lastplayed"]),
                                        "%Y-%m-%d %H:%M:%S" )))
                        except:
                            lptime = 0
                        if now - lptime > songdelay(row['requestcount']):
                            canrequest_song = canrequest_song and True
                    else:
                        canrequest_song = False
                    
                    if not canrequest_ip or not canrequest_song:
                        if not canrequest_ip:
                            sitetext = "You need to wait longer before requesting again."
                        elif not canrequest_song:
                            sitetext = "You need to wait longer before requesting this song."
                    else:
                        sitetext = "Thank you for making your request!"
                        #SQL magic
                        if ipcount >= 1:
                            cur.execute("UPDATE `requesttime` SET `time`=NOW() WHERE `ip`='%s';" % (environ["REMOTE_ADDR"]))
                        else:
                            cur.execute("INSERT INTO `requesttime` (`ip`) VALUES ('%s');" % (environ["REMOTE_ADDR"]))
                        song = manager.Song(trackid)
                        self.queue.append_request(song, environ["REMOTE_ADDR"])
                        try:
                            irc.connect().request_announce(song)
                        except:
                            logging.exception("Announcing request failure")
                        
            else:
                sitetext = "Invalid parameter."
        else:
            sitetext = "You can't request songs at the moment."
        start_response('200 OK', [('Content-Type', 'text/html')])
        yield '<html>'
        yield '<head>'
        yield '<title>r/a/dio</title>'
        yield '<meta http-equiv="refresh" content="5;url=/search/">'
        yield '<link rel="shortcut icon" href="/favicon.ico" />'
        yield '</head>'
        yield '<body>'
        yield '<center><h2>%s</h2><center><br/>' % (sitetext)
        yield '<center><h3>You will be redirected shortly.</h3></center>'
        yield '</body>'
        yield '</html>'
        
if __name__ == "__main__":
    import multiprocessing, logging
    logger = multiprocessing.log_to_stderr()
    logger.setLevel(logging.DEBUG)
    server = FastCGIServer()
    server.run()