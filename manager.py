import logging
import mutagen
import time
import config
from random import randint
from multiprocessing import RLock, Queue
import MySQLdb
import MySQLdb.cursors
from threading import Event, Thread, Timer

def start(state):
    global processor_queue
    if (state):
        processor_queue = state[0]
        np.change(state[1])
    else:
        processor_queue = None
    np._event = Event()
    np.updater = Thread(target=np.send, args=(np._event,))
    np.updater.name = "Now Playing updater"
    np.updater.daemon = 1
    np.updater.start()
def shutdown():
    np._event.set()
    np.updater.join()
    return (processor_queue, np.song)

class MySQLCursor:
    """Return a connected MySQLdb cursor object"""
    counter = 0
    def __init__(self, cursortype=MySQLdb.cursors.DictCursor, lock=None):
        self.counter += 1
        self.conn = MySQLdb.connect(host=config.dbhost,
                                user=config.dbuser,
                                passwd=config.dbpassword,
                                db=config.dbtable,
                                charset='utf8',
                                use_unicode=True)
        self.curtype = cursortype
        self.lock = lock
    def __enter__(self):
        if (self.lock != None):
            self.lock.acquire()
        self.cur = self.conn.cursor(self.curtype)
        self.cur.escape_string = MySQLdb.escape_string
        return self.cur
        
    def __exit__(self, type, value, traceback):
        self.cur.close()
        self.conn.commit()
        self.conn.close()
        if (self.lock != None):
            self.lock.release()
        return

class Proxy(object):
    """Generic proxy class, should be subclassed and then the
    method_list and object_name should be overwritten
    
    method_list is a list of strings of method names in the original object
    to create a proxy of.
    
    object_name is a string the name of the specific object this is a proxy off
    
    Look at the proxy_np below to see an example
    """
    method_list = []
    object_name = ""
    def __init__(self, queue):
        object.__init__(self)
        self._queue = queue
    def __getattr__(self, key):
        if (key in self.method_list):
            return lambda *a, **k: self._queue.put((self.object_name, key,
                                                    a, k))
        else:
            raise AttributeError()
        
def use_queue(queue):
    """Function to make the whole module use pipe magic to access the functions
    in the main thread instead of in the process this is used from
    
    Current implementation only allows calling the
    method WITHOUT return value nor exceptions"""
    class proxy_stream(Proxy):
        method_list = ["down", "up"]
        object_name = "stream"
        UP = True
        DOWN = False
        LISTENER = 0
        STATUS = 1
        STREAMER = 2
    class proxy_np(Proxy):
        method_list = ["change",
                       "end",
                       "remaining"]
        object_name = "np"
    global np, stream
    np = proxy_np(queue)
    stream = proxy_stream(queue)
    
def read_queue(q):
    """blocks on a queue.get, and launches any incoming requests into this
    process and thread, exceptions are caught and ignored"""
    logging.info("THREADING: Started manager proxy")
    while True:
        call_request = q.get()
        if (call_request == None):
            break
        else:
            try:
                obj, key, args, kwargs = call_request
                obj = globals()[obj]
                try:
                    getattr(obj, key)(*args, **kwargs)
                except (TypeError):
                    getattr(obj, key)
            except:
                pass
    logging.info("THREADING: Stopped manager proxy")
processor_queue = None

def get_queue():
    """Returns a multiprocessing.Queue to send to other processes that require
    access to the manager pieces that aren't synced with the database
    
    You require to call manager.use_queue(queue) when the separate process
    is started, you don't have to do this if you are accessing manager.lp,
    manager.queue or manager.Song, those are all synced"""
    global processor_queue
    if (not processor_queue):
        processor_queue = Queue()
        # This spawns a thread to feed from the queue
        from threading import Thread
        thread = Thread(target=read_queue, args=(processor_queue,))
        thread.name = "Manager Proxy"
        thread.daemon = 1
        thread.start()
    return processor_queue
REGULAR = 0
REQUEST = 1
POPPED = 2

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
    def get_timestamp(cur, type=REGULAR):
        if (type == REGULAR):
            cur.execute("SELECT unix_timestamp(time) AS timestamp, length FROM `queue` ORDER BY `time` DESC LIMIT 1;")
        elif (type == REQUEST):
            cur.execute("SELECT unix_timestamp(time) AS timestamp, length FROM `queue` WHERE type={type} ORDER BY `time` DESC LIMIT 1;"\
                        .format(type=type))
        if (cur.rowcount > 0):
            result = cur.fetchone()
            result = result['timestamp'] + int(result['length'])
        else:
            result = np.end()
        return result if result != None else time.time()
    
    def append_request(self, song, ip="0.0.0.0"):
        with MySQLCursor(lock=self._lock) as cur:
            timestamp = self.get_timestamp(cur, REQUEST)
            cur.execute("UPDATE `queue` SET time=from_unixtime(\
                            unix_timestamp(time) + %s) WHERE type=0;",
                            (song.length,))
            cur.execute("DELETE FROM `queue` WHERE type=0 \
                            ORDER BY time DESC LIMIT 1")
            cur.execute("INSERT INTO `queue` (trackid, time, ip, \
            type, meta, length) VALUES (%s, from_unixtime(%s), %s, %s, %s, %s);",
                        (song.id, int(timestamp), ip, REQUEST,
                          song.metadata, song.length))
  
    def append(self, song):
        with MySQLCursor(lock=self._lock) as cur:
            timestamp = self.get_timestamp(cur, REGULAR)
            cur.execute("INSERT INTO `queue` (trackid, time, type, meta, \
            length) VALUES (%s, from_unixtime(%s), %s, %s, %s);",
                        (song.id, int(timestamp), REGULAR,
                          song.metadata, song.length))
    def append_many(self, songlist):
        """queue should be an iterator containing
            Song objects
        """
        with MySQLCursor(lock=self._lock) as cur:
            timestamp = self.get_timestamp(cur)
            for song in songlist:
                if (song.afk):
                    cur.execute(
                                "INSERT INTO `queue` (trackid, time, meta, \
                                length) VALUES (%s, \
                                from_unixtime(%s), %s, %s);",
                                (song.id, int(timestamp),
                                  song.metadata, song.length)
                                )
                    timestamp += song.length
                else:
                    cur.execute(
                                "INSERT INTO `queue` (time, meta, length) \
                                VALUES (from_unixtime(%s), %s, \
                                %s);",
                                (int(timestamp), song.metadata, song.length)
                                )
                    timestamp += song.length

    def append_random(self, amount=10):
        """Appends random songs to the queue,
        these come from the tracks table in
        the database"""
        if (amount > 100):
            amount = 100
        with MySQLCursor(lock=self._lock) as cur:
            cur.execute("SELECT tracks.id AS trackid \
            FROM tracks WHERE `usable`=1 AND NOT EXISTS (SELECT 1 FROM queue \
            WHERE queue.trackid = tracks.id) ORDER BY `lastplayed` ASC, \
            `lastrequested` ASC LIMIT 100;")
            result = list(cur.fetchall())
            queuelist = []
            n = 99
            for i in xrange(amount):
                row = result.pop(randint(0, n))
                queuelist.append(Song(id=row['trackid']))
                n -= 1
        self.append_many(queuelist)
    def pop(self):
        # TODO:
        #     Adjust the estimated play time for old queues, i.e. update them
        #     if necessary to current times
        #     Vin - this TODO should probably be moved to clear_pops instead
        if (len(self) == 0):
            self.append_random(20)
        try:
            with MySQLCursor(lock=self._lock) as cur:
                cur.execute("SELECT * FROM `queue` ORDER BY `time` ASC LIMIT 1;")
                if (cur.rowcount > 0):
                    result = cur.fetchone()
                    cur.execute("UPDATE `queue` SET `type`=2 WHERE id=%s;", (result['id'],))
                    return Song(id=result['trackid'],
                                meta=result['meta'],
                                length=result['length'])
                else:
                    raise EmptyQueue("Queue is empty")
        finally:
            if (self.length < 20):
                self.append_random(20 - self.length)
    def clear_pops(self):
        with MySQLCursor(lock=self._lock) as cur:
            cur.execute("DELETE FROM `queue` WHERE `type`=2;")
    def check_times(self):
        correct_time = np.end()
        with MySQLCursor(lock=self._lock) as cur:
            cur.execute("SELECT unix_timestamp(time) AS time FROM \
                `queue` ORDER BY `time` ASC LIMIT 1;")
            for row in cur:
                current_time = row['time']
            difference = correct_time - current_time
            if (5 > difference > -5):
                cur.execute("UPDATE `queue` SET `time`=from_unixtime(\
                    unix_timestamp(time) + %s);", (difference,))
    def clear(self):
        with MySQLCursor(lock=self._lock) as cur:
            cur.execute("DELETE FROM `queue`;")
    @property
    def length(self):
        return len(self)
    def __len__(self):
        with MySQLCursor(lock=self._lock) as cur:
            cur.execute("SELECT COUNT(*) as count FROM `queue`;")
            return int(cur.fetchone()['count'])
    def __iter__(self):
        with MySQLCursor(lock=self._lock) as cur:
            cur.execute("SELECT * FROM `queue` ORDER BY `time` ASC LIMIT 5;")
            for row in cur:
                yield Song(id=row['trackid'],
                           meta=row['meta'],
                           length=row['length'])

class lp(object):
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

class status(object):
    _timeout = time.time() - 60
    @property
    def listeners(self):
        return int(self.cached_status.get('Current Listeners', 0))
    @property
    def peak_listeners(self):
        return int(self.cached_status.get('Peak Listeners', 0))
    @property
    def online(self):
        return config.icecast_mount in self.status
    @property
    def started(self):
        return self.cached_status.get("Mount started", "Unknown")
    @property
    def type(self):
        return self.cached_status.get("Content Type", None)
    @property
    def current(self):
        return self.cached_status.get("Current Song", u"")
    def s_thread(self, url):
        """thread setter, use status.thread = thread"""
        with MySQLCursor() as cur:
            cur.execute("INSERT INTO `radvars` (name, value) VALUES \
            ('curthread', %(thread)s) ON DUPLICATE KEY UPDATE \
            `value`=%(thread)s;", {"thread": url})
    def g_thread(self):
        """thread getter, use status.thread"""
        with MySQLCursor() as cur:
            cur.execute("SELECT `value` FROM `radvars` WHERE \
            `name`='curthread' LIMIT 1;")
            if (cur.rowcount == 0):
                return u""
            return cur.fetchone()['value']
    thread = property(g_thread, s_thread)
    def g_requests_enabled(self):
        with MySQLCursor() as cur:
            cur.execute("SELECT * FROM radvars WHERE `name`='requesting';")
            if (cur.rowcount > 0):
                return bool(cur.fetchone()['value'])
            else:
                # We create our entry here because it doesn't exist
                cur.execute("INSERT INTO radvars (name, value) VALUES \
                            ('requesting', 0);")
                return False
    def s_requests_enabled(self, value):
        from types import BooleanType
        with MySQLCursor() as cur:
            current = self.requests_enabled
            if (isinstance(value, BooleanType)):
                if (current != value):
                    value = 1 if value else 0
                    cur.execute("UPDATE `radvars` SET `value`=%s WHERE `name`\
                                ='requesting';", (value,))
    requests_enabled = property(g_requests_enabled, s_requests_enabled)
    @property
    def cached_status(self):
        if (time.time() - self._timeout > 9):
            return self.status.get(config.icecast_mount, {})
        return self._status.get(config.icecast_mount, {})
    @property
    def status(self):
        import streamstatus
        self._status = streamstatus.get_status(config.icecast_server)
        self._timeout = time.time()
        return self._status
    def update(self):
        """Updates the database with current collected info"""
        with MySQLCursor() as cur:
            cur.execute("INSERT INTO `streamstatus` (id, lastset, \
                np, djid, listeners, start_time, end_time, \
                isafkstream) VALUES (0, NOW(), %(np)s, %(djid)s, \
                %(listener)s, %(start)s, %(end)s, %(afk)s) ON DUPLICATE KEY \
                UPDATE `lastset`=NOW(), `np`=%(np)s, `djid`=%(djid)s, \
                `listeners`=%(listener)s, `start_time`=%(start)s, \
                `end_time`=%(end)s, `isafkstream`=%(afk)s;",
                        {"np": np.metadata,
                         "djid": dj.id,
                         "listener": self.listeners,
                         "start": np._start,
                         "end": np.end(),
                         "afk": 1 if np.afk else 0
                         })
class NP(object):
    _end = 0
    _start = int(time.time())
    def __init__(self):
        self.song = Song(meta=u"", length=0.0)
    def send(self, event):
        logging.info("THREADING: Starting now playing updater")
        while not event.is_set():
            if (status.online):
                status.update()
                stream.up(stream.STATUS)
            else:
                stream.down(stream.STATUS)
            time.sleep(10)
        logging.info("THREADING: Stopping now playing updater")
    def change(self, song):
        """Changes the current playing song to 'song' which should be an
        manager.Song object"""
        if (song.afk):
            status.requests_enabled = True
        else:
            status.requests_enabled = False
        if (self.song == song):
            return
        if (self.song.metadata != u""):
            self.song.update(lp=time.time())
            if (self.song.length == 0):
                self.song.update(length=(time.time() - self._start))
        self.song = song
        self._start = int(time.time())
        self._end = int(time.time()) + self.song.length
        import irc
        try:
            irc.session.announce()
        except (AttributeError):
            pass
    def remaining(self, remaining):
        self.song.update(length=(time.time() + remaining) - self._start)
        self._end = time.time() + remaining
    @property
    def position(self):
        return int(time.time() - self._start)
    @property
    def positionf(self):
        return get_ms(self.position)
    def end(self):
        return self._end if self._end != 0 else int(time.time())
    def __getattr__(self, name):
        return getattr(self.song, name)
    def __repr__(self):
        return "<Playing " + repr(self.song)[1:]
    def __str__(self):
        return self.__repr__()

class DJError(Exception):
    pass
class dj(object):
    _name = None
    _cache = {}
    def g_id(self):
        user = self.user
        if (user in self._cache):
            return self._cache[user]
        with MySQLCursor() as cur:
            # we don't have a user
            if (not self.user):
                cur.execute("SELECT `djid` FROM `streamstatus`")
                if (cur.rowcount == 0):
                    self.id = 18
                    return
                djid = cur.fetchone()['djid']
                cur.execute("SELECT `user` FROM `users` WHERE `djid`=%s \
                LIMIT 1;", (djid,))
                if (cur.rowcount > 0):
                    user = cur.fetchone()['user']
                    self._cache[user] = djid
                    self._name = user
                return djid
            
            cur.execute("SELECT `djid` FROM `users` WHERE `user`=%s LIMIT 1;",
                        (user,))
            if cur.rowcount > 0:
                djid = cur.fetchone()['djid']
                if djid != None:
                    self._cache[user] = djid
                    return djid
            return 0
    def s_id(self, value):
        if (not isinstance(value, (int, long, float))):
            raise TypeError("Expected integer")
        with MySQLCursor() as cur:
            cur.execute("SELECT `user` FROM `users` WHERE `djid`=%s \
            LIMIT 1;", (value,))
            if (cur.rowcount > 0):
                user = cur.fetchone()['user']
                self._cache[user] = value
                self._name = user
            else:
                raise TypeError("Invalid ID, no such DJ")
    id = property(g_id, s_id)
    def g_name(self):
        return self._name
    def s_name(self, value):
        old_name = self._name
        self._name = value
        if (self.user == None):
            self._name = old_name
            raise TypeError("Invalid name, no such DJ")
    name = property(g_name, s_name)
    @property
    def user(self):
        from re import escape, search, IGNORECASE
        name = self.name
        if (name == None):
            with MySQLCursor() as cur:
                cur.execute("SELECT `djid` FROM `streamstatus`")
                if (cur.rowcount == 0):
                    self.id = 18
                    return None
                djid = cur.fetchone()['djid']
                cur.execute("SELECT `user` FROM `users` WHERE `djid`=%s \
                LIMIT 1;", (djid,))
                if (cur.rowcount > 0):
                    user = cur.fetchone()['user']
                    self._cache[user] = djid
                    self._name = user
                    name = user
                else:
                    return None
        with open(config.djfile) as djs:
            djname = None
            for line in djs:
                temp = line.split('@')
                wildcards = temp[0].split('!')
                djname_temp = temp[1].strip()
                for wildcard in wildcards:
                    wildcard = escape(wildcard)
                    '^' + wildcard
                    wildcard = wildcard.replace('*', '.*')
                    if (search(wildcard, name, IGNORECASE)):
                        djname = djname_temp
                        break
                if (djname):
                    return unicode(djname)
        return None

class Song(object):
    def __init__(self, id=None, meta=None, length=None, filename=None):
        object.__init__(self)
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
            if (temp_filename == None) and (temp_meta == None):
                # No track with that ID sir
                raise ValueError("ID does not exist")
            if (meta == None):
                meta = temp_meta
            if (filename == None):
                filename = temp_filename
        self._filename = filename
        self._metadata = self.fix_encoding(meta)
    def update(self, **kwargs):
        """Gives you the possibility to update the
            'lp', 'id', 'length', 'filename' and 'metadata'
            variables in the Song instance
            
            Updating the 'lp' and 'length' will directly affect the database
            while 'filename', 'metadata' and 'id' don't, updating 'id' also
            updates 'filename' but not 'metadata'
            """
        if (self.metadata == u'') and (kwargs.get("metadata", u"") == u""):
            return
        for key, value in kwargs.iteritems():
            if (key in ["lp", "id", "length", "filename", "metadata"]):
                if (key == "metadata"):
                    value = self.fix_encoding(value)
                setattr(self, "_" + key, value)
                with MySQLCursor() as cur:
                    if (key == "lp"):
                        # change database entries for LP data
                        cur.execute("INSERT INTO eplay (`isong`, `dt`) \
                        VALUES(%s, FROM_UNIXTIME(%s));",
                        (self.songid, int(value)))
                        if (self.afk):
                            cur.execute("UPDATE `tracks` SET \
                            `lastplayed`=FROM_UNIXTIME(%s) \
                            WHERE `id`=%s LIMIT 1;", (self._lp, self.id))
                    elif (key == "length"):
                        # change database entries for length data
                        cur.execute("UPDATE `esong` SET `len`=%s WHERE \
                        id=%s", (self.length, self.songid))
                    elif (key == "id"):
                        self._filename, temp = self.get_file(value)
    @staticmethod
    def create_digest(metadata):
        """Creates a digest of 'metadata'"""
        from hashlib import sha1
        if (type(metadata) == unicode):
            metadata = metadata.encode('utf-8', 'replace')
        return sha1(metadata).hexdigest()
    @property
    def filename(self):
        """Filename, returns None if none found"""
        return self._filename if self._filename != None else None
    @property
    def id(self):
        """Returns the trackid, as in tracks.id"""
        return self._id if self._id != None else 0L
    @property
    def songid(self):
        """Returns the songid as in esong.id, efave.isong, eplay.isong"""
        if (not self._songid):
            self._songid = self.get_songid(self)
        return self._songid
    @property
    def metadata(self):
        """Returns metadata or an empty unicode string"""
        return self._metadata if self._metadata != None else u''
    @property
    def digest(self):
        """A sha1 digest of the metadata, can be changed by updating the
        metadata"""
        if (self._digest == None):
            self._digest = self.create_digest(self.metadata)
        return self._digest
    @property
    def length(self):
        """Returns the length from song as integer, defaults to 0"""
        if (self._length == None):
            self._length = self.get_length(self)
        return int(self._length if self._length != None else 0)
    @property
    def lengthf(self):
        """Returns the length formatted as mm:nn where mm is minutes and
        nn is seconds, defaults to 00:00. Returns an unicode string"""
        return u'%02d:%02d' % divmod(self.length, 60)
    @property
    def lp(self):
        """Returns the unixtime of when this song was last played, defaults
        to None"""
        with MySQLCursor() as cur:
            query = "SELECT unix_timestamp(`dt`) AS ut FROM eplay,esong \
            WHERE eplay.isong = esong.id AND esong.hash = '{digest}' \
            ORDER BY `dt` DESC LIMIT 1;"
            cur.execute(query.format(digest=self.digest))
            if (cur.rowcount > 0):
                return cur.fetchone()['ut']
            return None
    @property
    def lpf(self):
        """Returns a unicode string of when this song was last played,
        looks like '5 years, 3 months, 1 week, 4 days, 2 hours,
         54 minutes, 20 seconds', defaults to 'Never before'"""
        return parse_lastplayed(0 if self.lp == None else self.lp)
    @property
    def favecount(self):
        """Returns the amount of favorites on this song as integer,
        defaults to 0"""
        return len(self.faves)
    @property
    def faves(self):
        """Returns a Faves instance, list-like object that allows editing of
        the favorites of this song"""
        class Faves(object):
            def __init__(self, song):
                self.song = song
            def index(self, key):
                """Same as a normal list, very inefficient shouldn't be used"""
                return list(self).index(key)
            def count(self, key):
                """returns 1 if nick exists else 0, use "key in faves" instead
                of faves.count(key)"""
                if (key in self):
                    return 1
                return 0
            def remove(self, key):
                """Removes 'key' from the favorites"""
                self.__delitem__(key)
            def pop(self, index):
                """Not implemented"""
                raise NotImplementedError("No popping allowed")
            def insert(self, index, value):
                """Not implemented"""
                raise NotImplementedError("No inserting allowed, use append")
            def sort(self, cmp, key, reverse):
                """Not implemented"""
                raise NotImplementedError("Sorting now allowed, use reverse(faves) or list(faves)")
            def append(self, nick):
                """Add a nickname to the favorites of this song, handles
                creation of nicknames in the database. Does nothing if
                nick is already in the favorites"""
                if (nick in self):
                    return
                with MySQLCursor() as cur:
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
                """Same as 'append' but allows multiple nicknames to be added
                by suppling a list of nicknames"""
                original = list(self)
                with MySQLCursor() as cur:
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
                """Returns an iterator over the favorite list, sorted 
                alphabetical. Use list(faves) to generate a list copy of the
                nicknames"""
                with MySQLCursor() as cur:
                    cur.execute("SELECT enick.nick FROM esong JOIN efave ON \
                    efave.isong = esong.id JOIN enick ON efave.inick = \
                    enick.id WHERE esong.hash = '{digest}' ORDER BY enick.nick\
                     ASC"\
                    .format(digest=self.song.digest))
                    for result in cur:
                        yield result['nick']
            def __reversed__(self):
                """Just here for fucks, does the normal as you expect"""
                with MySQLCursor() as cur:
                    cur.execute("SELECT enick.nick FROM esong JOIN efave ON \
                    efave.isong = esong.id JOIN enick ON efave.inick = \
                    enick.id WHERE esong.hash = '{digest}' ORDER BY enick.nick\
                     DESC"\
                    .format(digest=self.song.digest))
                    for result in cur:
                        yield result['nick']
            def __len__(self):
                """len(faves) is efficient"""
                with MySQLCursor() as cur:
                    cur.execute("SELECT count(*) AS favecount FROM efave \
                    WHERE isong={songid}".format(songid=self.song.songid))
                    return cur.fetchone()['favecount']
            def __getitem__(self, key):
                return list(self)[key]
            def __setitem__(self, key, value):
                """Not implemented"""
                raise NotImplementedError("Can't set on <Faves> object")
            def __delitem__(self, key):
                original = list(self)
                if (isinstance(key, basestring)):
                    # Nick delete
                    if (key in original):
                        # It is in there
                        with MySQLCursor() as cur:
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
                        with MySQLCursor() as cur:
                            cur.execute(
                                        "DELETE efave.* FROM efave LEFt JOIN \
                                        enick ON enick.id = efave.inick WHERE \
                                        enick.nick=%s AND isong=%s;",
                                        (key, self.song.songid))
                else:
                    raise TypeError("Fave key has to be 'string' or 'int'")
            def __contains__(self, key):
                with MySQLCursor() as cur:
                    cur.execute("SELECT count(*) AS contains FROM efave JOIN\
                     enick ON enick.id = efave.inick WHERE enick.nick=%s \
                     AND efave.isong=%s;",
                     (key, self.song.songid))
                    if (cur.fetchone()['contains'] > 0):
                        return True
                    return False
            def __repr__(self):
                return (u"Favorites of %s" % repr(self.song)).encode('utf-8')
            def __str__(self):
                return self.__repr__()
        if (not self._faves):
            return Faves(self)
        return self._faves

    @property
    def playcount(self):
        """returns the playcount as long, defaults to 0L"""
        with MySQLCursor() as cur:
            query = "SELECT count(*) AS playcount FROM eplay,esong WHERE \
            eplay.isong = esong.id AND esong.hash = '{digest}';"
            cur.execute(query.format(digest=self.digest))
            if (cur.rowcount > 0):
                return cur.fetchone()['playcount']
            else:
                return 0L
    @property
    def afk(self):
        """Returns true if there is an self.id, which means there is an
        entry in the 'tracks' table for this song"""
        return False if self.id == 0L else True
    @staticmethod
    def get_length(song):
        if (song.filename != None):
            try:
                length = mutagen.File(song.filename).info.length
            except (IOError):
                logging.exception("Failed length check")
                return 0.0
            return length
        if (song.filename == None):
            # try hash
            with MySQLCursor() as cur:
                cur.execute("SELECT len FROM `esong` WHERE `hash`=%s;",
                            (song.digest,))
                if (cur.rowcount > 0):
                    return cur.fetchone()['len']
                else:
                    return 0.0
    @staticmethod
    def get_file(songid):
        """Retrieve song path and metadata from the track ID"""
        from os.path import join
        with MySQLCursor() as cur:
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
    def get_songid(song):
        with MySQLCursor() as cur:
            cur.execute("SELECT * FROM `esong` WHERE `hash`=%s LIMIT 1;",
                        (song.digest,))
            if (cur.rowcount == 1):
                return cur.fetchone()['id']
            else:
                cur.execute("INSERT INTO `esong` (`hash`, `len`, `meta`) \
                VALUES (%s, %s, %s);", (song.digest, song.length, song.metadata))
                cur.execute("SELECT * FROM `esong` WHERE `hash`=%s LIMIT 1;",
                        (song.digest,))
                return cur.fetchone()['id']
    @staticmethod
    def fix_encoding(metadata):
        try:
            try:
                return unicode(metadata, 'utf-8', 'strict').strip()
            except (UnicodeDecodeError):
                return unicode(metadata, 'shiftjis', 'replace').strip()
        except (TypeError):
            return metadata.strip()
    @classmethod
    def search(cls, query, limit=5):
        """Searches the 'tracks' table in the database, returns a list of
        Song objects. Defaults to 5 results, can be less"""
        from re import compile, escape, sub
        def replace(query):
            replacements = {r"\\": "", r"(": "",
                                         r")": "", r"*": ""}
            re = compile("|".join(escape(s) for s in \
                                  replacements))
            return re.sub(lambda x: replacements[x.group()], query)
        from os.path import join
        query_raw = query
        with MySQLCursor() as cur:
            search = replace(query)
            temp = []
            search = search.split(" ")
            for item in search:
                result = sub(r"^[+\-<>~]", "", item)
                temp.append("+" + result)
            query = " ".join(temp)
            del temp
            cur.execute("SELECT * FROM `tracks` WHERE `usable`='1' AND MATCH \
            (tags, artist, track, album) AGAINST (%s IN BOOLEAN MODE) \
            ORDER BY `priority` DESC, MATCH (tags, artist, track, \
            album) AGAINST (%s) DESC LIMIT %s;",
                    (query, query_raw, limit))
        result = []
        for row in cur:
            result.append(cls(
                              id=row['id'],
                              meta=row['track'] if row['artist'] == u'' \
                                else row['artist'] + u' - ' + row['track'],
                            filename=join(config.music_directory, row['path'])))
        return result
    @classmethod
    def nick(cls, nick, limit=5):
        with MySQLCursor() as cur:
            if (limit):
                cur.execute("SELECT len, meta FROM `esong` JOIN `efave` ON \
                esong.id = efave.isong JOIN `enick` ON efave.inick = enick.id \
                WHERE LOWER(enick.nick) = LOWER(%s) LIMIT %s;", (nick, limit))
            else:
                cur.execute("SELECT len, meta FROM `esong` JOIN `efave` ON \
                esong.id = efave.isong JOIN `enick` ON efave.inick = enick.id \
                WHERE LOWER(enick.nick) = LOWER(%s);", (nick,))
            result = []
            for row in cur:
                result.append(cls(
                              meta=row['meta'],
                              length=row['len']))
            return result
    @classmethod
    def random(cls):
        from os.path import join
        with MySQLCursor() as cur:
            cur.execute("SELECT * FROM `tracks` WHERE `usable`='1' \
                    ORDER BY RAND() LIMIT 0,1;")
            for row in cur:
                return cls(id=row['id'],
                           meta=row['track'] if row['artist'] == u'' \
                                else row['artist'] + u' - ' + row['track'],
                            filename=join(config.music_directory, row['path']))
    def __str__(self):
        return self.__repr__()
    def __repr__(self):
        return (u"<Song [%s, %d, %s] at %s>" % (self.metadata, self.id,
                                             self.digest, hex(id(self))))\
                                             .encode("utf-8")
    def __ne__(self, other):
        if (not isinstance(other, (Song, NP))):
            return False
        elif (self.digest != other.digest):
            return True
        else:
            return False
    def __eq__(self, other):
        if (not isinstance(other, (Song, NP))):
            return False
        elif (self.digest == other.digest):
            return True
        else:
            return False
    def __hash__(self):
        return hash(self.digest)
    def __getstate__(self):
        return (self.id, self.metadata, self.length, self.filename)
    def __setstate__(self, state):
        self.__init__(*state)
        
class stream(object):
    UP = True
    DOWN = False
    
    LISTENER = 0
    STATUS = 1
    STREAMER = 2
    
    streamer = listener = passing = timer = False
    def shutdown(self, force=False):
        import bootstrap
        self.passing = True
        bootstrap.controller.stop("afkstreamer", force=force)
    def down(self, reporter, status=None):
        """Called whenever a component thinks the stream is down, this can
        be a invalid call so it has to be checked where it came from"""
        import bootstrap
        if (reporter == self.STATUS):
            # Very reliable
            if (not self.passing):
                try:
                    bootstrap.controller.reload("afkstreamer")
                except:
                    pass
            else:
                def load_streamer():
                    bootstrap.controller.reload("afkstreamer")
                    self.timer = False
                    self.passing = False
                self.timer = Timer(15.0, load_streamer)
                self.timer.start()
            if (self.listener):
                # Stream down? whyi s listener on
                try:
                    bootstrap.controller.stop("listener")
                except:
                    pass
        elif (reporter == self.STREAMER):
            self.streamer = False
            bootstrap.controller.stop("afkstreamer")
        elif (reporter == self.LISTENER):
            self.listener = False
            bootstrap.controller.stop("listener")
            
    def up(self, reporter, status=None):
        """Called whenever a component thinks the stream is going up
        only called when the previous state was down"""
        import bootstrap
        if (self.timer):
            self.timer.cancel()
            self.timer = False
            self.passing = False
        if (reporter == self.STATUS):
            if (not self.streamer) and (not self.listener):
                try:
                    bootstrap.controller.reload("listener")
                except:
                    pass
        elif (reporter == self.STREAMER):
            self.streamer = True
            if (self.listener):
                # Listener is on again
                bootstrap.controller.stop("listener")
        elif (reporter == self.LISTENER):
            self.listener = True
            if (self.streamer):
                # Why is the listener on
                bootstrap.controller.stop("listener")
# declaration goes here
stream = stream()
status = status()
np = NP()
dj = dj()
queue = queue()
lp = lp()
# GENERAL TOOLS GO HERE

def get_ms(seconds):
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