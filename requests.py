import logging
import config
import webcom
import hanyuu_commands as commands
import time
from multiprocessing import Process
from flup.server.fcgi import WSGIServer
streamer = None # Should be assigned shoutmain.instance
server = None
def start():
    global process
    process = Process(target=start_fastcgi)
def start_fastcgi():
    global server
    server = WSGIServer(external_request, bindAddress=config.fastcgi_socket,umask=0)
    server.run()
    
def shutdown():
    global server
    server.shutdown()
    process.join()
    
def external_request(environ, start_response):
    if (streamer.afk_streaming):
        def is_int(num):
            try:
                int(num)
                return True
            except:
                return False
        try:
            postdata = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))
        except:
            postdata = ""
        splitdata = postdata.split('=')
        sitetext = ""
        if len(splitdata) == 2 and splitdata[0] == 'songid' and is_int(splitdata[1]):
            songid = int(splitdata[1])
            canrequest_ip = False
            canrequest_song = False
            with webcom.MySQLCursor() as cur:
                # SQL magic
                cur.execute("SELECT * FROM `requesttime` WHERE `ip`='%s' LIMIT 1;" % (environ["REMOTE_ADDR"]))
                ipcount = cur.rowcount
                if cur.rowcount >= 1:
                    try:
                        iptime = int(time.mktime(time.strptime(str(cur.fetchone()["time"]), "%Y-%m-%d %H:%M:%S" )))
                    except:
                        iptime = 0
                else:
                    iptime = 0
                now = int(time.time())
                if now - iptime > 1800:
                    canrequest_ip = True
                
                cur.execute("SELECT * FROM `tracks` WHERE `id`=%s LIMIT 1;" % (songid))
                if cur.rowcount >= 1:
                    try:
                        lptime = int(time.mktime(time.strptime(str(cur.fetchone()["lastrequested"]), "%Y-%m-%d %H:%M:%S" )))
                    except:
                        lptime = 0
                else:
                    lptime = now
                if now - lptime > 3600 * 8:
                    canrequest_song = True
                
                if cur.rowcount >= 1:
                    try:
                        lptime = int(time.mktime(time.strptime(str(cur.fetchone()["lastplayed"]), "%Y-%m-%d %H:%M:%S" )))
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
                    cur.execute("UPDATE `tracks` SET `lastrequested`=NOW(), `priority`=priority+4 WHERE `id`=%s;" % (songid))
                    try:
                        commands.request_announce(songid)
                    except:
                        logging.exception("Announcing request failure")
                    streamer.queue.add_request(songid)
                    streamer.queue.send_queue(streamer.get_left())
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