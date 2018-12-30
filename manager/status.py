from __future__ import absolute_import
import time
import re
import logging
import threading
from multiprocessing.managers import RemoteError

import requests

from .util import MySQLNormalCursor, MySQLCursor, get_ms
from .song import Song
import bootstrap
import config

class LP(object):
    def get(self, amount=5):
        return list(self.iter(amount))

    def iter(self, amount=5):
        if (not isinstance(amount, int)):
            pass
        with MySQLCursor() as cur:
            cur.execute("SELECT esong.meta FROM eplay JOIN esong ON \
            esong.id = eplay.isong ORDER BY eplay.dt DESC LIMIT %s;",
                        (amount,))
            for row in cur:
                yield Song(meta=row['meta'])

    def __iter__(self):
        return self.iter()


class Status(object):
    __metaclass__ = bootstrap.Singleton
    _timeout = bootstrap.Switch(True, 0)
    _handlers = []
    _last_listeners = 0

    @property
    def listeners(self):
        return int(self.cached_status.get('listeners', 0))

    @property
    def peak_listeners(self):
        return int(self.cached_status.get('peak_listeners', 0))

    @property
    def online(self):
        return self.status.get("online", False)

    @property
    def started(self):  # NO LONGER RETURNED BY ICECAST. CHECK THIS.
        return self.cached_status.get("stream_start", "Unknown")

    @property
    def type(self):  # This is never used.
        return self.cached_status.get("server_type", None)

    @property
    def current(self):  # Not even needed. Hanyuu uses ICY-Metadata...
        return self.cached_status.get("current_song", u"")

    @property
    def thread(self):
        """thread getter, use status.thread"""
        with MySQLCursor() as cur:
            cur.execute("SELECT `thread` FROM `streamstatus`;")
            if (cur.rowcount == 0):
                return u""
            return cur.fetchone()['thread']

    @thread.setter
    def thread(self, url):
        """thread setter, use status.thread = thread"""
        with MySQLCursor() as cur:
            cur.execute("UPDATE `streamstatus` SET \
            `thread`=%(thread)s;", {"thread": url})

    @property
    def requests_enabled(self):
        with MySQLNormalCursor() as cur:
            cur.execute("SELECT requesting FROM streamstatus LIMIT 1;")

            for requesting, in cur:
                return bool(requesting)
            return False

    @requests_enabled.setter
    def requests_enabled(self, value):
        value = bool(value)

        with MySQLCursor() as cur:
            # !!!WARNING: This sets all rows in streamstatus, but since we
            # generally only have one row in it, this is not a problem.
            # !!!WARNING ABOVE
            cur.execute("UPDATE streamstatus SET requesting=%s;", (value,))

    @property
    def last_listeners(self):
        return self._last_listeners

    @last_listeners.setter
    def last_listeners(self, ll):
        self._last_listeners = ll

    @property
    def cached_status(self):
        if (not self._timeout):
            return self.status
        return self._status

    @property
    def status(self):
        import streamstatus
        self._status = streamstatus.get_status(config.master_server)
        self._timeout.reset(9)
        for handle in self._handlers:
            try:
                handle(self._status)
            except:
                logging.exception("Status handler failed")
        return self._status

    def add_handler(self, handle):
        """Adds a handler to the status object.

        The handle is called every time the cached status dict is updated with
        new values with the current dict as only argument.
        """
        self._handlers.append(handle)

    def update(self):
        """Updates the database with current collected info"""
        with MySQLNormalCursor() as cur:
            cur.execute(
                "INSERT INTO streamstatus (id, lastset, listeners)"
                " VALUES (0, NOW(), %s) ON DUPLICATE KEY UPDATE"
                " lastset=NOW(), listeners=%s;",
                (self.listeners, self.listeners),
            )


class DJError(Exception):
    pass


class DJ(object):
    @property
    def id(self):
        with MySQLNormalCursor() as cur:
            cur.execute("SELECT djid FROM streamstatus LIMIT 1;")
            for djid, in cur:
                return djid

            self.id = 18
            return 18

    @id.setter
    def id(self, value):
        if (not isinstance(value, (int, long, float))):
            raise TypeError("Expected integer")

        with MySQLCursor() as cur:
            cur.execute("SELECT user FROM users WHERE djid=%s LIMIT 1;")
            for user, in cur:
                cur.execute("UPDATE streamstatus SET djid=%s, djname=%s", (value, user))
                return

            # Only reached if the for above doesn't run at all
            raise TypeError("Invalid ID, no such DJ")

    @property
    def name(self):
        with MySQLNormalCursor() as cur:
            cur.execute("SELECT djname FROM streamstatus LIMIT 1;")
            for name, in cur:
                return name
            return None

    @name.setter
    def name(self, name):
        username = self.is_valid(name)
        if username is None:
            raise TypeError("Invalid name, no such DJ")

        with MySQLCursor() as cur:
            if username == "guest" and ':' in name:
                guestname = name.split(':')[1]
                if len(guestname) > 0:
                    # 43 is the guest dj profile.
                    cur.execute("UPDATE djs SET djname=%s where id=43 LIMIT 1", (guestname,))
            cur.execute("UPDATE streamstatus SET djid=(SELECT djid FROM users WHERE user=%s LIMIT 1), djname=%s",
                        (username, name))

    @property
    def user(self):
        with MySQLNormalCursor() as cur:
            cur.execute("SELECT user FROM users WHERE djid=(SELECT djid FROM streamstatus LIMIT 1);")
            for user, in cur:
                return user
            self.id = 18 # MAGIC CONSTANTS (really just AFK streamers ID)
            return 'AFK'

    @classmethod
    def is_valid(cls, name):
        with open(config.djfile) as f:
            for line in f:
                wildcards, dj = line.split('@')

                wildcards = wildcards.split('!')
                dj = dj.strip()

                for wc in wildcards:
                    wc = re.escape(wc)
                    wc = '^' + wc
                    wc = wc.replace('*', '.*')
                    if re.match(wc, name, re.I):
                        return unicode(dj)


class NP(Song):
    def __init__(self):
        with MySQLCursor() as cur:
            cur.execute("SELECT * FROM `streamstatus` LIMIT 1;")
            for row in cur:
                Song.__init__(self, id=row['trackid'], meta=row['np'])
                self._end = row["end_time"]
                self._start = row["start_time"]
                break
            else:
                super(NP, self).__init__(meta=u"", length=0.0)
                self._end = 0
                self._start = int(time.time())

    @property
    def start(self):
        return self._start

    @start.setter
    def start(self, value):
        self._start = value
        with MySQLCursor() as cur:
            cur.execute("UPDATE `streamstatus` SET `start_time`=%s", (value,))

    @property
    def end(self):
        return self._end

    @end.setter
    def end(self, value):
        self._end = value
        with MySQLCursor() as cur:
            cur.execute("UPDATE `streamstatus` SET `end_time`=%s", (value,))

    def remaining(self, remaining):
        self.update(length=(time.time() + remaining) - self.start)
        self.end = time.time() + remaining

    @property
    def position(self):
        return int(time.time() - self.start)

    @property
    def positionf(self):
        return get_ms(self.position)

    @classmethod
    def change(cls, song):
        """Changes the current playing song to 'song' which should be an
        manager.Song object"""
        import re
        current = cls()
        # old stuff
        if (song.afk):
            Status().requests_enabled = True
        else:
            Status().requests_enabled = False
        if (current == song):
            return
        if (current.metadata != u""):
            # Get the listener difference. Disregard it if the numbers
            # are just too low; that probably means we are just starting
            # up or we are switching DJ.
            cur_list = Status().listeners
            last_list = Status().last_listeners
            Status().last_listeners = cur_list
            diff = (cur_list - last_list) if (cur_list > 10 and last_list > 10) else None
            current.update(lp=time.time(), ldiff=diff)
            if (current.length == 0):
                current.update(length=(time.time() - current._start))

        # New stuff
        current.start = int(time.time())
        current.end = int(time.time()) + song.length

        # tunein
        def tunein(song):
            try:
                url = "http://air.radiotime.com/Playing.ashx"
                urlparams = {
                    'partnerId': config.tunein_id,
                    'partnerKey': config.tunein_key,
                    'id': config.tunein_station}
                if song.metadata != u'':
                    match = re.match(
                        r"^((?P<artist>.*?) - )?(?P<title>.*)",
                        song.metadata)
                    artist = match.groups()[1]
                    title = match.groups()[2]
                    if artist:
                        urlparams['artist'] = artist.encode(
                            'utf-8') if isinstance(artist,
                                                   unicode) else artist
                    if title:
                        urlparams['title'] = title.encode(
                            'utf-8') if isinstance(title,
                                                   unicode) else title
                r = requests.get(url,
                    headers={'User-Agent': config.user_agent},
                    params=urlparams,
                    timeout=8
                )
                r.raise_for_status()
            except:
                logging.warning("Error when contacting tuneIn API")

        tunein_thread = threading.Thread(target=tunein, args=(song,), name="TuneIn")
        tunein_thread.daemon = True
        tunein_thread.start()

        with MySQLCursor() as cur:
            djid = DJ().id
            cur.execute("INSERT INTO `streamstatus` (id, lastset, \
                            np, djid, listeners, start_time, end_time, \
                            isafkstream, trackid) VALUES (0, NOW(), %(np)s, %(djid)s, \
                            %(listener)s, %(start)s, %(end)s, %(afk)s, %(trackid)s) ON DUPLICATE KEY \
                            UPDATE `lastset`=NOW(), `np`=%(np)s, `djid`=%(djid)s, \
                            `listeners`=%(listener)s, `start_time`=%(start)s, \
                            `end_time`=%(end)s, `isafkstream`=%(afk)s, `trackid`=%(trackid)s;",
                        {"np": song.metadata,
                         "djid": djid if djid else 18,
                         "listener": Status().listeners,
                         "start": current._start,
                         "end": current._end,
                         "afk": 1 if song.afk else 0,
                         "trackid": song.id
                         })

        import bot
        bot.announce()

    def __repr__(self):
        return "<Playing " + Song.__repr__(self)[1:]

    def __str__(self):
        return self.__repr__()
