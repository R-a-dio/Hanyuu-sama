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
import manager

irc_colours = {"c": u"\x03", "c1": u"\x0301", "c2": u"\x0302",
            "c3": u"\x0303", "c4": u"\x0304", "c5": u"\x0305",
            "c7": u"\x0306", "c7": u"\x0307", "c8": u"\x0308",
            "c9": u"\x0309", "c10": u"\x0310", "c11": u"\x0311",
            "c12": u"\x0312", "c13": u"\x0313", "c14": u"\x0314",
            "c15": u"\x0315"}

def np(server, nick, channel, text, hostmask):
    if (manager.status.online):
        message = u"Now playing:{c4} '{np}' {c}[{curtime}/{length}]({listeners}/{max_listener}), {faves} fave{fs}, played {times} time{ts}, {c3}LP:{c} {lp}".format(
            np=manager.np.metadata, curtime=manager.np.positionf,
            length=manager.np.lengthf, listeners=manager.status.listeners,
            max_listener=config.listener_max, faves=manager.np.favecount,
            fs="" if (manager.np.favecount == 1) else "s", 
            times=manager.np.playcount,
            ts="" if (manager.np.playcount == 1) else "s",
            lp=manager.np.lpf,
            **irc_colours)
    else:
        message = u"Stream is currently down."
    server.privmsg(channel, message)
    
np.handler = ("on_text", r'[.!@]np$', irc.ALL_NICKS, irc.ALL_CHANNELS)

def lp(server, nick, channel, text, hostmask):
    lastplayed = manager.lp.get()
    if (len(lastplayed) > 0):
        message = u"{c3}Last Played:{c} ".format(**irc_colours) + \
            " {c3}|{c} ".format(**irc_colours).join(
                                        [song.metadata for song in lastplayed])
    else:
        message = u"There is currently no last played data available"
    server.privmsg(channel, message)
    
lp.handler = ("on_text", r'[.!@]lp$', irc.ALL_NICKS, irc.ALL_CHANNELS)

def queue(server, nick, channel, text, hostmask):
    queue = list(manager.queue)
    if (len(queue) > 0):
        message = u"{c3}Queue:{c} ".format(**irc_colours) + \
            " {c3}|{c} ".format(**irc_colours)\
            .join([song.metadata for song in queue])
    else:
        message = u"No queue at the moment"
    server.privmsg(channel, message)

queue.handler = ("on_text", r'[.!@]q(ueue)?$', irc.ALL_NICKS, irc.ALL_CHANNELS)

def dj(server, nick, channel, text, hostmask):
    tokens = text.split(' ')
    new_dj = " ".join(tokens[1:])
    if (new_dj != ''):
        if (server.hasaccess(channel, nick)):
            if (new_dj):
                if (new_dj == 'None'):
                    new_status = 'DOWN'
                elif (new_dj):
                    new_status = 'UP'
                topic = server.get_topic(channel)
                regex = re.compile(r"((.*?r/)(.*)(/dio.*?))\|(.*?)\|(.*)")
                result = regex.match(topic)
                if (result != None):
                    result = list(result.groups())
                    result[1:5] = u'|{c7} Stream:{c4} {status} {c7}DJ:{c4} {dj} {c11} http://r-a-dio.com{c} |'.format(status=new_status, dj=new_dj, **irc_colours)
                    server.topic(channel, u"".join(result))
                    manager.dj.name = new_dj
                else:
                    server.privmsg(channel, "Topic is the wrong format, can't set new topic")
        else:
            server.notice(nick, "You don't have the necessary privileges to do this.")
    else:
        server.privmsg(channel, "Current DJ: {c3}{dj}"\
                       .format(dj=manager.dj.name, **irc_colours))
        
dj.handler = ("on_text", r'[.!@]dj.*', irc.ALL_NICKS, irc.MAIN_CHANNELS)

def favorite(server, nick, channel, text, hostmask):
    if (nick in manager.np.faves):
        message = u"You already have {c3}'{np}'{c} favourited"\
            .format(np=manager.np.metadata, **irc_colours)
    else:
        manager.np.faves.append(nick)
        message = u"Added {c3}'{np}'{c} to your favorites."\
        .format(np=manager.np.metadata, **irc_colours)
    server.notice(nick, message)
    
favorite.handler = ("on_text", r'[.!@]fave.*', irc.ALL_NICKS, irc.ALL_CHANNELS)

def unfavorite(server, nick, channel, text, hostmask):
    if (nick in manager.np.faves):
        manager.np.faves.remove(nick)
        message = u"{c3}'{np}'{c} is removed from your favorites."\
            .format(np=manager.np.metadata, **irc_colours)
    else:
        message = u"You don't have {c3}'{np}'{c} in your favorites."\
            .format(np=manager.np.metadata, **irc_colours)
    server.notice(nick, message)
    
unfavorite.handler = ("on_text", r'[.!@]unfave.*',
                       irc.ALL_NICKS, irc.ALL_CHANNELS)

def set_curthread(server, nick, channel, text, hostmask):
    tokens = text.split(' ')
    threadurl = " ".join(tokens[1:]).strip()

    if threadurl != "" or len(tokens) > 1:
        if server.hasaccess(channel, nick):
            manager.status.thread = threadurl

    message = u"Thread: {thread}".format(thread=manager.status.thread)
    server.privmsg(channel, message)
    
set_curthread.handler = ("on_text", r'[.!@]thread(\s.*)?',
                          irc.ACCESS_NICKS, irc.MAIN_CHANNELS)

def topic(server, nick, channel, text, hostmask):
    tokens = text.split(' ')
    param = u" ".join(tokens[1:]).strip()
    if param != u"" or len(tokens) > 1: #i have NO IDEA WHATSOEVER why this is like this. just c/p from above
        if server.hasaccess(channel, nick):
            topic = server.get_topic(channel)
            print(u"Topic: {0}".format(topic))
            regex = re.compile(ur"(.*?r/)(.*)(/dio.*?)(.*)")
            result = regex.match(topic)
            if (result != None):
                result = list(result.groups())
                result[1] = u"{param}{c7}".format(param=param, **irc_colours)
                server.topic(channel, u"".join(result))
            else:
                server.privmsg(channel, "Topic is the wrong format, can't set new topic")

    else:
        topic = server.get_topic(channel)
        server.privmsg(channel, u"Topic: {topic}".format(topic=topic))
        
topic.handler = ("on_text", r'[.!@]topic(\s.*)?',
                  irc.ACCESS_NICKS, irc.MAIN_CHANNELS)

# TODO:
#     No way yet to kill the streamer, so this is TODO
killing_stream = False
def kill_afk(server, nick, channel, text, hostmask):
    if (server.isop(channel, nick)):
        try:
            import bootstrap
            global killing_stream
            if (not killing_stream):
                killing_stream = True
                #bootstrap.stop("afkstreamer", force=True)
            message = u"Forced AFK Streamer down,\
                        please connect in 15 seconds or less."
        except:
            message = u"Something went wrong, please punch Wessie."
            logging.exception("AFK kill failed")
        server.privmsg(channel, message)
    else:
        server.notice(nick, u"You don't have high enough access to do this.")
        
kill_afk.handler = ("on_text", r'[.!@]kill',
                     irc.DEV_NICKS, irc.ALL_CHANNELS)

# TODO:
#    same as above
def shut_afk(server, nick, channel, text, hostmask):
    if (server.isop(channel, nick)):
        try:
            from threading import Thread
            import bootstrap
            global killing_stream
            if (not killing_stream):
                killing_stream = True
                #thread = Thread(target=bootstrap.stop, args=("afkstreamer",))
                #thread.daemon = 1
                #thread.start()
            message = u'AFK Streamer will disconnect after current track, use ".kill" to force disconnect.'
        except:
            message = u"Something went wrong, please punch Wessie."
            logging.exception("AFK cleankill failed")
        server.privmsg(channel, message)
    else:
        server.notice(nick, u"You don't have high enough access to do this.")
        
shut_afk.handler = ("on_text", r'[.!@]cleankill',
                     irc.ACCESS_NICKS, irc.MAIN_CHANNELS)

def announce(server):
    for nick in manager.np.faves:
        if (server.inchannel("#r/a/dio", nick)):
            server.notice(nick, u"Fave: {0} is playing."\
                          .format(manager.np.metadata))
        message = u"Now starting:{c4} '{np}' {c}[{curtime}/{length}]({listeners}/{max_listener}), {faves} fave{fs}, played {times} time{ts}, {c3}LP:{c} {lp}".format(
            np=manager.np.metadata, curtime=manager.np.positionf,
            length=manager.np.lengthf, listeners=manager.status.listeners,
            max_listener=config.listener_max, faves=manager.np.favecount,
            fs="" if (manager.np.favecount == 1) else "s", 
            times=manager.np.playcount,
            ts="" if (manager.np.playcount == 1) else "s",
            lp=manager.np.lpf,
            **irc_colours)
    server.privmsg("#r/a/dio", message)

announce.exposed = True

def request_announce(server, song):
    message = u"Requested:{c3} '{song}'".format(song=song.metadata,
                                                   **irc_colours)
    server.privmsg("#r/a/dio", message)

request_announce.exposed = True

def search(server, nick, channel, text, hostmask):
    match = re.match(r"^(?P<mode>[.!@])s(earch)?\s(?P<query>.*)", text, re.I|re.U)
    if (match):
        mode, query = match.group('mode', 'query')
    else:
        message = u"Hauu~ you forgot a search query"
        server.notice(nick, message)
        return
    message = [u"{c4}{meta} {c3}({trackid}){c}"\
               .format(meta=song.metadata, trackid=song.id, **irc_colours) for \
               song in manager.Song.search(query)]
    if (len(message) > 0):
        message = u" | ".join(message)
    else:
        message = u"Your search returned no results"
    if (mode == "@"):
        server.privmsg(channel, message)
    else:
        server.notice(nick, message)
        
search.handler = ("on_text", r'[.!@]s(earch)?\b',
                   irc.ALL_NICKS, irc.ALL_CHANNELS)

def request(server, nick, channel, text, hostmask):
    #this should probably be fixed to remove the nick thing, but i can't into regex
    match = re.match(r"^(?P<mode>[.!@])r(equest)?\s(?P<query>.*)", text, re.I|re.U)
    if (match):
        mode, query = match.group('mode', 'query')
    else:
        server.notice(nick, u"You forgot to give me an ID, do !search <query> first.")
        return
    try:
        trackid = int(query)
    except (ValueError):
        server.notice(nick, u"You need to give a number, try !search instead.")
        return
    else:
        response = nick_request_song(trackid, hostmask)
        if (isinstance(response, manager.Song)):
            song = manager.Song(trackid)
            manager.queue.append_request(song)
            request_announce(server, song)
            return
        elif (response == 1): #wasn't song
            message = u"I don't know of any song with that id..."
        elif (response == 2): #too early
            message = u"You have to wait a bit longer before you can request again~"
        elif (response == 3): #not afk stream
            message = u"I'm not streaming right now!"
        elif (response == 4): #song not ready
            message = u"You have to wait a bit longer before requesting that song~"
    server.privmsg(channel, message)

request.handler = ("on_text", r'[.!@]r(equest)?\b',
                   irc.ALL_NICKS, irc.MAIN_CHANNELS)

def request_help(server, nick, channel, text, hostmask):
    message = u"{nick}: http://r-a-dio.com/search {c5}Thank you for listening to r/a/dio!".format(nick=nick, **irc_colours)
    server.privmsg(channel, message)
    
request_help.handler = ("on_text", r'.*how.+request',
                        irc.ALL_NICKS, irc.MAIN_CHANNELS)

def nick_request_song(trackid, host=None):
    """Gets data about the specified song, for the specified hostmask.
    If the song didn't exist, it returns 1.
    If the host needs to wait before requesting, it returns 2.
    If there is no ongoing afk stream, it returns 3.
    If the play delay on the song hasn't expired yet, it returns 4.
    Else, it returns (artist, title).
    """
    # TODO:
    # rewrite shit man
    import time
    with manager.MySQLCursor() as cur:
        try:
            song = manager.Song(trackid)
        except (ValueError):
            return 1
        can_request = True
        hostmask_id = None
        if host:
            cur.execute("SELECT id, UNIX_TIMESTAMP(time) as timestamp \
                FROM `nickrequesttime` WHERE `host`=%s LIMIT 1;",
                (host,))
            if cur.rowcount == 1:
                row = cur.fetchone()
                hostmask_id = int(row['id'])
                if int(time.time()) - int(row['timestamp']) < 3600:
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
        can_song = True
        cur.execute("SELECT UNIX_TIMESTAMP(lastplayed) as lp, UNIX_TIMESTAMP(lastrequested) as lr from `tracks` WHERE `id`=%s", (trackid,))
        if cur.rowcount == 1:
            row = cur.fetchone()
            song_lp = row['lp']
            song_lr = row['lr']
            if int(time.time()) - song_lp < 3600 * 8 or int(time.time()) - song_lr < 3600 * 8:
                can_song = False
        if (not can_request):
            return 2
        elif (not can_afk):
            return 3
        elif (not can_song):
            return 4
        else:
            if host:
                if hostmask_id:
                    cur.execute("UPDATE `nickrequesttime` SET `time`=NOW() WHERE `id`=%s LIMIT 1;", (hostmask_id,))
                else:
                    cur.execute("INSERT INTO `nickrequesttime` (host, time) VALUES (%s, NOW());", (host,))
            cur.execute("UPDATE `tracks` SET `lastrequested`=NOW() WHERE `id`=%s", (trackid,))
            return song