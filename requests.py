import logging
import config
import time
from multiprocessing import Process, Queue
from threading import Thread
from flup.server.fcgi import WSGIServer
import manager
import irc

def start(state):
    global fastcgi
    if (state):
        queue = state
    else:
        queue = irc.get_queue()
    fastcgi = FastCGIServer(queue=queue)
    return fastcgi

def shutdown():
    return fastcgi.shutdown()
class FastCGIServer(Process):
    """Starts a fastcgi server that handles our requests,
    runs in a separate process, supply a problem_handler
    and it will be called when the process shuts down.
    
    DO NOTE that the handler is called in the separate process"""
    def __init__(self, problem_handler=lambda: None, queue=None):
        Process.__init__(self)
        self.handler = problem_handler
        self._shutdown = Queue()
        self._queue = queue
        self.name = "Request FastCGI Server"
        self.daemon = 1
        self.start()
    def run(self):
        """Internal"""
        import bootstrap
        thread = Thread(target=self.check_shutdown, args=(self._shutdown,))
        thread.name = "FastCGI Shutdown"
        thread.start()
        bootstrap.get_logger("Requests") # Setup logging
        logging.info("PROCESS: Started FastCGI")
        irc.use_queue(self._queue)
        try:
            self.server = WSGIServer(self.external_request,
                            bindAddress=config.fastcgi_socket,
                            umask=0)
            self.server = self.server.run()
        finally:
            self.handler()
        logging.info("PROCESS: Stopped FastCGI")
        
    def shutdown(self):
        """Shuts down the fastcgi server and process"""
        self._shutdown.put(1)
        self.join()
        return self._queue
    def check_shutdown(self, shutdown):
        """Internal"""
        logging.info("THREADING: Started FastCGI shutdown thread")
        shutdown.get()
        self.server.shutdown()
        logging.info("THREADING: Stopped FastCGI shutdown thread")
    def external_request(self, environ, start_response):
        if (manager.status.requests_enabled):
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
                    if now - iptime > 1800:
                        canrequest_ip = True
                    
                    cur.execute("SELECT * FROM `tracks` WHERE \
                    `id`=%s LIMIT 1;", (trackid,))
                    if cur.rowcount >= 1:
                        try:
                            lptime = int(time.mktime(time.strptime(
                                        str(cur.fetchone()["lastrequested"]),
                                        "%Y-%m-%d %H:%M:%S")))
                        except:
                            lptime = 0
                    else:
                        lptime = now
                    if now - lptime > 3600 * 8:
                        canrequest_song = True
                    
                    if cur.rowcount >= 1:
                        try:
                            lptime = int(time.mktime(time.strptime(
                                        str(cur.fetchone()["lastplayed"]),
                                        "%Y-%m-%d %H:%M:%S" )))
                        except:
                            lptime = 0
                    else:
                        lptime = now
                    if now - lptime > 3600 * 8:
                        canrequest_song = canrequest_song and True
    
                    
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
                        cur.execute("UPDATE `tracks` SET `lastrequested`=NOW(), \
                        `priority`=priority+4 WHERE `id`=%s;", (trackid,))
                        song = manager.Song(trackid)
                        try:
                            irc.session.request_announce(song)
                        except:
                            logging.exception("Announcing request failure")
                        manager.queue.append_request(song, environ["REMOTE_ADDR"])
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