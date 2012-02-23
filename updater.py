import logging
import webcom
import mutagen
import time
import config
from random import randint
from multiprocessing import RLock
TYPE_REGULAR = 0
TYPE_REQUEST = 1

KIND_META_LENGTH = 0
KIND_TRACKID_META_LENGTH = 1
class EmptyQueue(Exception):
    pass

# TO DO
# Make sure the queue times are correct after adding a request
# Check string encoding ? seems to be non-unicode string returned
# Fix encoding on all metadata
# Make regular queue go empty when requests get entered
class queue(object):
    _lock = RLock()
    @staticmethod
    def get_timestamp(cur, type=TYPE_REGULAR):
        if (type == TYPE_REGULAR):
            cur.execute("SELECT unix_timestamp(time) AS timestamp, length FROM `queue` ORDER BY `time` DESC LIMIT 1;")
        elif (type == TYPE_REQUEST):
            cur.execute("SELECT unix_timestamp(time) AS timestamp, length FROM `queue` WHERE type={type} ORDER BY `time` DESC LIMIT 1;"\
                        .format(type=type))
        if (cur.rowcount > 0):
            result = cur.fetchone()
            return result['timestamp'] + int(result['length'])
        else:
            return np.end()
    def append_by_id(self, trackid, type=TYPE_REGULAR, meta=None, ip="0.0.0.0"):
        filename, metadata = webcom.get_song(trackid)
        length = Song.get_length(filename)
        if (meta == None):
            meta = metadata
        with webcom.MySQLCursor(lock=self._lock) as cur:
            timestamp = self.get_timestamp(cur, type)
            meta = cur.escape_string(meta.encode("utf-8"))
            if (type == TYPE_REQUEST):
                cur.execute("DELETE FROM `queue` WHERE trackid={trackid}"\
                            .format(trackid=trackid))
                cur.execute("UPDATE `queue` SET time=from_unixtime(unix_timestamp(time) + {length}) WHERE type=0;"\
                            .format(length=length))
                cur.execute("DELETE FROM `queue` WHERE type=0 ORDER BY time DESC LIMIT 1")
            cur.execute("INSERT INTO `queue` (time, ip, type, meta, length, trackid) VALUES (from_unixtime({timestamp}), '{ip}', {type}, '{meta}', {length}, {trackid});"\
                    .format(timestamp=int(timestamp), ip=ip, type=type, meta=meta, length=length, trackid=trackid))
    def append_by_meta(self, meta, length, type=TYPE_REGULAR, ip="0.0.0.0"):
        with webcom.MySQLCursor(lock=self._lock) as cur:
            timestamp = self.__get_timestamp(cur, type)
            meta = cur.escape_string(meta.encode("utf-8"))
            if (type == TYPE_REQUEST):
                cur.execute("UPDATE `queue` SET time=from_unixtime(unix_timestamp(time) + {length}) WHERE type=0;"\
                            .format(length=length))
                cur.execute("DELETE FROM `queue` WHERE type=0 ORDER BY time DESC LIMIT 1")
            cur.execute("INSERT INTO `queue` (time, ip, type, meta, length) VALUES (from_unixtime({timestamp}), '{ip}', {type}, '{meta}', {length});"\
                        .format(timestamp=int(timestamp), ip=ip, type=type, meta=meta, length=length))
    def append_many(self, queuelist, kind=KIND_META_LENGTH):
        """queue should be an iterater containing
            (metadata, length) tuples
        """
        with webcom.MySQLCursor(lock=self._lock) as cur:
            timestamp = self.get_timestamp(cur)
            if (kind == KIND_META_LENGTH):
                query = "INSERT INTO `queue` (time, meta, length) VALUES (from_unixtime({time}), '{meta}', {length});"
                for meta, length in queuelist:
                    meta = cur.escape_string(meta.encode("utf-8"))
                    cur.execute(query.format(time=int(timestamp), meta=meta, length=length))
                    timestamp += length
            elif (kind == KIND_TRACKID_META_LENGTH):
                query = "INSERT INTO `queue` (trackid, time, meta, length) VALUES ({trackid}, from_unixtime({time}), '{meta}', {length});"
                for trackid, meta, length in queuelist:
                    meta = cur.escape_string(meta.encode("utf-8"))
                    cur.execute(query.format(trackid=trackid, time=int(timestamp), meta=meta, length=length))
                    timestamp += length
    def append_random(self, amount=10):
        """Appends random songs to the queue,
        these come from the tracks table in
        the database"""
        if (amount > 100):
            amount = 100
        with webcom.MySQLCursor(lock=self._lock) as cur:
            cur.execute("SELECT tracks.id AS trackid, artist, track, path FROM tracks WHERE `usable`=1 AND NOT EXISTS (SELECT 1 FROM queue WHERE queue.trackid = tracks.id) ORDER BY `lastplayed` ASC, `lastrequested` ASC LIMIT 100;")
            result = list(cur.fetchall())
            queuelist = []
            n = 99
            for i in xrange(amount):
                row = result.pop(randint(0, n))
                filename = "{0}/{1}".format(config.music_directory, row['path'])
                meta = row['track']
                if row['artist'] != u'':
                    meta = row['artist'] + u' - ' + meta
                length = Song.get_length(filename)
                queuelist.append((row['trackid'], meta, length))
                n -= 1
        self.append_many(queuelist, kind=KIND_TRACKID_META_LENGTH)
    def pop(self):
        try:
            with webcom.MySQLCursor(lock=self._lock) as cur:
                cur.execute("SELECT * FROM `queue` ORDER BY `time` ASC LIMIT 1;")
                if (cur.rowcount > 0):
                    result = cur.fetchone()
                    cur.execute("DELETE FROM `queue` WHERE id={id};"\
                                .format(id=result['id']))
                    return Song(id=result['trackid'],
                                meta=result['meta'].decode('utf-8'),
                                length=result['length'])
                else:
                    raise EmptyQueue("Queue is empty")
        finally:
            if (self.length < 20):
                self.append_random(20 - self.length)
    def clear(self):
        with webcom.MySQLCursor(lock=self._lock) as cur:
            cur.execute("DELETE FROM `queue`;")
    @property
    def length(self):
        return len(self)
    def __len__(self):
        with webcom.MySQLCursor(lock=self._lock) as cur:
            cur.execute("SELECT COUNT(*) as count FROM `queue`;")
            return int(cur.fetchone()['count'])
    def __iter__(self):
        with webcom.MySQLCursor(lock=self._lock) as cur:
            cur.execute("SELECT * FROM `queue` ORDER BY `time` ASC LIMIT 5;")
            for row in cur:
                yield Song(id=row['trackid'],
                           meta=row['meta'].decode('utf-8'),
                           length=row['length'])
queue = Queue()

class LastPlayed(object):
    def get(self, amount=5):
        limit = amount
        if (not isinstance(amount, int)):
            pass
        return list(webcom.fetch_lastplayed())
    def update(self, id, digest, title=None, length=None, lastplayed=None):
        lastplayed = time.time() if lastplayed is None else lastplayed
        if (id != None):
            self.update_track(id)
        self.update_hash(digest, title, length, lastplayed)
    def update_track(self, id):
        webcom.update_lastplayed(id)
    def update_hash(self, digest=None, title=None, length=None, lastplayed=None):
        lastplayed = time.time() if lastplayed is None else lastplayed
        webcom.send_hash(digest, title, length, lastplayed)
    def get_lastplayed(self, digest):
        webcom.get_lastplayed(digest)
        
lp = LastPlayed()

class NowPlaying(object):
    __nowplaying = None
    __length = 0
    __digest = None
    __playcount = 0
    __lastplayed = None
    __songid = None
    __trackid = None
    __end = 0
    __start = int(time.time())
    def change(self, id=None, meta=None, length=None, lastplayed=None):
        digest = None
        if (id != None):
            metadb = webcom.get_song(id)[1]
            digest = webcom.generate_hash(metadb)
        elif (meta != None):
            meta = webcom.fix_encoding(meta)
            digest = webcom.generate_hash(meta)
        else:
            raise TypeError("Requires 'id' or 'meta' got neither")
        
        lp.update(self.__trackid, self.__digest,
                  self.__nowplaying, self.__length,
                  self.__lastplayed)
        
        self.__trackid = id if id != None else None
        self.__nowplaying = meta
        self.__songid, self.__playcount, self.__length, self.__lastplayed = webcom.get_hash(digest)
    def remaining(self, duration):
        self.__length = (time.time() + duration) - self.__start
        self.__end = time.time() + self.__length
    def end(self):
        return self.__end if self.__end != 0 else int(time.time())
    def lp(self):
        return self.__lastplayed
    def lpf(self):
        return parse_lastplayed(0 if self.__lastplayed == None else self.__lastplayed)
    def length(self):
        return self.__length
    def lengthf(self):
        return get_ms(self.__length)
    def favecount(self):
        return webcom.count_fave(self.__songid)
    def faves(self):
        return webcom.get_faves(self.__digest)
    def playcount(self):
        return self.__playcount
    def afk(self):
        return False if self.__trackid == None else True
    def __call__(self):
        return self.__nowplaying
np = NowPlaying()

class DJError(Exception):
    pass
class DJ(object):
    __djid = webcom.get_djid()
    __djname = webcom.get_djuser(__djid)
    __djuser = __djname
    def set(self, djname):
        try:
            temp_user = webcom.get_djname(djname)
        except (IOError):
            logging.exception("DJ.conf is missing, assuming DJ does not exist")
            raise DJError("No such DJ")
        if (temp_user != None):
            self.__djname = djname
            self.__djuser = temp_user
            self.__djid = webcom.get_djid(self.__djuser)
            webcom.send_status(djid=self.__djid)
        else:
            logging.info("DJ not found {dj}".format(dj=djname))
            raise DJError("No such DJ")
    def __call__(self):
        return self.__djid
    def get_id(self):
        return self.__djid
    def get_name(self):
        return self.__djname
    def get_user(self):
        return self.__djuser
        
dj = DJ()

class Song(object):
    def __init__(self, id=None, meta=None, length=0.0):
        if (meta is None) and (id is None):
            raise TypeError("Require either 'id' or 'meta' argument")
        elif (id == None) or (meta == None) or (length == 0.0):
            # do shit
            filename, meta = webcom.get_song(id)
            length = self.get_length(filename)
        self._metadata = meta
        self._length = length
        self._id = id
        self._digest = None
        self._lp = None
    @staticmethod
    def create_digest(metadata):
        from hashlib import sha1
        if (type(metadata) == unicode):
            metadata = metadata.encode('utf-8', 'replace')
        return sha1(metadata).hexdigest()
    @property
    def id(self):
        return self._id if self._id != None else L0
    @property
    def metadata(self):
        return self._metadata if self._metadata != None else u''
    @property
    def digest(self):
        if (self._digest == None):
            self._digest = self.create_digest(self.metadata)
        return self._digest
    @property
    def length(self):
        # Make it int instead of float
        return int(self._length)
    @property
    def lengthf(self):
        # Formatted
        return u'%02d:%02d' % divmod(int(self._length), 60)
    @property
    def lp(self):
        pass
    lastplayed = lp
    @staticmethod
    def get_length(filename):
        try:
            length = mutagen.File(filename).info.length
        except (IOError):
            logging.exception("Failed length check")
            length = 0.0
        return length
    def __str__(self):
        return self.__repr__().encode("utf-8")
    def __repr__(self):
        return u"<Song [%s, %.2f, %s] at %s>" % (self.metadata, self.id,
                                             self.digest, hex(id(self)))
# GENERAL TOOLS GO HERE

def get_ms(self, seconds):
        m, s = divmod(seconds, 60)
        return u"%02d:%02d" % (m, s)
def parse_lastplayed(seconds):
    if (seconds > 0):
        difference = int(time.time()) - seconds
        year, month = divmod(difference, 31557600)
        month, week = divmod(month, 2629800)
        week, day = divmod(week, 604800)
        day, hour = divmod(day, 86400)
        hour, minute = divmod(hour, 3600)
        minute, second = divmod(minute, 60)
        result = ''
        if (year): result += u'%d year(s) ' % year
        if (month): result += u'%d month(s) ' % month
        if (week): result += u'%d week(s) ' % week
        if (day): result += u'%d day(s) ' % day
        if (hour): result += u'%d hour(s) ' % hour
        if (minute): result += u'%d minute(s) ' % minute
        if (second): result += u'%d second(s) ' % second
        return result.strip()
    else:
        return u'Never before'