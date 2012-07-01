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
import main
import random as _random
from datetime import timedelta

def tokenize(text):
    return text.lower().split(" ")

irc_colours = {"c": u"\x03", "c1": u"\x0301", "c2": u"\x0302",
            "c3": u"\x0303", "c4": u"\x0304", "c5": u"\x0305",
            "c7": u"\x0306", "c7": u"\x0307", "c8": u"\x0308",
            "c9": u"\x0309", "c10": u"\x0310", "c11": u"\x0311",
            "c12": u"\x0312", "c13": u"\x0313", "c14": u"\x0314",
            "c15": u"\x0315"}

def np(server, nick, channel, text, hostmask):
    status = manager.Status()
    np = manager.NP()
    if (status.online):
        message = u"Now playing:{c4} '{np}' {c}[{curtime}/{length}]({listeners}/{max_listener}), {faves} fave{fs}, played {times} time{ts}, {c3}LP:{c} {lp}".format(
            np=np.metadata, curtime=np.positionf,
            length=np.lengthf, listeners=status.listeners,
            max_listener=config.listener_max, faves=np.favecount,
            fs="" if (np.favecount == 1) else "s", 
            times=np.playcount,
            ts="" if (np.playcount == 1) else "s",
            lp=np.lpf,
            **irc_colours)
    else:
        message = u"Stream is currently down."
    server.privmsg(channel, message)
    
np.handler = ("on_text", r'[.!@]np$', irc.ALL_NICKS, irc.ALL_CHANNELS)

def create_faves_code(server, nick, channel, text, hostmask):
    with manager.MySQLCursor() as cur:
        cur.execute("SELECT * FROM enick WHERE `nick`=%s", (nick,))
        authcode = None
        if (cur.rowcount > 0):
            authcode = cur.fetchone()['authcode']
            print authcode
        if (not authcode):
            while 1:
                authcode = str(_random.getrandbits(24))
                cur.execute("SELECT * FROM enick WHERE `authcode`=%s", (authcode,))
                if (cur.rowcount == 0):
                    break
            cur.execute("INSERT INTO enick (nick, authcode) VALUES (%(nick)s, "
                        "%(authcode)s) ON DUPLICATE KEY UPDATE `authcode`="
                        "%(authcode)s", {"nick": nick, "authcode": authcode})
    server.privmsg(nick, "Your authentication code is: %s" % (authcode,))

create_faves_code.handler = ("on_text", r'SEND CODE',
                             irc.ALL_NICKS, irc.PRIVATE_MESSAGE)

def lp(server, nick, channel, text, hostmask):
    lastplayed = manager.LP().get()
    if (len(lastplayed) > 0):
        message = u"{c3}Last Played:{c} ".format(**irc_colours) + \
            " {c3}|{c} ".format(**irc_colours).join(
                                        [song.metadata for song in lastplayed])
    else:
        message = u"There is currently no last played data available"
    server.privmsg(channel, message)
    
lp.handler = ("on_text", r'[.!@]lp$', irc.ALL_NICKS, irc.ALL_CHANNELS)

def queue(server, nick, channel, text, hostmask):
    p = tokenize(text)
    if len(p) > 1:
        if p[1] == u"length":
            request_queue = regular_queue = requests = regulars = 0
            for song in manager.Queue().iter(None):
                if (song.type == manager.REQUEST):
                    request_queue += song.length
                    requests += 1
                elif (song.type == manager.REGULAR):
                    regular_queue += song.length
                    regulars += 1
            message = u"There are {req} requests ({req_time}), {norm} randoms ({norm_time}), total of {total} songs ({total_time})".\
                    format(**{'req_time': timedelta(seconds=request_queue),
                    'norm_time': timedelta(seconds=regular_queue),
                    'total_time': timedelta(seconds=request_queue+regular_queue),
                    'req': requests,
                    'norm': regulars,
                    'total': requests+regulars})
    else:
        queue = list(manager.Queue())
        if (len(queue) > 0):
            message = u"{c3}Queue:{c} ".format(**irc_colours) + \
                " {c3}|{c} ".format(**irc_colours)\
                .join([song.metadata for song in queue])
        else:
            message = u"No queue at the moment"
    server.privmsg(channel, message)

queue.handler = ("on_text", r'[.!@]q(ueue)?', irc.ALL_NICKS, irc.ALL_CHANNELS)

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
                    result[1:5] = u'|{c7} Stream:{c4} {status} {c7}DJ:{c4} {dj} {c11} http://r-a-d.io{c} |'.format(status=new_status, dj=new_dj, **irc_colours)
                    server.topic(channel, u"".join(result))
                    manager.DJ().name = new_dj
                else:
                    server.privmsg(channel, "Topic is the wrong format, can't set new topic")
        else:
            server.notice(nick, "You don't have the necessary privileges to do this.")
    else:
        server.privmsg(channel, "Current DJ: {c3}{dj}"\
                       .format(dj=manager.DJ().name, **irc_colours))
        
dj.handler = ("on_text", r'[.!@]dj.*', irc.ALL_NICKS, irc.MAIN_CHANNELS)

def favorite(server, nick, channel, text, hostmask):
    np = manager.NP()
    if (nick in np.faves):
        message = u"You already have {c3}'{np}'{c} favourited"\
            .format(np=np.metadata, **irc_colours)
    else:
        np.faves.append(nick)
        message = u"Added {c3}'{np}'{c} to your favorites."\
        .format(np=np.metadata, **irc_colours)
    server.notice(nick, message)
    
favorite.handler = ("on_text", r'[.!@]fave.*', irc.ALL_NICKS, irc.ALL_CHANNELS)

def unfavorite(server, nick, channel, text, hostmask):
    np = manager.NP()
    if (nick in np.faves):
        np.faves.remove(nick)
        message = u"{c3}'{np}'{c} is removed from your favorites."\
            .format(np=np.metadata, **irc_colours)
    else:
        message = u"You don't have {c3}'{np}'{c} in your favorites."\
            .format(np=np.metadata, **irc_colours)
    server.notice(nick, message)
    
unfavorite.handler = ("on_text", r'[.!@]unfave.*',
                       irc.ALL_NICKS, irc.ALL_CHANNELS)

def set_curthread(server, nick, channel, text, hostmask):
    status = manager.Status()
    tokens = text.split(' ')
    threadurl = " ".join(tokens[1:]).strip()

    if threadurl != "" or len(tokens) > 1:
        if server.hasaccess(channel, nick):
            status.thread = threadurl

    message = u"Thread: {thread}".format(thread=status.thread)
    server.privmsg(channel, message)
    
set_curthread.handler = ("on_text", r'[.!@]thread(\s.*)?',
                          irc.ALL_NICKS, irc.MAIN_CHANNELS)

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
                  irc.ALL_NICKS, irc.MAIN_CHANNELS)

# TODO:
#     No way yet to kill the streamer, so this is TODO
killing_stream = False
def kill_afk(server, nick, channel, text, hostmask):
    if (server.isop(channel, nick)):
        try:
            stream = main.connect()
            stream.switch_dj(force=True)
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
    try:
        stream = main.connect()
        stream.switch_dj()
        message = u'AFK Streamer will disconnect after current track, use ".kill" to force disconnect.'
    except:
        message = u"Something went wrong, please punch Wessie."
        logging.exception("AFK cleankill failed")
    server.privmsg(channel, message)
        
shut_afk.handler = ("on_text", r'[.!@]cleankill',
                     irc.ACCESS_NICKS, irc.MAIN_CHANNELS)

def announce(server):
    np = manager.NP()
    status = manager.Status()
    if (len(np.faves) != 0):
        message = u"Now starting:{c4} '{np}' {c}[{curtime}/{length}]({listeners}/{max_listener}), {faves} fave{fs}, played {times} time{ts}, {c3}LP:{c} {lp}".format(
            np=np.metadata, curtime=np.positionf,
            length=np.lengthf, listeners=status.listeners,
            max_listener=config.listener_max, faves=np.favecount,
            fs="" if (np.favecount == 1) else "s", 
            times=np.playcount,
            ts="" if (np.playcount == 1) else "s",
            lp=np.lpf,
            **irc_colours)
        server.privmsg("#r/a/dio", message)
    for nick in np.faves:
        if (server.inchannel("#r/a/dio", nick)):
            server.notice(nick, u"Fave: {0} is playing."\
                          .format(np.metadata))

announce.exposed = True

def request_announce(server, song):
    message = u"Requested:{c3} '{song}'".format(song=song.metadata,
                                                   **irc_colours)
    server.privmsg("#r/a/dio", message)

request_announce.exposed = True

def random(server, nick, channel, text, hostmask):
    match = re.match(r"^(?P<mode>[.!@])random\b(?P<command>.*)", text, re.I|re.U)
    if (match):
        mode, command = match.group("mode", "command")
    else:
        return
    if (command.lower().strip() == "fave"):
        songs = manager.Song.nick(nick, limit=None, tracks=True)
        while len(songs) > 0:
            song = songs.pop(_random.randrange(len(songs)))
            value = nick_request_song(song.id, hostmask)
            if (isinstance(value, tuple)):
                message = hanyuu_response(value[0], value[1])
                if (value[0] == 4):
                    continue
                else:
                    break
            elif (isinstance(value, manager.Song)):
                manager.Queue().append_request(song)
                request_announce(server, song)
                return
    else:
        while True:
            song = manager.Song.random()
            value = nick_request_song(song.id, hostmask)
            if (isinstance(value, tuple)):
                message = hanyuu_response(value[0], value[1])
                if (value[0] == 4):
                    continue
                else:
                    break
            elif (isinstance(value, manager.Song)):
                manager.Queue().append_request(song)
                request_announce(server, song)
                return
    if (mode == "@"):
        server.privmsg(channel, message)
    else:
        server.notice(nick, message)
        
random.handler = ("on_text", r'[.!@]random\b', irc.ALL_NICKS, irc.MAIN_CHANNELS)

def lucky(server, nick, channel, text, hostmask):
    match = re.match(r"^(?P<mode>[.!@])lucky\s(?P<query>.*)", text, re.I|re.U)
    if (match):
        mode, query = match.group("mode", "query")
    else:
        message = u"Hauu~ you didn't have a search query!"
        server.notice(nick, message)
        return
    result = manager.Song.search(query, limit=20)
    message = None
    for song in result:
        value = nick_request_song(song.id, hostmask)
        if (isinstance(value, tuple)):
            message = hanyuu_response(value[0], value[1])
            if (value[0] == 4):
                continue
            else:
                break
        elif (isinstance(value, manager.Song)):
            manager.Queue().append_request(song)
            request_announce(server, song)
            return
    if (message == None):
        message = u"Your query did not have any results"
    if (mode == "@"):
        server.privmsg(channel, message)
    else:
        server.notice(nick, message)
        
lucky.handler = ("on_text", r'[.!@]lucky\b', irc.ALL_NICKS, irc.MAIN_CHANNELS)

def search(server, nick, channel, text, hostmask):
    match = re.match(r"^(?P<mode>[.!@])s(earch)?\s(?P<query>.*)", text, re.I|re.U)
    if (match):
        mode, query = match.group('mode', 'query')
    else:
        message = u"Hauu~ you forgot a search query"
        server.notice(nick, message)
        return
    try:
        query = int(query);
        try:
            song = manager.Song(id=query)
            message = [u"{c4}{meta} {c3}({trackid}){c}"\
               .format(meta=song.metadata, trackid=song.id, **irc_colours)]
        except (ValueError):
            message = []
    except (ValueError):
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
            manager.Queue().append_request(song)
            request_announce(server, song)
            return
        elif (response == 1): #wasn't song
            message = u"I don't know of any song with that id..."
        elif (isinstance(response, tuple)):
            message = hanyuu_response(response[0], response[1])
    server.privmsg(channel, message)

request.handler = ("on_text", r'[.!@]r(equest)?\b',
                   irc.ALL_NICKS, irc.MAIN_CHANNELS)

def request_help(server, nick, channel, text, hostmask):
    message = u"{nick}: http://r-a-d.io/search {c5}Thank you for listening to r/a/dio!".format(nick=nick, **irc_colours)
    server.privmsg(channel, message)
    
request_help.handler = ("on_text", r'.*how.+request',
                        irc.ALL_NICKS, irc.MAIN_CHANNELS)

def markov_store(server, nick, channel, text, hostmask):
    import markov
    try:
        if (nick == "godzilla"):
            return
        if type(text) == unicode:
            text = text.encode('utf-8') # do i really need to do this? i'm so confused by the unicode in mysql
        if len(text.strip()) > 0:
            markov.add_sentence(text)
    except:
        logging.exception("Markov store failure")
    
#markov_store.handler = ("on_text", r'.*', irc.ALL_NICKS, ['#r/a/dio'])

def markov_say(server, nick, channel, text, hostmask):
    import markov
    try:
        server.privmsg(channel, markov.make_sentence())
    except:
        server.privmsg(channel, u'Something went wrong.')
    
markov_say.handler = ("on_text", r'[.!]say', irc.ALL_NICKS, irc.ALL_CHANNELS)

def hanyuu_response(response, delay):
    """Gets a chat response for a specific delay type and delay time.
    """
    self_messages = [(60*10, irc_colours['c3'] + u"Only less than ten minutes before you can request again!"),
                     (60*30, irc_colours['c2'] + u"You need to wait at most another half hour until you can request!"),
                     (60*61, irc_colours['c5'] + u"You still have quite a lot of time before you can request again..."),
                     (20000000, irc_colours['c4'] + u"No.")]
    song_messages = [(60*5, irc_colours['c3'] + u"Only five more minutes before I'll let you request that!"),
                     (60*15, irc_colours['c3'] + u"Just another 15 minutes to go for that song!"),
                     (60*40, irc_colours['c2'] + u"Only less than 40 minutes to go for that song!"),
                     (60*60, irc_colours['c2'] + u"You need to wait at most an hour for that song!"),
                     (60*60*4, irc_colours['c2'] + u"That song can be requested in a few hours!"),
                     (60*60*24, irc_colours['c5'] + u"You'll have to wait at most a day for that song..."),
                     (60*60*24*3, irc_colours['c5'] + u"That song can only be requested in a few days' time..."),
                     (60*60*24*7, irc_colours['c5'] + u"You might want to go do something else while you wait for that song."),
                     (20000000, irc_colours['c4'] + u"No.")]
    
    if (response == 2):
        for (d, r) in self_messages:
            if delay <= d:
                return r
    elif (response == 3):
        return u"I'm not streaming right now!"
    elif (response == 4):
        for (d, r) in song_messages:
            if delay <= d:
                return r
    return u"I have no idea what's happening~"
    

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
    import requests
    with manager.MySQLCursor() as cur:
        try:
            song = manager.Song(trackid)
        except (ValueError):
            return 1
        can_request = True
        hostmask_id = None
        delaytime = 0;
        if host:
            cur.execute("SELECT id, UNIX_TIMESTAMP(time) as timestamp \
                FROM `nickrequesttime` WHERE `host`=%s LIMIT 1;",
                (host,))
            if cur.rowcount == 1:
                row = cur.fetchone()
                hostmask_id = int(row['id'])
                if int(time.time()) - int(row['timestamp']) < 3600:
                    can_request = False
                    delaytime = 3600 - (int(time.time()) - int(row['timestamp']))
        can_afk = True
        cur.execute("SELECT isafkstream FROM `streamstatus` WHERE `id`=0;")
        if cur.rowcount == 1:
            row = cur.fetchone()
            afk = row['isafkstream']
            if not afk == 1:
                can_afk = False
        else:
            can_afk = False
        can_song = True
        cur.execute("SELECT UNIX_TIMESTAMP(lastplayed) as lp, UNIX_TIMESTAMP(lastrequested) as lr, requestcount from `tracks` WHERE `id`=%s", (trackid,))
        if cur.rowcount == 1:
            row = cur.fetchone()
            song_lp = row['lp']
            song_lr = row['lr']
            if int(time.time()) - song_lp < requests.songdelay(row['requestcount']) or int(time.time()) - song_lr < requests.songdelay(row['requestcount']):
                can_song = False
                if delaytime == 0:
                    delaytime = requests.songdelay(row['requestcount']) - (int(time.time()) - song_lp)
                    if int(time.time()) - song_lr > delaytime: # :/
                        delaytime = requests.songdelay(row['requestcount']) - (int(time.time()) - song_lr)
        if (not can_request):
            return (2, delaytime)
        elif (not can_afk):
            return (3, 0)
        elif (not can_song):
            return (4, delaytime)
        else:
            if host:
                if hostmask_id:
                    cur.execute("UPDATE `nickrequesttime` SET `time`=NOW() WHERE `id`=%s LIMIT 1;", (hostmask_id,))
                else:
                    cur.execute("INSERT INTO `nickrequesttime` (host, time) VALUES (%s, NOW());", (host,))
            cur.execute("UPDATE `tracks` SET `lastrequested`=NOW() WHERE `id`=%s", (trackid,))
            return song