from __future__ import absolute_import
import time

import mutagen

from .util import MySQLNormalCursor, MySQLCursor, unix_to_text, search
import config


class Song(object):
    def __init__(self, id=None, meta=None, length=None, filename=None):
        super(Song, self).__init__()
        if (not isinstance(id, (int, long, type(None)))):
            raise TypeError("'id' incorrect type, expected int or long")
        if (not isinstance(meta, (basestring, type(None)))):
            raise TypeError(
                "'meta' incorrect type, expected string or unicode")
        if (not isinstance(length, (int, long, float, type(None)))):
            raise TypeError("'length' incorrect type, expected int or long")
        if (not isinstance(filename, (basestring, type(None)))):
            raise TypeError(
                "'filename' incorrect type, expected string or unicode")
        self._length = length
        self._id = id
        self._digest = None
        self._lp = None
        self._songid = None
        self._faves = None
        if (meta is None) and (self.id == 0):
            raise TypeError("Require either 'id' or 'meta' argument")
        elif (self.id != 0):
            temp_filename, temp_meta = self.get_file(self.id)
            if (temp_filename is None) and (temp_meta is None):
                # No track with that ID sir
                raise ValueError("ID does not exist")
            if (meta is None):
                meta = temp_meta
            if (filename is None):
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
                            self.update_index() # update the search index for the song on the site
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
        if (isinstance(metadata, unicode)):
            metadata = metadata.encode('utf-8', 'replace').lower().strip()
        return sha1(metadata).hexdigest()

    @property
    def filename(self):
        """Filename, returns None if none found"""
        return self._filename if self._filename is not None else None

    @property
    def id(self):
        """Returns the trackid, as in tracks.id"""
        return self._id if self._id is not None else 0

    @property
    def songid(self):
        """Returns the songid as in esong.id, efave.isong, eplay.isong"""
        if (not self._songid):
            self._songid = self.get_songid(self)
        return self._songid

    @property
    def metadata(self):
        """Returns metadata or an empty unicode string"""
        return self._metadata if self._metadata is not None else u''

    @property
    def digest(self):
        """A sha1 digest of the metadata, can be changed by updating the
        metadata"""
        if (self._digest is None):
            self._digest = self.create_digest(self.metadata)
        return self._digest

    @property
    def length(self):
        """Returns the length from song as integer, defaults to 0"""
        if (self._length is None):
            self._length = self.get_length(self)
        return int(self._length if self._length is not None else 0)

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
        return unix_to_text(0 if self.lp is None else self.lp)

    @property
    def lpd(self):
        """Returns lastplayed as datetime.datetime object."""
        with MySQLCursor() as cur:
            query = "SELECT `lastplayed` FROM `tracks` WHERE id=%s;"
            cur.execute(query, (self.id,))
            for row in cur:
                return row['lastplayed']
            return None

    @property
    def lrd(self):
        """Return last requested time as datetime.datetime"""
        with MySQLCursor() as cur:
            query = "SELECT `lastrequested` FROM `tracks` WHERE id=%s;"
            cur.execute(query, (self.id,))
            for row in cur:
                return row['lastrequested']
            return None

    @property
    def lr(self):
        """Return last requested time in unix timestamp format"""
        try:
            return time.mktime(self.lrd.timetuple())
        except AttributeError:
            return None

    @property
    def lrf(self):
        """Return same format as lpf but for last requested."""
        return unix_to_text(0 if self.lr is None else self.lr)

    @property
    def delay(self):
        if self.id == 0:
            return 1000000

        with MySQLNormalCursor() as cur:
            cur.execute("SELECT requestcount FROM tracks WHERE id=%s;", (self.id,))
            for rc, in cur:
                break

        import math
        rc = min(rc, 30)

        if 0 <= rc <= 7:
            return -11057 * rc ** 2 + 172954 * rc + 81720
        return int(599955 * math.exp(0.0372 * rc) + 0.5)

    @property
    def requestable(self):
        """Returns true if the song can be requested, false otherwise."""
        if self.id == 0:
            return False  # song isn't in the db

        with MySQLNormalCursor() as cur:
            cur.execute("SELECT usable FROM tracks WHERE id=%s;", (self.id,))
            for usable, in cur:
                if usable == 0:
                    return False

        songdelay = self.delay

        now = time.time()
        if self.lp and songdelay > (now - self.lp):
            return False  # the song delay has not passed for lp
        if self.lr and songdelay > (now - self.lr):
            return False  # the song delay has not passed for lr
        return True

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

            def transfer(self, other_song):
                """Transfers faves from `self` to `other_song`"""
                other_song.faves.extend(self)
                for fave in self:
                    self.remove(fave)

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
                raise NotImplementedError(
                    "Sorting now allowed, use reverse(faves) or list(faves)")

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
                    if (self.song.id != 0):
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
                            cur.execute(
                                "INSERT INTO enick (`nick`) VALUES(%s);",
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
                        if (self.song.id != 0):
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
                     ASC"
                                .format(digest=self.song.digest))
                    for result in cur:
                        yield result['nick']

            def __reversed__(self):
                """Just here for fucks, does the normal as you expect"""
                with MySQLCursor() as cur:
                    cur.execute("SELECT enick.nick FROM esong JOIN efave ON \
                    efave.isong = esong.id JOIN enick ON efave.inick = \
                    enick.id WHERE esong.hash = '{digest}' ORDER BY enick.nick\
                     DESC"
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
                if (isinstance(key, basestring)):
                    # Nick delete
                    if (key in self):
                        # It is in there
                        with MySQLCursor() as cur:
                            cur.execute(
                                "DELETE efave.* FROM efave LEFT JOIN enick ON enick.id = efave.inick WHERE \
        enick.nick=%s AND isong=%s;", (key, self.song.songid))
                    else:
                        raise KeyError("{0}".format(key))
                else:
                    raise TypeError("Fave key has to be 'string'")

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
                return (u"Favorites of {song}".format(song=repr(self.song).decode('utf-8'))).encode('utf-8')

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
                return 0

    @property
    def afk(self):
        """Returns true if there is an self.id, which means there is an
        entry in the 'tracks' table for this song"""
        return False if self.id == 0 else True

    @staticmethod
    def get_length(song):
        if (song.filename is not None):
            try:
                length = mutagen.File(song.filename).info.length
            except (IOError):
                logging.exception("Failed length check")
                return 0.0
            return length
        if (song.filename is None):
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
            cur.execute(
                "SELECT * FROM `tracks` WHERE `id`=%s LIMIT 1;" %
                (songid))
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
                cur.execute("INSERT INTO `esong` (`hash`, `len`, `meta`, `hash_link`) \
                VALUES (%s, %s, %s, %s);", (song.digest, song.length, song.metadata, song.digest))
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

        return [cls(id=item["id"]) for item in search(query, limit)]

    @classmethod
    def nick(cls, nick, limit=5, tracks=False):
        with MySQLCursor() as cur:
            if (limit):
                cur.execute("SELECT esong.len AS len, esong.meta AS meta, \
                tracks.id AS trackid FROM tracks RIGHT JOIN esong ON tracks.hash \
                = esong.hash JOIN efave ON efave.isong = esong.id JOIN enick \
                ON efave.inick = enick.id WHERE enick.nick = %s LIMIT %s;",
                            (nick, limit))
            else:
                cur.execute("SELECT esong.len AS len, esong.meta AS meta, \
                tracks.id AS trackid FROM tracks RIGHT JOIN esong ON tracks.hash \
                = esong.hash JOIN efave ON efave.isong = esong.id JOIN enick \
                ON efave.inick = enick.id WHERE enick.nick = %s;", (nick,))
            result = []
            for row in cur:
                if (tracks and row['trackid']) or (not tracks):
                    result.append(cls(
                                  id=row['trackid'],
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
                           meta=row['track'] if row['artist'] == u''
                           else row['artist'] + u' - ' + row['track'],
                           filename=join(config.music_directory, row['path']))

    def update_index(self):
        """Updates the elasticsearch index for the song when changing it."""
        if not self.afk:
            return

        url = config.index_route.format(self.id)

        try:
            requests.get(url, auth=(config.index_user, config.index_pass))
        except:
            # all that matters is that it's pinged.
            # the response is for sanity checking.
            pass

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return (u"<Song [%s, %d, %s] at %s>" % (self.metadata, self.id,
                                                self.digest, hex(id(self))))\
            .encode("utf-8")

    def __ne__(self, other):
        from .status import NP
        if (not isinstance(other, (Song, NP))):
            return False
        elif (self.digest != other.digest):
            return True
        else:
            return False

    def __eq__(self, other):
        from .status import NP
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
