"""
All IRC related commands go here

Description of how commands are now handled and should be created

Handler creation:
    All handlers get the following arguments passed
    
        session:
            an irc.Session object having this handler loaded
        server:
            an irclib.ServerConnection object that triggered this handler
        nick:
            the IRC nickname that triggered this event
        channel:
            the IRC channel where this was triggered, can be None if private message
        message:
            the IRC message that triggered this handler as unicode object
        hostmask:
            the IRC hostmask of the nickname that triggered this event

Handler registration:
    Handlers should set their 'handler' attribute to a tuple with the following
        format.
        
        (event type, regular expression, allowed nicknames, allowed channels)
        
        event type:
            The type of event to trigger this handler on, currently only
            supports 'on_text'
            
        regular expression:
            A regex that is used to match against the incoming IRC message,
            if it's a match the handler will be called if the
            'allowed nicknames' and 'allowed channels' are True
            
        allowed nicknames:
            A constant or list of nicknames that are allowed to trigger this
            handler. Look in irc.py for the constants defined.
            
        allowed channels:
            Same as above but then with the channel that is allowed, do note
            that private messages always get accepted.
"""

import logging
import re
import config
import irc

irc_colours = {"c": u"\x03", "c1": u"\x0301", "c2": u"\x0302",
            "c3": u"\x0303", "c4": u"\x0304", "c5": u"\x0305",
            "c7": u"\x0306", "c7": u"\x0307", "c8": u"\x0308",
            "c9": u"\x0309", "c10": u"\x0310", "c11": u"\x0311",
            "c12": u"\x0312", "c13": u"\x0313", "c14": u"\x0314",
            "c15": u"\x0315"}

def np(conn, nick, channel, text, hostmask):
    if (streamer.active()):
        try:
            message = u"Now playing:{c4} '{np}' {c}[{curtime}/{length}]({listeners}/{max_listener}), {faves} fave{fs}, played {times} time{ts}, {c3}LP:{c} {lp}".format(
                np=streamer.nowplaying(), curtime=streamer.get_duration(), length=streamer.get_length(), listeners=streamer.listeners, max_listener=config.listener_max,
                faves=streamer.get_fave_count(), fs="" if (streamer.get_fave_count() == 1) else "s",
                times=streamer.get_playcount(), ts="" if (streamer.get_playcount() == 1) else "s",
                lp=streamer.get_lastplayed(),
                **irc_colours)
        except UnicodeDecodeError:
            logging.exception("Error compiling np message")
            message = u"We have an encoding problem, borked tags."
    else:
        message = u"Stream is currently down."
    try:
        conn.privmsg(channel, message)
    except:
        logging.exception("Error sending np message to channel '{chan}'".format(chan=channel))
        conn.privmsg(channel, u"Encoding errors go here")
np.handler = ("on_text", r'[.!@]np$', irc.ALL_NICKS, irc.ALL_CHANNELS)

def lp(conn, nick, channel, text, hostmask):
    lp = streamer.lastplayed()
    try:
        slice = lp[:5]
        string = u"{c3}Last Played:{c} ".format(**irc_colours) + " {c3}|{c} ".format(**irc_colours).join(slice)
    except (UnicodeDecodeError):
        logging.exception("Error compiling lp message")
        string = u"Derped on Unicode"
    try:
        conn.privmsg(channel, string)
    except:
        logging.exception("Error sending lp message to channel '{chan}'".format(chan=channel))
        conn.privmsg(channel, u"Encoding errors go here")
lp.handler = ("on_text", r'[.!@]lp$', irc.ALL_NICKS, irc.ALL_CHANNELS)

def queue(conn, nick, channel, text, hostmask):
    string = u"No queue at the moment (lazy Wessie)"
    queue = webcom.queue
    try:
        slice = queue[:5]
        string = u"{c3}Queue:{c} ".format(**irc_colours) + " {c3}|{c} ".format(**irc_colours).join(slice)
    except (UnicodeDecodeError):
        logging.exception("Error compiling queue message")
        string = u"Derped on Unicode"
    try:
        conn.privmsg(channel, string)
    except:
        logging.exception("Error sending queue message to channel '{chan}'".format(chan=channel))
        conn.privmsg(channel, u"Encoding errors go here")
queue.handler = ("on_text", r'[.!@]q(ueue)?$', irc.ALL_NICKS, irc.ALL_CHANNELS)

def dj(conn, nick, channel, text, hostmask):
    tokens = text.split(' ')
    new_dj = " ".join(tokens[1:])
    if (new_dj != ''):
        if (irc.hasaccess(conn, channel, nick)):
            if (new_dj):
                if (new_dj == 'None'):
                    new_status = 'DOWN'
                elif (new_dj):
                    new_status = 'UP'
                topic = irc.topic(conn, channel)
                logging.debug("Topic: {0}".format(topic))
                regex = re.compile(r"((.*?r/)(.*)(/dio.*?))\|(.*?)\|(.*)")
                result = regex.match(topic)
                if (result != None):
                    result = list(result.groups())
                    result[1:5] = u'|{c7} Stream:{c4} {status} {c7}DJ:{c4} {dj} {c11} http://r-a-dio.com{c} |'.format(status=new_status, dj=new_dj, **irc_colours)
                    irc.set_topic(conn, channel, u"".join(result))
                    current_dj = new_dj
                    new_dj = webcom.get_dj(new_dj)
                    streamer.djid = webcom.get_djid(new_dj)
                    webcom.send_queue(0, [])
                    logging.debug(streamer.djid + " " + new_dj)
                    webcom.send_nowplaying(djid=streamer.djid)
                else:
                    conn.privmsg(channel, 'Topic is borked, repair first')
        else:
            conn.notice(nick, "You don't have the necessary privileges to do this.")
    else:
        conn.privmsg(channel, "Current DJ: {c3}{dj}".format(dj=current_dj, **irc_colours))
dj.handler = ("on_text", r'[.!@]dj.*', irc.ALL_NICKS, irc.MAIN_CHANNELS)

def favorite(conn, nick, channel, text, hostmask):
    if (webcom.check_fave(nick, streamer.songid)):
        response = u"You already have {c3}'{np}'{c} favorited".format(np=streamer.nowplaying(), **irc_colours)
    else:
        if (streamer.isafk()):
            webcom.add_fave(nick, streamer.songid, streamer._accurate_songid) #first esong.id, then tracks.id
        else:
            webcom.add_fave(nick, streamer.songid)
        response = u"Added {c3}'{np}'{c} to your favorites.".format(np=streamer.nowplaying(), **irc_colours)
    conn.notice(nick, response)
favorite.handler = ("on_text", r'[.!@]fave.*', irc.ALL_NICKS, irc.ALL_CHANNELS)

def unfavorite(conn, nick, channel, text, hostmask):
    if (webcom.check_fave(nick, streamer.songid)):
        webcom.del_fave(nick, streamer.songid)
        response = u"{c3}'{np}'{c} is removed from your favorites.".format(np=streamer.nowplaying(), **irc_colours)
    else:
        response = u"You don't have {c3}'{np}'{c} in your favorites.".format(np=streamer.nowplaying(), **irc_colours)
    conn.notice(nick, response)
unfavorite.handler = ("on_text", r'[.!@]unfave.*',
                       irc.ALL_NICKS, irc.ALL_CHANNELS)

def set_curthread(conn, nick, channel, text, hostmask):
    tokens = text.split(' ')
    threadurl = " ".join(tokens[1:]).strip()

    if threadurl != "" or len(tokens) > 1:
        if irc.hasaccess(conn, channel, nick):
            webcom.send_curthread(threadurl)

    curthread = webcom.get_curthread()
    response = u"Thread: {thread}".format(thread=curthread)
    conn.privmsg(channel, response)
set_curthread.handler = ("on_text", r'[.!@]thread(\s.*)?',
                          irc.ACCESS_NICKS, irc.MAIN_CHANNELS)

def topic(conn, nick, channel, text, hostmask):
    tokens = text.split(' ')
    param = u" ".join(tokens[1:]).strip()
    param = shoutmain.fix_encoding(param)
    if param != u"" or len(tokens) > 1: #i have NO IDEA WHATSOEVER why this is like this. just c/p from above
        if irc.hasaccess(conn, channel, nick):
            topic = irc.topic(conn, channel)
            print(u"Topic: {0}".format(topic))
            regex = re.compile(ur"(.*?r/)(.*)(/dio.*?)(.*)")
            result = regex.match(topic)
            if (result != None):
                result = list(result.groups())
                result[1] = u"{param}{c7}".format(param=param, **irc_colours)
                irc.set_topic(conn, channel, u"".join(result))
            else:
                conn.privmsg(channel, 'Topic is borked, repair first')

    else:
        topic = irc.topic(conn, channel)
        conn.privmsg(channel, u"Topic: {topic}".format(topic=topic))
topic.handler = ("on_text", r'[.!@]topic(\s.*)?',
                  irc.ACCESS_NICKS, irc.MAIN_CHANNELS)

def kill_afk(conn, nick, channel, text, hostmask):
    if (irc.isop(conn, channel, nick)):
        try:
            streamer.shut_afk_streamer(True)
            message = u"Forced AFK Streamer down,\
                        please connect in 15 seconds or less."
        except:
            message = u"Something went wrong, please punch Wessie."
            logging.exception("AFK kill failed")
        conn.privmsg(channel, message)
    else:
        conn.notice(nick, u"You don't have high enough access to do this.")
kill_afk.handler = ("on_text", r'[.!@]kill',
                     irc.DEV_NICKS, irc.ALL_CHANNELS)

def shut_afk(conn, nick, channel, text, hostmask):
    if (irc.isop(conn, channel, nick)):
        try:
            streamer.shut_afk_streamer(False)
            message = u'AFK Streamer will disconnect after current track, use ".kill" to force disconnect.'
        except:
            message = u"Something went wrong, please punch Wessie."
            logging.exception("AFK cleankill failed")
        conn.privmsg(channel, message)
    else:
        conn.notice(nick, u"You don't have high enough access to do this.")
shut_afk.handler = ("on_text", r'[.!@]cleankill',
                     irc.ACCESS_NICKS, irc.MAIN_CHANNELS)

def announce(faves):
    for fave in faves:
        if (irc.inchannel(irc.server, "#r/a/dio", fave)):
            irc.server.notice(fave, u"Fave: {0} is playing.".format(streamer.current))
    if (len(faves) > 0):
        message = u"Now starting:{c4} '{np}' {c}[{curtime}/{length}]({listeners}/{max_listener}), {faves} fave{fs}, played {times} time{ts}, {c3}LP:{c} {lp}".format(
                np=streamer.nowplaying(), curtime=streamer.get_duration(), length=streamer.get_length(), listeners=streamer.listeners, max_listener=config.listener_max,
                faves=streamer.get_fave_count(), fs="" if (streamer.get_fave_count() == 1) else "s",
                times=streamer.get_playcount(), ts="" if (streamer.get_playcount() == 1) else "s",
                lp=streamer.get_lastplayed(),
                **irc_colours)
        irc.server.privmsg("#r/a/dio", message)
announce.exposed = True

def request_announce(request):
    try:
        path, message = webcom.get_song(request)
        message = u"Requested:{c3} '{request}'".format(request=message, **irc_colours)
        irc.server.privmsg("#r/a/dio", message)
    except:
        logging.exception("I'm broken with all the requests")
request_announce.exposed = True

def search(conn, nick, channel, text, hostmask):
    match = re.match(r"^(?P<mode>[.!@])s(earch)?\s(?:@(?P<nick>.*?)\s)?(?P<query>.*)", text, re.I|re.U)
    mode, favenick, query = match.group('mode', 'nick', 'query')
    result = []
    result_msg = u"Hauu~ you broke something inside of me ~desu"
    try:
        if (query == None):
            result_msg = u"Hauu~ you forgot to give me a query"
        elif (favenick == None):
            msgpart = "{c4}{metadata} {c3}({trackid}){c}"
            for row in webcom.search_tracks(query):
                if (row['artist'] != u''):
                    meta = "{a} - {t}".format(a=row['artist'], t=row['track'])
                else:
                    meta = row['track']
                trackid = row['id']
                result.append(msgpart.format(metadata=meta, trackid=trackid, **irc_colours))
            result_msg = " | ".join(result)
        else:
            pass
    except:
        logging.exception("IRC search failed")
    if (mode == "@"):
        conn.privmsg(channel, result_msg)
    else:
        conn.notice(nick, result_msg)
search.handler = ("on_text", r'[.!@]s(earch)?\b',
                   irc.ALL_NICKS, irc.ALL_CHANNELS)

def request(conn, nick, channel, text, hostmask):
    #this should probably be fixed to remove the nick thing, but i can't into regex
    match = re.match(r"^(?P<mode>[.!@])r(equest)?\s(?:@(?P<nick>.*?)\s)?(?P<query>.*)", text, re.I|re.U)
    mode, favenick, query = match.group('mode', 'nick', 'query')
    msg = u"Hauu~ you broke something inside of me ~desu"
    try:
        if (query == None):
            msg = u"Hauu~ You forgot to make a request"
        elif (favenick == None):
            try:
                songid = int(query)
                response = webcom.nick_request_song(songid, hostmask)
                if (isinstance(response, tuple)):
                    streamer.queue.add_request(songid)
                    streamer.queue.send_queue(streamer.get_left())
                    request_announce(songid)
                    return
                elif (response == 1): #wasn't song
                    msg = u"I don't know of any song with that id..."
                elif (response == 2): #too early
                    msg = u"You have to wait a bit longer before you can request again~"
                elif (response == 3): #not afk stream
                    msg = u"I'm not streaming right now!"
            except (ValueError):
                msg = u"That's not a song id! Use .search first!"
        else:
            pass
    except:
        logging.exception("IRC request failed")
    try:
        conn.privmsg(channel, msg)
    except:
        logging.exception("IRC request send message failed")
request.handler = ("on_text", r'[.!@]r(equest)?\b',
                   irc.ALL_NICKS, irc.MAIN_CHANNELS)

def request_help(conn, nick, channel, text, hostmask):
    try:
        message = u"{nick}: http://r-a-dio.com/search {c5}Thank you for listening to r/a/dio!".format(nick=nick, **irc_colours)
        irc.server.privmsg(channel, message)
    except:
        print "Error in request help function"
request_help.handler = ("on_text", r'.*how.+request',
                        irc.ALL_NICKS, irc.MAIN_CHANNELS)

def nick_request_song(songid, host=None):
    """Gets data about the specified song, for the specified hostmask.
    If the song didn't exist, it returns 1.
    If the host needs to wait before requesting, it returns 2.
    If there is no ongoing afk stream, it returns 3.
    Else, it returns (artist, title).
    """
    # TODO:
    # rewrite shit man
    with manager.MySQLCursor() as cur:
        can_request = True
        if host:
            host = mysql.escape_string(host)
            cur.execute("SELECT UNIX_TIMESTAMP(time) as timestamp FROM `nickrequesttime` WHERE `host`='{host}' LIMIT 1;".format(host=host))
            if cur.rowcount == 1:
                row = cur.fetchone()
                if int(time.time()) - int(row['timestamp']) < 1800:
                    can_request = False
        
        can_afk = True
        cur.execute("SELECT isafkstream FROM `streamstatus`;")
        if cur.rowcount == 1:
            row = cur.fetchone()
            afk = row['isafkstream']
            if not afk == 1:
                can_afk = False
        else:
            can_afk = False
        if (not can_request):
            return 2
        if (not can_afk):
            return 3
        cur.execute("SELECT * FROM `tracks` WHERE `id`={id};".format(id=songid))
        if (cur.rowcount == 1):
            row = cur.fetchone()
            artist = row['artist']
            title = row['track']
            return (artist, title)
        return 1