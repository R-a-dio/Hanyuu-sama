"""
Module that contains all the classes required to track channels, nicknames
modes and other related stuff.
"""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import sqlite3


class SqliteCursor:
    """A simple Sqlite cursor."""
    def __init__(self, conn):
        """Creates an instance of the :class:`SqliteCursor`.

            :param conn: Either an :class:`IRCTracker` object or a
                          :class:`sqlite3.Connection` object. This object
                          will be used to connect to the database.
        
        It is meant to be used in a 'with' statement, like this:
        
            with SqliteCursor(my_conn) as cur:
                ... do something ...
        
        """
        if isinstance(conn, IRCTracker):
            self.__conn = conn._conn
        elif isinstance(conn, sqlite3.Connection):
            self.__conn = conn
    def __enter__(self):
        self.__cur = self.__conn.cursor()
        return self.__cur
    def __exit__(self, type, value, traceback):
        self.__cur.close()
        self.__conn.commit()
        return

class IRCTracker:
    """This class is used to track nicknames, channels, and the modes
    that are associated to nicknames on channels. It also tracks channel
    topics.
    
    This tracker uses an internal Sqlite database to store its information.    
    """
    def __init__(self):
        """Creates an instance of the IRCTracker."""
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with SqliteCursor(self) as cur:
            cur.execute("create table nicks (id integer primary key autoincrement, nick varchar(50) collate nocase);")
            cur.execute("create table channels (id integer primary key autoincrement, chan varchar(100) collate nocase, topic text);")
            cur.execute("create table nick_chan_link (id integer primary key autoincrement, nick_id integer not null constraint fk_n_c REFERENCES nicks(id), chan_id integer not null constraint fk_c_n REFERENCES channels(id), modes varchar(20));")

    def join(self, chan, nick):
        """Tells the tracker that the nickname 'nick' joined 'chan'."""
        chan_id = self.__get_chan_id(chan)
        nick_id = self.__get_nick_id(nick)
        with SqliteCursor(self) as cur:
            if not nick_id:
                cur.execute("INSERT INTO nicks (nick) VALUES (?)", (nick,))
                nick_id = self.__get_nick_id(nick)
            if not chan_id:
                cur.execute("INSERT INTO channels (chan, topic) VALUES (?, '')", (chan,))
                chan_id = self.__get_chan_id(chan)
            if not self.in_chan(chan, nick):
                cur.execute("INSERT INTO nick_chan_link (nick_id, chan_id, modes) VALUES (?, ?, '')", (nick_id, chan_id))
        pass
    
    def part(self, chan, nick):
        """Tells the tracker that the nickname 'nick' left 'chan'."""
        if self.in_chan(chan, nick):
            chan_id = self.__get_chan_id(chan)
            nick_id = self.__get_nick_id(nick)
            with SqliteCursor(self) as cur:
                cur.execute("DELETE FROM nick_chan_link WHERE nick_id=? AND chan_id=?", (nick_id, chan_id))
                
                cur.execute("SELECT * FROM nick_chan_link WHERE nick_id=?", (nick_id,))
                res = cur.fetchall()
                if len(res) == 0:
                    cur.execute("DELETE FROM nicks WHERE id=?", (nick_id,))
                cur.execute("SELECT * FROM nick_chan_link WHERE chan_id=?", (chan_id,))
                res = cur.fetchall()
                if len(res) == 0:
                    cur.execute("DELETE FROM channels WHERE id=?", (chan_id,))
    
    def quit(self, nick):
        """Tells the tracker that the nickname 'nick' has left the server."""
        if self.has_nick(nick):
            nick_id = self.__get_nick_id(nick)
            with SqliteCursor(self) as cur:
                cur.execute("SELECT chan_id FROM nick_chan_link WHERE nick_id=?", (nick_id,))
                res = cur.fetchall()
                for row in res:
                    chan_id = row[0]
                    cur.execute("SELECT chan FROM channels WHERE id=?", (chan_id,))
                    chan = cur.fetchone()[0]
                    self.part(chan, nick)
    
    def nick(self, nick, newnick):
        """Tells the tracker that the nickname 'nick' has changed to 'newnick'."""
        if self.has_nick(nick):
            nick_id = self.__get_nick_id(nick)
            with SqliteCursor(self) as cur:
                cur.execute("UPDATE nicks SET nick=? WHERE id=?", (newnick, nick_id))
    
    def add_mode(self, chan, nick, mode):
        """Sets 'mode' on 'nick' in the channel 'chan'."""
        if self.in_chan(chan, nick) and not self.has_modes(chan, nick, mode):
            chan_id = self.__get_chan_id(chan)
            nick_id = self.__get_nick_id(nick)
            with SqliteCursor(self) as cur:
                cur.execute("UPDATE nick_chan_link SET modes=modes||? WHERE nick_id=? AND chan_id=?", (mode, nick_id, chan_id))
    
    def rem_mode(self, chan, nick, mode):
        """Unsets 'mode' on 'nick' in the channel 'chan'"""
        if self.in_chan(chan, nick) and self.has_modes(chan, nick, mode):
            chan_id = self.__get_chan_id(chan)
            nick_id = self.__get_nick_id(nick)
            with SqliteCursor(self) as cur:
                cur.execute("UPDATE nick_chan_link SET modes=replace(modes, ?, '') WHERE nick_id=? AND chan_id=?", (mode, nick_id, chan_id))
    
    def topic(self, chan, topic=None):
        """If 'topic' is None, this gets the topic in the channel 'chan'.
        
        Otherwise, the topic will be set to 'topic'."""
        if self.has_chan(chan):
            if topic == None:
                with SqliteCursor(self) as cur:
                    cur.execute("SELECT topic FROM channels WHERE chan=?", (chan,))
                    return cur.fetchone()[0]
            else:
                with SqliteCursor(self) as cur:
                    cur.execute("UPDATE channels SET topic=? WHERE chan=?", (topic, chan))
                    return
        return None
    
    
    def has_nick(self, nick):
        """Returns True if the tracker is familiar with the nickname 'nick'."""
        with SqliteCursor(self) as cur:
            cur.execute("SELECT * FROM nicks WHERE nick=? LIMIT 1", (nick,))
            res = cur.fetchall()
            if len(res) == 1:
                return True
        return False

    def has_chan(self, chan):
        """Returns True if the tracker is familiar with the channel 'chan'."""
        with SqliteCursor(self) as cur:
            cur.execute("select * from channels where chan=? limit 1", (chan,))
            res = cur.fetchall()
            if len(res) == 1:
                return True
        return False 
    
    def in_chan(self, chan, nick):
        """Returns true if the nickname 'nick' is in the channel 'chan'."""
        if self.has_chan(chan) and self.has_nick(nick):
            with SqliteCursor(self) as cur:
                chan_id = self.__get_chan_id(chan)
                nick_id = self.__get_nick_id(nick)
                cur.execute("SELECT * FROM nick_chan_link WHERE nick_id=? AND chan_id=?", (nick_id, chan_id))
                res = cur.fetchall()
                if len(res) == 1:
                    return True
        return False
    
    def has_modes(self, chan, nick, modes, operator='and'):
        """Returns true if the nickname 'nick' has the modes 'modes' in the
        channel 'chan'.
        
        Based on the value of 'operator', the return value is different; if
        the operator is 'and', the nickname must have ALL of the specified
        modes. If the operator is 'or', the nickname must have ANY of the
        specified modes.
        """
        if self.in_chan(chan, nick):
            chan_id = self.__get_chan_id(chan)
            nick_id = self.__get_nick_id(nick)
            with SqliteCursor(self) as cur:
                cur.execute("SELECT modes FROM nick_chan_link WHERE nick_id=? AND chan_id=?", (nick_id, chan_id))
                nick_modes = cur.fetchone()[0]
                for mode in modes:
                    if (operator == 'and'):
                        if not mode in nick_modes:
                            return False
                    elif (operator == 'or'):
                        if mode in nick_modes:
                            return True
                return True if operator == 'and' else False
        return False
    
    def __get_nick_id(self, nick):
        """Retrieves the internal nickname ID for a nickname."""
        with SqliteCursor(self) as cur:
            cur.execute("select * from nicks where nick=? limit 1", (nick,))
            res = cur.fetchall()
            if len(res) == 1:
                return res[0][0]
        return None
    
    def __get_chan_id(self, chan):
        """Retrieves the internal channel ID for a channel."""
        with SqliteCursor(self) as cur:
            cur.execute("select * from channels where chan=? limit 1", (chan,))
            res = cur.fetchall()
            if len(res) == 1:
                return res[0][0]
        return None
    
    def execute(self, query):
        """Executes a Sqlite query and returns the results."""
        with SqliteCursor(self) as cur:
            cur.execute(query)
            return cur.fetchall()
    
    def close(self):
        """Closes the Sqlite connection."""
        self._conn.close()