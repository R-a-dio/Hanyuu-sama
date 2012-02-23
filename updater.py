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

class lp(object):
    def get(self, amount=5):
        limit = amount
        if (not isinstance(amount, int)):
            pass
        return list(webcom.fetch_lastplayed())
    def update(self, song):
        if (song.afk):
            self.update_track(song)
        self.update_hash(song)
    def update_track(self, song):
        webcom.update_lastplayed(song.id)
    def update_hash(self, song):
        lp = time.time() if song.lp is None else song.lp
        webcom.send_hash(song.digest, song.metadata, song.length, lp)

class np(object):
    _end = 0
    _start = int(time.time())
    def __init__(self):
        self.song = Song(meta=u"Placeholder", length=0.0)
    def change(self, song):
        """Changes the current playing song to 'song' which should be an
        updater.Song object"""
        lp.update(self.song)
        self.song = song
    def remaining(self, duration):
        self.length = (time.time() + duration) - self._start
        self._end = time.time() + self.length
    def end(self):
        return self._end if self._end != 0 else int(time.time())
    def __getattr__(self, name):
        return getattr(self.song, name)


class DJError(Exception):
    pass
class dj(object):
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
        

class Song(object):
    def __init__(self, id=None, meta=None, length=None, filename=None):
        if (not isinstance(id, (int, long, type(None)))):
            raise TypeError("'id' incorrect type, expected int or long")
        if (not isinstance(meta, (basestring, type(None)))):
            raise TypeError("'meta' incorrect type, expected string or unicode")
        if (not isinstance(length, (int, long, float, type(None)))):
            raise TypeError("'length' incorrect type, expected int or long")
        if (not isinstance(filename, (basestring, type(None)))):
            raise TypeError("'filename' incorrect type, expected string or unicode")
        self._length = length
        self._id = id
        self._digest = None
        self._lp = None
        self._songid = None
        self._faves = None
        if (meta is None) and (self.id == 0L):
            raise TypeError("Require either 'id' or 'meta' argument")
        elif (self.id != 0L):
            temp_filename, temp_meta = self.get_file(self.id)
            if (meta == None):
                meta = temp_meta
            if (filename == None):
                filename = temp_filename
        self._filename = filename
        self._metadata = self.fix_encoding(meta)
    def update(self, **kwargs):
        for key, value in kwargs.iteritems():
            if (key in dir(self)):
                setattr(self, "_" + key, value)
    @staticmethod
    def create_digest(metadata):
        from hashlib import sha1
        if (type(metadata) == unicode):
            metadata = metadata.encode('utf-8', 'replace')
        return sha1(metadata).hexdigest()
    @property
    def filename(self):
        return self._filename if self._filename != None else None
    @property
    def id(self):
        return self._id if self._id != None else 0L
    @property
    def songid(self):
        if (not self._songid):
            self._songid = self.get_songid(self.digest)
        return self._songid
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
        if (self._length == None):
            self._length = self.get_length(self)
        return int(self._length if self._length != None else 0)
    @property
    def lengthf(self):
        # Formatted
        return u'%02d:%02d' % divmod(self.length, 60)
    @property
    def lp(self):
        with webcom.MySQLCursor() as cur:
            query = "SELECT unix_timestamp(`dt`) AS ut FROM eplay,esong \
            WHERE eplay.isong = esong.id AND esong.hash = '{digest}' \
            ORDER BY `dt` DESC LIMIT 1;"
            cur.execute(query.format(digest=self.digest))
            if (cur.rowcount > 0):
                return cur.fetchone()['ut']
            return None
    @property
    def lpf(self):
        return parse_lastplayed(0 if self.lp == None else self.lp)
    @property
    def favecount(self):
        return len(self.faves)
    @property
    def faves(self):
        class Faves(object):
            def __init__(self, song):
                self.song = song
            def index(self, key):
                return list(self).index(key)
            def count(self, key):
                if (key in self):
                    return 1
                return 0
            def remove(self, key):
                self.__delitem__(key)
            def pop(self, index):
                raise NotImplemented("No popping allowed")
            def insert(self, index, value):
                raise NotImplemented("No inserting allowed, use append")
            def sort(self, cmp, key, reverse):
                raise NotImplemented("Sorting now allowed, use reverse(faves) or list(faves)")
            def append(self, nick):
                if (nick in self):
                    return
                with webcom.MySQLCursor() as cur:
                    cur.execute("SELECT * FROM enick WHERE nick=%s;",
                                (nick,))
                    if (cur.rowcount == 0):
                        cur.execute("INSERT INTO enick (`nick`) VALUES(%s);",
                                    (nick,))
                        cur.execute("SELECT * FROM enick WHERE nick=%s;",
                                    (nick,))
                        nickid = cur.fetchone()['id']
                        cur.execute("INSERT INTO efave (`inick`, `isong`) \
                        VALUES(%s, %s);", (nickid, self.song.songid))
                    elif (cur.rowcount == 1):
                        nickid = cur.fetchone()['id']
                        cur.execute("INSERT INTO efave (inick, isong) \
                        VALUES(%s, %s);", (nickid, self.song.songid))
                    if (self.song.id != 0L):
                        cur.execute("UPDATE `tracks` SET `priority`=priority+2\
                         WHERE `id`=%s;", (self.song.id,))
            def extend(self, seq):
                original = list(self)
                with webcom.MySQLCursor() as cur:
                    for nick in seq:
                        if (nick in original):
                            continue
                        original.append(nick)
                        cur.execute("SELECT * FROM enick WHERE nick=%s;",
                                (nick,))
                        if (cur.rowcount == 0):
                            cur.execute("INSERT INTO enick (`nick`) VALUES(%s);",
                                        (nick,))
                            cur.execute("SELECT * FROM enick WHERE nick=%s;",
                                        (nick,))
                            nickid = cur.fetchone()['id']
                            cur.execute("INSERT INTO efave (`inick`, `isong`) \
                            VALUES(%s, %s);", (nickid, self.song.songid))
                        elif (cur.rowcount == 1):
                            nickid = cur.fetchone()['id']
                            cur.execute("INSERT INTO efave (inick, isong) \
                            VALUES(%s, %s);", (nickid, self.song.songid))
                        if (self.song.id != 0L):
                            cur.execute("UPDATE `tracks` SET `priority`=\
                            priority+2 WHERE `id`=%s;", (self.song.id,))
            def __iter__(self):
                with webcom.MySQLCursor() as cur:
                    cur.execute("SELECT enick.nick FROM esong JOIN efave ON \
                    efave.isong = esong.id JOIN enick ON efave.inick = \
                    enick.id WHERE esong.hash = '{digest}' ORDER BY enick.nick\
                     ASC"\
                    .format(digest=self.song.digest))
                    for result in cur:
                        yield result['nick']
            def __reversed__(self):
                with webcom.MySQLCursor() as cur:
                    cur.execute("SELECT enick.nick FROM esong JOIN efave ON \
                    efave.isong = esong.id JOIN enick ON efave.inick = \
                    enick.id WHERE esong.hash = '{digest}' ORDER BY enick.nick\
                     DESC"\
                    .format(digest=self.song.digest))
                    for result in cur:
                        yield result['nick']
            def __len__(self):
                with webcom.MySQLCursor() as cur:
                    cur.execute("SELECT count(*) AS favecount FROM efave \
                    WHERE isong={songid}".format(songid=self.song.songid))
                    return cur.fetchone()['favecount']
            def __getitem__(self, key):
                return list(self)[key]
            def __setitem__(self, key, value):
                raise NotImplemented("Can't set on <Faves> object")
            def __delitem__(self, key):
                original = list(self)
                if (isinstance(key, basestring)):
                    # Nick delete
                    if (key in original):
                        # It is in there
                        with webcom.MySQLCursor() as cur:
                            cur.execute(
        "DELETE efave.* FROM efave LEFT JOIN enick ON enick.id = efave.inick WHERE \
        enick.nick=%s AND isong=%s;", (key, self.song.songid))
                    else:
                        raise KeyError("{0}".format(key))
                elif (isinstance(key, (int, long))):
                    try:
                        key = original[key]
                    except (IndexError):
                        raise IndexError("Fave index out of range")
                    else:
                        with webcom.MySQLCursor() as cur:
                            cur.execute(
                                        "DELETE efave.* FROM efave LEFt JOIN \
                                        enick ON enick.id = efave.inick WHERE \
                                        enick.nick=%s AND isong=%s;",
                                        (key, self.song.songid))
                else:
                    raise TypeError("Fave key has to be 'string' or 'int'")
            def __contains__(self, key):
                # TODO safe
                with webcom.MySQLCursor() as cur:
                    cur.execute("SELECT count(*) AS contains FROM efave JOIN\
                     enick ON enick.id = efave.inick WHERE enick.nick=%s \
                     AND efave.isong=%s;",
                     (key, self.song.songid))
                    if (cur.fetchone()['contains'] > 0):
                        return True
                    return False
            def __repr__(self):
                return u"Favorites of %s" % repr(self.song)
            def __str__(self):
                return self.__repr__().encode('utf-8')
        if (not self._faves):
            return Faves(self)
        return self._faves

    @property
    def playcount(self):
        with webcom.MySQLCursor() as cur:
            query = "SELECT count(*) playcount FROM eplay,esong WHERE \
            eplay.isong = esong.id AND esong.hash = '{digest}';"
            cur.execute(query.format(digest=self.digest))
            if (cur.rowcount > 0):
                return cur.fetchone()['playcount']
            else:
                return 0
    @property
    def afk(self):
        return False if self.id == None else True
    @staticmethod
    def get_length(song):
        if (song.filename == None):
            # try hash
            with webcom.MySQLCursor() as cur:
                cur.execute("SELECT len FROM `esong` WHERE `hash`=%s;",
                            (song.digest,))
                return cur.fetchone()['len']
        else:
            try:
                length = mutagen.File(song.filename).info.length
            except (IOError):
                logging.exception("Failed length check")
                return 0.0
    @staticmethod
    def get_file(songid):
        """Retrieve song path and metadata from the track ID"""
        from os.path import join
        with webcom.MySQLCursor() as cur:
            cur.execute("SELECT * FROM `tracks` WHERE `id`=%s LIMIT 1;" % (songid))
            if cur.rowcount == 1:
                row = cur.fetchone()
                artist = row['artist']
                title = row['track']
                path = join(config.music_directory, row['path'])
                meta = title if artist == u'' \
                        else artist + u' - ' + title
                return (path, meta)
            else:
                return (None, None)
    @staticmethod
    def get_songid(digest):
        with webcom.MySQLCursor() as cur:
            cur.execute("SELECT * FROM `esong` WHERE `hash`=%s LIMIT 1;",
                        (digest,))
            if (cur.rowcount == 1):
                return cur.fetchone()['id']
            else:
                return None
    @staticmethod
    def fix_encoding(metadata):
        try:
            try:
                return unicode(metadata, 'utf-8', 'strict')
            except (UnicodeDecodeError):
                return unicode(metadata, 'shiftjis', 'replace')
        except (TypeError):
            return metadata
    _search_replacer = webcom.make_replacer(**{r"\\": "", r"(": "",
                                         r")": "", r"*": ""})
    from re import compile
    _search_regex = compile(r"^[+\-<>~]")
    @classmethod
    def search(cls, query, limit=5):
        from os.path import join
        query_raw = query
        with webcom.MySQLCursor() as cur:
            search = cls._search_replacer(query)
            temp = []
            search = search.split(" ")
            for item in search:
                result = cls._search_regex.sub("", item)
                temp.append("+" + result)
            query = " ".join(temp)
            del temp
            try:
                query = query.encode("utf-8")
                query_raw = query_raw.encode("utf-8")
            except (UnicodeDecodeError):
                return []
            cur.execute("SELECT * FROM `tracks` WHERE `usable`='1' AND MATCH \
            (tags, artist, track, album) AGAINST (%s IN BOOLEAN MODE) \
            ORDER BY `priority` DESC, MATCH (tags, artist, track, \
            album) AGAINST (%s) DESC LIMIT %s;",
                    (query, query_raw, limit))
        result = []
        for row in cur:
            result.append(cls(
                              id=row['id'],
                              meta=row['title'] if row['artist'] == u'' \
                                else row['artist'] + u' - ' + row['title'],
                            filename=join(config.music_directory, row['path'])))
        return result
    def __str__(self):
        return self.__repr__()
    def __repr__(self):
        return (u"<Song [%s, %d, %s] at %s>" % (self.metadata, self.id,
                                             self.digest, hex(id(self))))\
                                             .encode("utf-8")
        
# declaration goes here
np = np()
dj = dj()
queue = queue()
lp = lp()
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