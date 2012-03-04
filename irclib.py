# Copyright (C) 1999--2002  Joel Rosdahl
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA
#
# keltus <keltus@users.sourceforge.net>
#
# $Id: irclib.py,v 1.47 2008/09/25 22:00:59 keltus Exp $
from Queue import Full

"""irclib -- Internet Relay Chat (IRC) protocol client library.

This library is intended to encapsulate the IRC protocol at a quite
low level.  It provides an event-driven IRC client framework.  It has
a fairly thorough support for the basic IRC protocol, CTCP, DCC chat,
but DCC file transfers is not yet supported.

In order to understand how to make an IRC client, I'm afraid you more
or less must understand the IRC specifications.  They are available
here: [IRC specifications].

The main features of the IRC client framework are:

  * Abstraction of the IRC protocol.
  * Handles multiple simultaneous IRC server connections.
  * Handles server PONGing transparently.
  * Messages to the IRC server are done by calling methods on an IRC
    connection object.
  * Messages from an IRC server triggers events, which can be caught
    by event handlers.
  * Reading from and writing to IRC server sockets are normally done
    by an internal select() loop, but the select()ing may be done by
    an external main loop.
  * Functions can be registered to execute at specified times by the
    event-loop.
  * Decodes CTCP tagging correctly (hopefully); I haven't seen any
    other IRC client implementation that handles the CTCP
    specification subtilties.
  * A kind of simple, single-server, object-oriented IRC client class
    that dispatches events to instance methods is included.

Current limitations:

  * The IRC protocol shines through the abstraction a bit too much.
  * Data is not written asynchronously to the server, i.e. the write()
    may block if the TCP buffers are stuffed.
  * There are no support for DCC file transfers.
  * The author haven't even read RFC 2810, 2811, 2812 and 2813.
  * Like most projects, documentation is lacking...

.. [IRC specifications] http://www.irchelp.org/irchelp/rfc/
"""

import bisect
import re
import select
import socket
import string
import sys
import time
import types
import codecs
import Queue
import sqlite3

VERSION = 0, 4, 8
DEBUG = 0

# TODO
# ----
# (maybe) thread safety
# (maybe) color parser convenience functions
# documentation (including all event types)
# (maybe) add awareness of different types of ircds
# send data asynchronously to the server (and DCC connections)
# (maybe) automatically close unused, passive DCC connections after a while

# NOTES
# -----
# connection.quit() only sends QUIT to the server.
# ERROR from the server triggers the error event and the disconnect event.
# dropping of the connection triggers the disconnect event.

class IRCError(Exception):
    """Represents an IRC exception."""
    pass


class IRC:
    """Class that handles one or several IRC server connections.

    When an IRC object has been instantiated, it can be used to create
    Connection objects that represent the IRC connections.  The
    responsibility of the IRC object is to provide an event-driven
    framework for the connections and to keep the connections alive.
    It runs a select loop to poll each connection's TCP socket and
    hands over the sockets with incoming data for processing by the
    corresponding connection.

    The methods of most interest for an IRC client writer are server,
    add_global_handler, remove_global_handler, execute_at,
    execute_delayed, process_once and process_forever.

    Here is an example:

        irc = irclib.IRC()
        server = irc.server()
        server.connect(\"irc.some.where\", 6667, \"my_nickname\")
        server.privmsg(\"a_nickname\", \"Hi there!\")
        irc.process_forever()

    This will connect to the IRC server irc.some.where on port 6667
    using the nickname my_nickname and send the message \"Hi there!\"
    to the nickname a_nickname.
    """

    def __init__(self, fn_to_add_socket=None,
                 fn_to_remove_socket=None,
                 fn_to_add_timeout=None,
                 encoding='utf-8'):
        """Constructor for IRC objects.

        Optional arguments are fn_to_add_socket, fn_to_remove_socket
        and fn_to_add_timeout.  The first two specify functions that
        will be called with a socket object as argument when the IRC
        object wants to be notified (or stop being notified) of data
        coming on a new socket.  When new data arrives, the method
        process_data should be called.  Similarly, fn_to_add_timeout
        is called with a number of seconds (a floating point number)
        as first argument when the IRC object wants to receive a
        notification (by calling the process_timeout method).  So, if
        e.g. the argument is 42.17, the object wants the
        process_timeout method to be called after 42 seconds and 170
        milliseconds.

        The three arguments mainly exist to be able to use an external
        main loop (for example Tkinter's or PyGTK's main app loop)
        instead of calling the process_forever method.

        An alternative is to just call ServerConnection.process_once()
        once in a while.
        """

        if fn_to_add_socket and fn_to_remove_socket:
            self.fn_to_add_socket = fn_to_add_socket
            self.fn_to_remove_socket = fn_to_remove_socket
        else:
            self.fn_to_add_socket = None
            self.fn_to_remove_socket = None

        self.fn_to_add_timeout = fn_to_add_timeout
        self.connections = []
        self.handlers = {}
        self.delayed_commands = [] # list of tuples in the format (time, function, arguments)
        self.encoding = encoding
        self.add_global_handler("ping", _ping_ponger, -42)
        
    def server(self):
        """Creates and returns a ServerConnection object."""

        c = ServerConnection(self)
        self.connections.append(c)
        return c

    def process_data(self, sockets):
        """Called when there is more data to read on connection sockets.

        Arguments:

            sockets -- A list of socket objects.

        See documentation for IRC.__init__.
        """
        for s in sockets:
            for c in self.connections:
                if s == c._get_socket():
                    c.process_data()

    def process_timeout(self):
        """Called when a timeout notification is due.

        See documentation for IRC.__init__.
        """
        t = time.time()
        while self.delayed_commands:
            if t >= self.delayed_commands[0][0]:
                self.delayed_commands[0][1](*self.delayed_commands[0][2])
                del self.delayed_commands[0]
            else:
                break

    def send_once(self):
        for c in self.connections:
            try:
                delta = time.time() - c.last_time
            except (AttributeError):
                continue
            c.last_time = time.time()
            c.send_time += delta
            if c.send_time >= 1.2:
                c.send_time = 0
                c.sent_lines = 0
            
            while not c.message_queue.empty():
                if c.sent_lines <= 5:
                    message = c.message_queue.get()
                    try:
                        if c.ssl:
                            c.send_raw_instant(message)
                        else:
                            c.send_raw_instant(message)
                    except (AttributeError):
                        c.reconnect()
                    c.sent_lines += 1
                    if DEBUG:
                        print "TO SERVER:", message
                else:
                    break

    def process_once(self, timeout=0):
        """Process data from connections once.

        Arguments:

            timeout -- How long the select() call should wait if no
                       data is available.

        This method should be called periodically to check and process
        incoming data, if there are any.  If that seems boring, look
        at the process_forever method.
        """
        sockets = map(lambda x: x._get_socket(), self.connections)
        sockets = filter(lambda x: x != None, sockets)
        if sockets:
            (i, o, e) = select.select(sockets, [], [], timeout)
            self.process_data(i)
        else:
            time.sleep(timeout)
        _current_time = time.time()
        for connection in self.connections:
            try:
                _difference = _current_time - connection._last_ping
            except (AttributeError):
                continue
            if (_difference >= 240.0):
                print("Good morning, client-side ping is here")
                connection.reconnect("Ping timeout: 240 seconds")
        self.send_once()
        self.process_timeout()
        
    def process_forever(self, timeout=0.2):
        """Run an infinite loop, processing data from connections.

        This method repeatedly calls process_once.

        Arguments:

            timeout -- Parameter to pass to process_once.
        """
        while 1:
            self.process_once(timeout)

    def disconnect_all(self, message=""):
        """Disconnects all connections."""
        for c in self.connections:
            c.disconnect(message)

    def add_global_handler(self, event, handler, priority=0):
        """Adds a global handler function for a specific event type.

        Arguments:

            event -- Event type (a string).  Check the values of the
            numeric_events dictionary in irclib.py for possible event
            types.

            handler -- Callback function.

            priority -- A number (the lower number, the higher priority).

        The handler function is called whenever the specified event is
        triggered in any of the connections.  See documentation for
        the Event class.

        The handler functions are called in priority order (lowest
        number is highest priority).  If a handler function returns
        \"NO MORE\", no more handlers will be called.
        """
        if not event in self.handlers:
            self.handlers[event] = []
        bisect.insort(self.handlers[event], ((priority, handler)))

    def remove_global_handler(self, event, handler):
        """Removes a global handler function.

        Arguments:

            event -- Event type (a string).

            handler -- Callback function.

        Returns 1 on success, otherwise 0.
        """
        if not event in self.handlers:
            return 0
        for h in self.handlers[event]:
            if handler == h[1]:
                self.handlers[event].remove(h)
        return 1

    def execute_at(self, at, function, arguments=()):
        """Execute a function at a specified time.

        Arguments:

            at -- Execute at this time (standard \"time_t\" time).

            function -- Function to call.

            arguments -- Arguments to give the function.
        """
        self.execute_delayed(at-time.time(), function, arguments)

    def execute_delayed(self, delay, function, arguments=()):
        """Execute a function after a specified time.

        Arguments:

            delay -- How many seconds to wait.

            function -- Function to call.

            arguments -- Arguments to give the function.
        """
        bisect.insort(self.delayed_commands, (delay+time.time(), function, arguments))
        if self.fn_to_add_timeout:
            self.fn_to_add_timeout(delay)

    def dcc(self, dcctype="chat", dccinfo=(None, None)):
        """Creates and returns a DCCConnection object.

        Arguments:

            dcctype -- "chat" for DCC CHAT connections or "raw" for
                       DCC SEND (or other DCC types). If "chat",
                       incoming data will be split in newline-separated
                       chunks. If "raw", incoming data is not touched.
        """
        c = DCCConnection(self, dcctype, dccinfo)
        self.connections.append(c)
        return c

    def _handle_event(self, connection, event):
        """[Internal]"""
        h = self.handlers
        for handler in h.get("all_events", []) + h.get(event.eventtype(), []):
            if handler[1](connection, event) == "NO MORE":
                return

    def _remove_connection(self, connection):
        """[Internal]"""
        self.connections.remove(connection)
        if self.fn_to_remove_socket:
            self.fn_to_remove_socket(connection._get_socket())

_rfc_1459_command_regexp = re.compile("^(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)( *(?P<argument> .+))?", re.UNICODE)

class Connection:
    """Base class for IRC connections.

    Must be overridden.
    """
    def __init__(self, irclibobj):
        self.irclibobj = irclibobj

    def _get_socket(self):
        raise IRCError, "Not overridden"

    ##############################
    ### Convenience wrappers.

    def execute_at(self, at, function, arguments=()):
        self.irclibobj.execute_at(at, function, arguments)

    def execute_delayed(self, delay, function, arguments=()):
        self.irclibobj.execute_delayed(delay, function, arguments)


class ServerConnectionError(IRCError):
    pass

class ServerNotConnectedError(ServerConnectionError):
    pass


# Huh!?  Crrrrazy EFNet doesn't follow the RFC: their ircd seems to
# use \n as message separator!  :P
_linesep_regexp = re.compile("\r?\n")

class ServerConnection(Connection):
    """This class represents an IRC server connection.

    ServerConnection objects are instantiated by calling the server
    method on an IRC object.
    """

    def __init__(self, irclibobj):
        Connection.__init__(self, irclibobj)
        self.sqlite = SqliteConnection()
        self.connected = 0  # Not connected yet.
        self.socket = None
        self.ssl = None
        self.message_queue = Queue.Queue()
        self.sent_lines = 0
        self.send_time = 0
        self.last_time = time.time()
        self._last_ping = time.time()
        self.encoding = irclibobj.encoding
        
    def connect(self, server, port, nickname, password=None, username=None,
                ircname=None, localaddress="", localport=0,
                ssl=False, ipv6=False, encoding='utf-8'):
        """Connect/reconnect to a server.

        Arguments:

            server -- Server name.

            port -- Port number.

            nickname -- The nickname.

            password -- Password (if any).

            username -- The username.

            ircname -- The IRC name ("realname").

            localaddress -- Bind the connection to a specific local IP address.

            localport -- Bind the connection to a specific local port.

            ssl -- Enable support for ssl.

            ipv6 -- Enable support for ipv6.

        This function can be called to reconnect a closed connection.

        Returns the ServerConnection object.
        """
        if self.connected:
            self.disconnect("Changing servers")

        self.previous_buffer = ""
        self.handlers = {}
        self.real_server_name = ""
        self.real_nickname = nickname
        self.server = server
        self.port = port
        self.nickname = nickname
        self.username = username or nickname
        self.ircname = ircname or nickname
        self.password = password
        self.localaddress = localaddress
        self.localport = localport
        self.localhost = socket.gethostname()
        self._ipv6 = ipv6
        self._ssl = ssl
        if ipv6:
            self.socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.bind((self.localaddress, self.localport))
            self.socket.connect((self.server, self.port))
            if ssl:
                self.ssl = socket.ssl(self.socket)
        except socket.error, x:
            self.socket.close()
            self.socket = None
            raise ServerConnectionError, "Couldn't connect to socket: %s" % x
        self.connected = 1
        if self.irclibobj.fn_to_add_socket:
            self.irclibobj.fn_to_add_socket(self.socket)

        # Log on...
        if self.password:
            self.pass_(self.password)
        self.nick(self.nickname)
        self.user(self.username, self.ircname)
        return self

    def close(self):
        """Close the connection.

        This method closes the connection permanently; after it has
        been called, the object is unusable.
        """

        self.disconnect("Closing object")
        self.irclibobj._remove_connection(self)

    def _get_socket(self):
        """[Internal]"""
        return self.socket

    def get_server_name(self):
        """Get the (real) server name.

        This method returns the (real) server name, or, more
        specifically, what the server calls itself.
        """

        if self.real_server_name:
            return self.real_server_name
        else:
            return ""

    def get_nickname(self):
        """Get the (real) nick name.

        This method returns the (real) nickname.  The library keeps
        track of nick changes, so it might not be the nick name that
        was passed to the connect() method.  """

        return self.real_nickname

    def process_data(self):
        """[Internal]"""

        try:
            if self.ssl:
                new_data = self.ssl.read(2**14)
            else:
                new_data = self.socket.recv(2**14)
        except socket.error, x:
            # The server hung up.
            self.disconnect("Connection reset by peer")
            return
        if not new_data:
            # Read nothing: connection must be down.
            self.disconnect("Connection reset by peer")
            return
        self._last_ping = time.time()
        lines = _linesep_regexp.split(self.previous_buffer + new_data)

        # Save the last, unfinished line.
        self.previous_buffer = lines.pop()

        for line in lines:
            line = line.decode(self.encoding, 'replace')
            if DEBUG:
                print "FROM SERVER:", line

            if not line:
                continue

            prefix = None
            command = None
            arguments = None
            self._handle_event(Event("all_raw_messages",
                                     self.get_server_name(),
                                     None,
                                     [line]))

            m = _rfc_1459_command_regexp.match(line)
            if m.group("prefix"):
                prefix = m.group("prefix")
                if not self.real_server_name:
                    self.real_server_name = prefix

            if m.group("command"):
                command = m.group("command").lower()

            if m.group("argument"):
                a = m.group("argument").split(" :", 1)
                arguments = a[0].split()
                if len(a) == 2:
                    arguments.append(a[1])

            # Translate numerics into more readable strings.
            if command in numeric_events:
                command = numeric_events[command]

            if command == "nick":
                old_nick = nm_to_n(prefix)
                if old_nick == self.real_nickname:
                    # We changed our own nick
                    self.real_nickname = arguments[0]
                self.sqlite.nick(old_nick, arguments[0])
            elif command == "welcome":
                # Record the nickname in case the client changed nick
                # in a nicknameinuse callback.
                self.real_nickname = arguments[0]

            if command in ["privmsg", "notice"]:
                target, message = arguments[0], arguments[1]
                messages = _ctcp_dequote(message)

                if command == "privmsg":
                    if is_channel(target):
                        command = "pubmsg"
                else:
                    if is_channel(target):
                        command = "pubnotice"
                    else:
                        command = "privnotice"

                for m in messages:
                    if type(m) is types.TupleType:
                        if command in ["privmsg", "pubmsg"]:
                            command = "ctcp"
                        else:
                            command = "ctcpreply"

                        m = list(m)
                        if DEBUG:
                            print "command: %s, source: %s, target: %s, arguments: %s" % (
                                command, prefix, target, m)
                        self._handle_event(Event(command, prefix, target, m))
                        if command == "ctcp" and m[0] == "ACTION":
                            self._handle_event(Event("action", prefix, target, m[1:]))
                    else:
                        if DEBUG:
                            print "command: %s, source: %s, target: %s, arguments: %s" % (
                                command, prefix, target, [m])
                        self._handle_event(Event(command, prefix, target, [m]))
            else:
                target = None

                if command == "quit":
                    arguments = [arguments[0]]
                    self.sqlite.quit(nm_to_n(prefix))
                elif command == "ping":
                    target = arguments[0]
                else:
                    target = arguments[0]
                    arguments = arguments[1:]

                if command in ["join", "part"]:
                    getattr(self.sqlite, command)(target, nm_to_n(prefix))
                elif command == "kick":
                    self.sqlite.part(target, arguments[0])
                elif command == "topic":
                    self.sqlite.topic(target, arguments[0])
                elif command == "currenttopic":
                    self.sqlite.topic(arguments[0], " ".join(arguments[1:]))
                elif command == "notopic":
                    self.sqlite.topic(target, "")
                elif command == "featurelist":
                    match = re.search(r"\sPREFIX=\((.*?)\)(.*?)\s",
                                       " ".join(arguments))
                    if (match):
                        self.sqlite.nickchars = match.groups()[1]
                        self.sqlite.nickmodes = match.groups()[0]
                        self.sqlite.argmodes += self.sqlite.nickmodes
                elif command == "namreply":
                    chan = arguments[1]
                    names = arguments[2].strip().split(' ')
                    for name in names:
                        split = 0
                        for c in name:
                            if c not in self.sqlite.nickchars:
                                break
                            split += 1
                        modes = list(name[:split])
                        nick = name[split:]
                        self.sqlite.join(chan, nick)
                        for mode in modes:
                            pos = self.sqlite.nickchars.index(mode)
                            self.sqlite.add_mode(chan, nick,
                                                 self.sqlite.nickmodes[pos])
                if command == "mode":
                    chan = target
                    if not is_channel(target):
                        command = "umode"
                    operator = arguments[0][0]
                    modes = list(arguments[0])
                    targets = arguments[1:]
                    miter = titer = 0
                    while miter < len(modes):
                        mode = modes[miter]
                        if mode in ['+', '-']: #FUCK IRC
                            operator = mode
                        if mode in self.sqlite.nickmodes:
                            nick = targets[titer]
                            if operator == '+':
                                self.sqlite.add_mode(chan, nick, mode)
                            else:
                                self.sqlite.rem_mode(chan, nick, mode)
                        if mode in self.sqlite.argmodes:
                            titer += 1
                        miter += 1
                if DEBUG:
                    print "command: %s, source: %s, target: %s, arguments: %s" % (
                        command, prefix, target, arguments)
                self._handle_event(Event(command, prefix, target, arguments))

    def _handle_event(self, event):
        """[Internal]"""
        self.irclibobj._handle_event(self, event)
        if event.eventtype() in self.handlers:
            for fn in self.handlers[event.eventtype()]:
                fn(self, event)

    def is_connected(self):
        """Return connection status.

        Returns true if connected, otherwise false.
        """
        return self.connected

    def add_global_handler(self, *args):
        """Add global handler.

        See documentation for IRC.add_global_handler.
        """
        self.irclibobj.add_global_handler(*args)

    def remove_global_handler(self, *args):
        """Remove global handler.

        See documentation for IRC.remove_global_handler.
        """
        self.irclibobj.remove_global_handler(*args)

    def action(self, target, action):
        """Send a CTCP ACTION command."""
        self.ctcp("ACTION", target, action)

    def admin(self, server=""):
        """Send an ADMIN command."""
        self.send_raw(" ".join(["ADMIN", server]).strip())

    def ctcp(self, ctcptype, target, parameter=""):
        """Send a CTCP command."""
        ctcptype = ctcptype.upper()
        self.privmsg(target, "\001%s%s\001" % (ctcptype, parameter and (" " + parameter) or ""))

    def ctcp_reply(self, target, parameter):
        """Send a CTCP REPLY command."""
        self.notice(target, "\001%s\001" % parameter)

    def disconnect(self, message=""):
        """Hang up the connection.

        Arguments:

            message -- Quit message.
        """
        if not self.connected:
            return

        self.connected = 0

        self.quit(message)

        try:
            self.socket.close()
        except socket.error, x:
            pass
        self.socket = None
        self._handle_event(Event("disconnect", self.server, "", [message]))

    def get_topic(self, channel):
        """Return the topic of channel"""
        return self.sqlite.topic(channel)
    
    def globops(self, text):
        """Send a GLOBOPS command."""
        self.send_raw("GLOBOPS :" + text)

    def hasaccess(self, channel, nick):
        """Check if nick is halfop or higher"""
        return self.sqlite.has_modes(channel, nick, 'oaqh', 'or')
    
    def inchannel(self, channel, nick):
        """Check if nick is in channel"""
        return self.sqlite.in_chan(channel, nick)
        
    def info(self, server=""):
        """Send an INFO command."""
        self.send_raw(" ".join(["INFO", server]).strip())

    def invite(self, nick, channel):
        """Send an INVITE command."""
        self.send_raw(" ".join(["INVITE", nick, channel]).strip())

    def ishop(self, channel, nick):
        """Check if nick is half operator on channel"""
        return self.sqlite.has_modes(channel, nick, 'h')
    
    def isnormal(self, channel, nick):
        """Check if nick is a normal on channel"""
        return not self.sqlite.has_modes(channel, nick, 'oaqvh', 'or')
    
    def ison(self, nicks):
        """Send an ISON command.

        Arguments:

            nicks -- List of nicks.
        """
        self.send_raw("ISON " + " ".join(nicks))
    def isop(self, channel, nick):
        """Check if nick is operator or higher on channel"""
        return self.sqlite.has_modes(channel, nick, 'oaq', 'or')

    def isvoice(self, channel, nick):
        """Check if nick is voice on channel"""
        return self.sqlite.has_modes(channel, nick, 'v')
    
    def join(self, channel, key=""):
        """Send a JOIN command."""
        self.send_raw("JOIN %s%s" % (channel, (key and (" " + key))))

    def kick(self, channel, nick, comment=""):
        """Send a KICK command."""
        self.send_raw("KICK %s %s%s" % (channel, nick, (comment and (" :" + comment))))

    def links(self, remote_server="", server_mask=""):
        """Send a LINKS command."""
        command = "LINKS"
        if remote_server:
            command = command + " " + remote_server
        if server_mask:
            command = command + " " + server_mask
        self.send_raw(command)

    def list(self, channels=None, server=""):
        """Send a LIST command."""
        command = "LIST"
        if channels:
            command = command + " " + ",".join(channels)
        if server:
            command = command + " " + server
        self.send_raw(command)

    def lusers(self, server=""):
        """Send a LUSERS command."""
        self.send_raw(u"LUSERS" + (server and (u" " + server)))

    def mode(self, target, command):
        """Send a MODE command."""
        self.send_raw(u"MODE %s %s" % (target, command))

    def motd(self, server=""):
        """Send an MOTD command."""
        self.send_raw(u"MOTD" + (server and (u" " + server)))

    def names(self, channels=None):
        """Send a NAMES command."""
        self.send_raw(u"NAMES" + (channels and (u" " + u",".join(channels)) or u""))

    def nick(self, newnick):
        """Send a NICK command."""
        self.send_raw(u"NICK " + newnick)

    def notice(self, target, text):
        """Send a NOTICE command."""
        # Should limit len(text) here!
        self.send_raw(u"NOTICE %s :%s" % (target, text))

    def oper(self, nick, password):
        """Send an OPER command."""
        self.send_raw(u"OPER %s %s" % (nick, password))

    def part(self, channels, message=""):
        """Send a PART command."""
        if type(channels) == types.StringType:
            self.send_raw(u"PART " + channels + (message and (u" " + message)))
        else:
            self.send_raw(u"PART " + u",".join(channels) + (message and (u" " + message)))

    def pass_(self, password):
        """Send a PASS command."""
        self.send_raw(u"PASS " + password)

    def ping(self, target, target2=""):
        """Send a PING command."""
        self.send_raw_instant(u"PING %s%s" % (target, target2 and (u" " + target2)))

    def pong(self, target, target2=""):
        """Send a PONG command."""
        self.send_raw_instant(u"PONG %s%s" % (target, target2 and (u" " + target2)))

    def privmsg(self, target, text):
        """Send a PRIVMSG command."""
        # Should limit len(text) here!
        self.send_raw(u"PRIVMSG %s :%s" % (target, text))

    def privmsg_many(self, targets, text):
        """Send a PRIVMSG command to multiple targets."""
        # Should limit len(text) here!
        self.send_raw(u"PRIVMSG %s :%s" % (u",".join(targets), text))

    def quit(self, message=""):
        """Send a QUIT command."""
        # Note that many IRC servers don't use your QUIT message
        # unless you've been connected for at least 5 minutes!
        self.send_raw_instant(u"QUIT" + (message and (u" :" + message)))

    def reconnect(self, message=""):
        """Disconnect and connect with same parameters"""
        self.disconnect(message)
        self.connect(self.server, self.port, self.nickname, self.password,
                    self.username, self.ircname, self.localaddress,
                    self.localport, self._ssl, self._ipv6)
    def send_raw_instant(self, string):
        """Send raw string bypassing the flood protection"""
        if self.socket is None:
            raise ServerNotConnectedError, "Not connected."
        try:
            message = string + u'\r\n'
            if (type(message) == unicode):
                message = message.encode(self.encoding)
            if self.ssl:
                self.ssl.write(message)
            else:
                self.socket.sendall(message)
            if DEBUG:
                print "TO SERVER:", message
        except socket.error, x:
            self.disconnect("Connection reset by peer.")
    def send_raw(self, string):
        """Send raw string to the server.

        The string will be padded with appropriate CR LF.
        """
        if self.socket is None:
            raise ServerNotConnectedError, "Not connected."
        try:
            self.message_queue.put(string)
        except (Full):
            # Ouch!
            self.disconnect("Queue is full.")

    def squit(self, server, comment=""):
        """Send an SQUIT command."""
        self.send_raw(u"SQUIT %s%s" % (server, comment and (u" :" + comment)))

    def stats(self, statstype, server=""):
        """Send a STATS command."""
        self.send_raw(u"STATS %s%s" % (statstype, server and (u" " + server)))

    def time(self, server=""):
        """Send a TIME command."""
        self.send_raw(u"TIME" + (server and (u" " + server)))

    def topic(self, channel, new_topic=None):
        """Send a TOPIC command."""
        if new_topic is None:
            self.send_raw(u"TOPIC " + channel)
        else:
            self.send_raw(u"TOPIC %s :%s" % (channel, new_topic))

    def trace(self, target=""):
        """Send a TRACE command."""
        self.send_raw(u"TRACE" + (target and (u" " + target)))

    def user(self, username, realname):
        """Send a USER command."""
        self.send_raw(u"USER %s 0 * :%s" % (username, realname))

    def userhost(self, nicks):
        """Send a USERHOST command."""
        self.send_raw(u"USERHOST " + ",".join(nicks))

    def users(self, server=""):
        """Send a USERS command."""
        self.send_raw(u"USERS" + (server and (u" " + server)))

    def version(self, server=""):
        """Send a VERSION command."""
        self.send_raw(u"VERSION" + (server and (u" " + server)))

    def wallops(self, text):
        """Send a WALLOPS command."""
        self.send_raw(u"WALLOPS :" + text)

    def who(self, target="", op=""):
        """Send a WHO command."""
        self.send_raw(u"WHO%s%s" % (target and (u" " + target), op and (u" o")))

    def whois(self, targets):
        """Send a WHOIS command."""
        self.send_raw(u"WHOIS " + ",".join(targets))

    def whowas(self, nick, max="", server=""):
        """Send a WHOWAS command."""
        self.send_raw(u"WHOWAS %s%s%s" % (nick,
                                         max and (u" " + max),
                                         server and (u" " + server)))

class SqliteCursor:
    def __init__(self, conn):
        if isinstance(conn, SqliteConnection):
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

class SqliteConnection:
    def __init__(self):
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with SqliteCursor(self) as cur:
            cur.execute("create table nicks (id integer primary key autoincrement, nick varchar(50) collate nocase);")
            cur.execute("create table channels (id integer primary key autoincrement, chan varchar(100) collate nocase, topic text);")
            cur.execute("create table nick_chan_link (id integer primary key autoincrement, nick_id integer not null constraint fk_n_c REFERENCES nicks(id), chan_id integer not null constraint fk_c_n REFERENCES channels(id), modes varchar(20));")
            
            #cur.execute("insert into nicks (nick, lastrequested) values ('Vin', datetime('now'))")
            #cur.execute("insert into nicks (nick, lastrequested) values ('Wessie', datetime('now'))")
            #cur.execute("insert into channels (chan, topic) values ('#r/a/dio', 'radio topic')")
            #cur.execute("insert into nick_chan_link (nick_id, chan_id, modes) values (1, 1, 'ov')")
        self.nickmodes = ''
        self.nickchars = ''
        self.argmodes = 'bkle' #lol i'm lazy. just assuming that bkl are all argument modes

    def join(self, chan, nick):
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
        if self.has_nick(nick):
            nick_id = self.__get_nick_id(nick)
            with SqliteCursor(self) as cur:
                cur.execute("UPDATE nicks SET nick=? WHERE id=?", (newnick, nick_id))
    
    def add_mode(self, chan, nick, mode):
        if self.in_chan(chan, nick) and not self.has_modes(chan, nick, mode):
            chan_id = self.__get_chan_id(chan)
            nick_id = self.__get_nick_id(nick)
            with SqliteCursor(self) as cur:
                cur.execute("UPDATE nick_chan_link SET modes=modes||? WHERE nick_id=? AND chan_id=?", (mode, nick_id, chan_id))
    
    def rem_mode(self, chan, nick, mode):
        if self.in_chan(chan, nick) and self.has_modes(chan, nick, mode):
            chan_id = self.__get_chan_id(chan)
            nick_id = self.__get_nick_id(nick)
            with SqliteCursor(self) as cur:
                cur.execute("UPDATE nick_chan_link SET modes=replace(modes, ?, '') WHERE nick_id=? AND chan_id=?", (mode, nick_id, chan_id))
    
    def topic(self, chan, topic=None):
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
        with SqliteCursor(self) as cur:
            cur.execute("SELECT * FROM nicks WHERE nick=? LIMIT 1", (nick,))
            res = cur.fetchall()
            if len(res) == 1:
                return True
        return False

    def has_chan(self, chan):
        with SqliteCursor(self) as cur:
            cur.execute("select * from channels where chan=? limit 1", (chan,))
            res = cur.fetchall()
            if len(res) == 1:
                return True
        return False 
    
    def in_chan(self, chan, nick):
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
        with SqliteCursor(self) as cur:
            cur.execute("select * from nicks where nick=? limit 1", (nick,))
            res = cur.fetchall()
            if len(res) == 1:
                return res[0][0]
        return None
    
    def __get_chan_id(self, chan):
        with SqliteCursor(self) as cur:
            cur.execute("select * from channels where chan=? limit 1", (chan,))
            res = cur.fetchall()
            if len(res) == 1:
                return res[0][0]
            return None
    
    def execute(self, query):
        with SqliteCursor(self) as cur:
            cur.execute(query)
            return cur.fetchall()
    
    def close(self):
        self._conn.close()
    
class DCCConnectionError(IRCError):
    pass


class DCCConnection(Connection):
    """This class represents a DCC connection.

    DCCConnection objects are instantiated by calling the dcc
    method on an IRC object.
    """
    def __init__(self, irclibobj, dcctype, dccinfo=(None, None)):
        Connection.__init__(self, irclibobj)
        self.connected = 0
        self.passive = 0
        self.dcctype = dcctype
        self.dccfile = dccinfo[0]
        self.total = long(dccinfo[1])
        self.peeraddress = None
        self.peerport = None

    def connect(self, address, port):
        """Connect/reconnect to a DCC peer.

        Arguments:
            address -- Host/IP address of the peer.

            port -- The port number to connect to.

        Returns the DCCConnection object.
        """
        if (self.dcctype == "send"):
            self.fileobj = open(self.dccfile, "wb")
            self.current = 0
        self.peeraddress = socket.gethostbyname(address)
        self.peerport = port
        self.socket = None
        self.previous_buffer = ""
        self.handlers = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.passive = 0
        try:
            self.socket.connect((self.peeraddress, self.peerport))
        except socket.error, x:
            raise DCCConnectionError, "Couldn't connect to socket: %s" % x
        self.connected = 1
        if self.irclibobj.fn_to_add_socket:
            self.irclibobj.fn_to_add_socket(self.socket)
        return self

    def listen(self):
        """Wait for a connection/reconnection from a DCC peer.

        Returns the DCCConnection object.

        The local IP address and port are available as
        self.localaddress and self.localport.  After connection from a
        peer, the peer address and port are available as
        self.peeraddress and self.peerport.
        """
        self.previous_buffer = ""
        self.handlers = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.passive = 1
        try:
            self.socket.bind((socket.gethostbyname(socket.gethostname()), 0))
            self.localaddress, self.localport = self.socket.getsockname()
            self.socket.listen(10)
        except socket.error, x:
            raise DCCConnectionError, "Couldn't bind socket: %s" % x
        return self

    def disconnect(self, message=""):
        """Hang up the connection and close the object.

        Arguments:

            message -- Quit message.
        """
        if not self.connected:
            return

        self.connected = 0
        try:
            self.socket.close()
        except socket.error, x:
            pass
        self.socket = None
        self.irclibobj._handle_event(
            self,
            Event("dcc_disconnect", self.peeraddress, "", [message]))
        self.irclibobj._remove_connection(self)

    def process_data(self):
        """[Internal]"""

        if self.passive and not self.connected:
            conn, (self.peeraddress, self.peerport) = self.socket.accept()
            self.socket.close()
            self.socket = conn
            self.connected = 1
            if DEBUG:
                print "DCC connection from %s:%d" % (
                    self.peeraddress, self.peerport)
            self.irclibobj._handle_event(
                self,
                Event("dcc_connect", self.peeraddress, None, None))
            return

        try:
            new_data = self.socket.recv(2**14)
        except socket.error, x:
            # The server hung up.
            self.disconnect("Connection reset by peer")
            return
        if not new_data:
            # Read nothing: connection must be down.
            self.disconnect("Connection reset by peer")
            return

        if self.dcctype == "chat":
            # The specification says lines are terminated with LF, but
            # it seems safer to handle CR LF terminations too.
            chunks = _linesep_regexp.split(self.previous_buffer + new_data)

            # Save the last, unfinished line.
            self.previous_buffer = chunks[-1]
            if len(self.previous_buffer) > 2**14:
                # Bad peer! Naughty peer!
                self.disconnect()
                return
            chunks = chunks[:-1]
        elif self.dcctype == "send":
            # We are going to sidestep the events a bit
            size = len(new_data)
            self.current += size
            try:
                self.fileobj.write(new_data)
            except (AttributeError):
                self.disconnect("Invalid file object")
            except (IOError):
                self.disconnect("Invalid file object")
            chunks = ["send"]
        else:
            chunks = [new_data]

        command = "dccmsg"
        prefix = self.peeraddress
        target = None
        for chunk in chunks:
            if DEBUG:
                print "FROM PEER:", chunk
            arguments = [chunk]
            if DEBUG:
                print "command: %s, source: %s, target: %s, arguments: %s" % (
                    command, prefix, target, arguments)
            self.irclibobj._handle_event(
                self,
                Event(command, prefix, target, arguments))

    def _get_socket(self):
        """[Internal]"""
        return self.socket

    def privmsg(self, string):
        """Send data to DCC peer.

        The string will be padded with appropriate LF if it's a DCC
        CHAT session.
        """
        try:
            self.socket.send(string)
            if self.dcctype == "chat":
                self.socket.send("\n")
            if DEBUG:
                print "TO PEER: %s\n" % string
        except socket.error, x:
            # Ouch!
            self.disconnect("Connection reset by peer.")

class SimpleIRCClient:
    """A simple single-server IRC client class.

    This is an example of an object-oriented wrapper of the IRC
    framework.  A real IRC client can be made by subclassing this
    class and adding appropriate methods.

    The method on_join will be called when a "join" event is created
    (which is done when the server sends a JOIN messsage/command),
    on_privmsg will be called for "privmsg" events, and so on.  The
    handler methods get two arguments: the connection object (same as
    self.connection) and the event object.

    Instance attributes that can be used by sub classes:

        ircobj -- The IRC instance.

        connection -- The ServerConnection instance.

        dcc_connections -- A list of DCCConnection instances.
    """
    def __init__(self):
        self.ircobj = IRC()
        self.connection = self.ircobj.server()
        self.dcc_connections = []
        self.ircobj.add_global_handler("all_events", self._dispatcher, -10)
        self.ircobj.add_global_handler("dcc_disconnect", self._dcc_disconnect, -10)

    def _dispatcher(self, c, e):
        """[Internal]"""
        m = "on_" + e.eventtype()
        if hasattr(self, m):
            getattr(self, m)(c, e)

    def _dcc_disconnect(self, c, e):
        self.dcc_connections.remove(c)

    def connect(self, server, port, nickname, password=None, username=None,
                ircname=None, localaddress="", localport=0, ssl=False, ipv6=False):
        """Connect/reconnect to a server.

        Arguments:

            server -- Server name.

            port -- Port number.

            nickname -- The nickname.

            password -- Password (if any).

            username -- The username.

            ircname -- The IRC name.

            localaddress -- Bind the connection to a specific local IP address.

            localport -- Bind the connection to a specific local port.

            ssl -- Enable support for ssl.

            ipv6 -- Enable support for ipv6.

        This function can be called to reconnect a closed connection.
        """
        self.connection.connect(server, port, nickname,
                                password, username, ircname,
                                localaddress, localport, ssl, ipv6)

    def dcc_connect(self, address, port, dcctype="chat"):
        """Connect to a DCC peer.

        Arguments:

            address -- IP address of the peer.

            port -- Port to connect to.

        Returns a DCCConnection instance.
        """
        dcc = self.ircobj.dcc(dcctype)
        self.dcc_connections.append(dcc)
        dcc.connect(address, port)
        return dcc

    def dcc_listen(self, dcctype="chat"):
        """Listen for connections from a DCC peer.

        Returns a DCCConnection instance.
        """
        dcc = self.ircobj.dcc(dcctype)
        self.dcc_connections.append(dcc)
        dcc.listen()
        return dcc

    def start(self):
        """Start the IRC client."""
        self.ircobj.process_forever()


class Event:
    """Class representing an IRC event."""
    def __init__(self, eventtype, source, target, arguments=None):
        """Constructor of Event objects.

        Arguments:

            eventtype -- A string describing the event.

            source -- The originator of the event (a nick mask or a server).

            target -- The target of the event (a nick or a channel).

            arguments -- Any event specific arguments.
        """
        self._eventtype = eventtype
        self._source = source
        self._target = target
        if arguments:
            self._arguments = arguments
        else:
            self._arguments = []

    def eventtype(self):
        """Get the event type."""
        return self._eventtype

    def source(self):
        """Get the event source."""
        return self._source

    def target(self):
        """Get the event target."""
        return self._target

    def arguments(self):
        """Get the event arguments."""
        return self._arguments

_LOW_LEVEL_QUOTE = "\020"
_CTCP_LEVEL_QUOTE = "\134"
_CTCP_DELIMITER = "\001"

_low_level_mapping = {
    "0": "\000",
    "n": "\n",
    "r": "\r",
    _LOW_LEVEL_QUOTE: _LOW_LEVEL_QUOTE
}

_low_level_regexp = re.compile(_LOW_LEVEL_QUOTE + "(.)", re.UNICODE)

def mask_matches(nick, mask):
    """Check if a nick matches a mask.

    Returns true if the nick matches, otherwise false.
    """
    nick = irc_lower(nick)
    mask = irc_lower(mask)
    mask = mask.replace("\\", "\\\\")
    for ch in ".$|[](){}+":
        mask = mask.replace(ch, "\\" + ch)
    mask = mask.replace("?", ".")
    mask = mask.replace("*", ".*")
    r = re.compile(mask, re.IGNORECASE)
    return r.match(nick)

_special = "-[]\\`^{}"
nick_characters = string.ascii_letters + string.digits + _special
_ircstring_translation = string.maketrans(string.ascii_uppercase + "[]\\^",
                                        string.ascii_lowercase + "{}|~")

def irc_lower(s):
    """Returns a lowercased string.

    The definition of lowercased comes from the IRC specification (RFC
    1459).
    """
    if (type(s) == unicode):
        s = s.encode('utf-8')
    return s.translate(_ircstring_translation)

def _ctcp_dequote(message):
    """[Internal] Dequote a message according to CTCP specifications.

    The function returns a list where each element can be either a
    string (normal message) or a tuple of one or two strings (tagged
    messages).  If a tuple has only one element (ie is a singleton),
    that element is the tag; otherwise the tuple has two elements: the
    tag and the data.

    Arguments:

        message -- The message to be decoded.
    """

    def _low_level_replace(match_obj):
        ch = match_obj.group(1)

        # If low_level_mapping doesn't have the character as key, we
        # should just return the character.
        return _low_level_mapping.get(ch, ch)

    if _LOW_LEVEL_QUOTE in message:
        # Yup, there was a quote.  Release the dequoter, man!
        message = _low_level_regexp.sub(_low_level_replace, message)

    if _CTCP_DELIMITER not in message:
        return [message]
    else:
        # Split it into parts.  (Does any IRC client actually *use*
        # CTCP stacking like this?)
        chunks = message.split(_CTCP_DELIMITER)

        messages = []
        i = 0
        while i < len(chunks)-1:
            # Add message if it's non-empty.
            if len(chunks[i]) > 0:
                messages.append(chunks[i])

            if i < len(chunks)-2:
                # Aye!  CTCP tagged data ahead!
                messages.append(tuple(chunks[i+1].split(" ", 1)))

            i = i + 2

        if len(chunks) % 2 == 0:
            # Hey, a lonely _CTCP_DELIMITER at the end!  This means
            # that the last chunk, including the delimiter, is a
            # normal message!  (This is according to the CTCP
            # specification.)
            messages.append(_CTCP_DELIMITER + chunks[-1])

        return messages

def is_channel(string):
    """Check if a string is a channel name.

    Returns true if the argument is a channel name, otherwise false.
    """
    return string and string[0] in "#&+!"

def ip_numstr_to_quad(num):
    """Convert an IP number as an integer given in ASCII
    representation (e.g. '3232235521') to an IP address string
    (e.g. '192.168.0.1')."""
    n = long(num)
    p = map(str, map(int, [n >> 24 & 0xFF, n >> 16 & 0xFF,
                           n >> 8 & 0xFF, n & 0xFF]))
    return ".".join(p)

def ip_quad_to_numstr(quad):
    """Convert an IP address string (e.g. '192.168.0.1') to an IP
    number as an integer given in ASCII representation
    (e.g. '3232235521')."""
    p = map(long, quad.split("."))
    s = str((p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3])
    if s[-1] == "L":
        s = s[:-1]
    return s

def nm_to_n(s):
    """Get the nick part of a nickmask.

    (The source of an Event is a nickmask.)
    """
    return s.split("!")[0]

def nm_to_uh(s):
    """Get the userhost part of a nickmask.

    (The source of an Event is a nickmask.)
    """
    return s.split("!")[1]

def nm_to_h(s):
    """Get the host part of a nickmask.

    (The source of an Event is a nickmask.)
    """
    return s.split("@")[1]

def nm_to_u(s):
    """Get the user part of a nickmask.

    (The source of an Event is a nickmask.)
    """
    s = s.split("!")[1]
    return s.split("@")[0]

def parse_nick_modes(mode_string):
    """Parse a nick mode string.

    The function returns a list of lists with three members: sign,
    mode and argument.  The sign is \"+\" or \"-\".  The argument is
    always None.

    Example:

    >>> irclib.parse_nick_modes(\"+ab-c\")
    [['+', 'a', None], ['+', 'b', None], ['-', 'c', None]]
    """

    return _parse_modes(mode_string, "")

def parse_channel_modes(mode_string):
    """Parse a channel mode string.

    The function returns a list of lists with three members: sign,
    mode and argument.  The sign is \"+\" or \"-\".  The argument is
    None if mode isn't one of \"b\", \"k\", \"l\", \"v\" or \"o\".

    Example:

    >>> irclib.parse_channel_modes(\"+ab-c foo\")
    [['+', 'a', None], ['+', 'b', 'foo'], ['-', 'c', None]]
    """

    return _parse_modes(mode_string, "bklvo")

def _parse_modes(mode_string, unary_modes=""):
    """[Internal]"""
    modes = []
    arg_count = 0

    # State variable.
    sign = ""

    a = mode_string.split()
    if len(a) == 0:
        return []
    else:
        mode_part, args = a[0], a[1:]

    if mode_part[0] not in "+-":
        return []
    for ch in mode_part:
        if ch in "+-":
            sign = ch
        elif ch == " ":
            collecting_arguments = 1
        elif ch in unary_modes:
            if len(args) >= arg_count + 1:
                modes.append([sign, ch, args[arg_count]])
                arg_count = arg_count + 1
            else:
                modes.append([sign, ch, None])
        else:
            modes.append([sign, ch, None])
    return modes

def _ping_ponger(connection, event):
    """[Internal]"""
    connection._last_ping = time.time()
    connection.pong(event.target())

# Numeric table mostly stolen from the Perl IRC module (Net::IRC).
numeric_events = {
    "001": "welcome",
    "002": "yourhost",
    "003": "created",
    "004": "myinfo",
    "005": "featurelist",  # XXX
    "200": "tracelink",
    "201": "traceconnecting",
    "202": "tracehandshake",
    "203": "traceunknown",
    "204": "traceoperator",
    "205": "traceuser",
    "206": "traceserver",
    "207": "traceservice",
    "208": "tracenewtype",
    "209": "traceclass",
    "210": "tracereconnect",
    "211": "statslinkinfo",
    "212": "statscommands",
    "213": "statscline",
    "214": "statsnline",
    "215": "statsiline",
    "216": "statskline",
    "217": "statsqline",
    "218": "statsyline",
    "219": "endofstats",
    "221": "umodeis",
    "231": "serviceinfo",
    "232": "endofservices",
    "233": "service",
    "234": "servlist",
    "235": "servlistend",
    "241": "statslline",
    "242": "statsuptime",
    "243": "statsoline",
    "244": "statshline",
    "250": "luserconns",
    "251": "luserclient",
    "252": "luserop",
    "253": "luserunknown",
    "254": "luserchannels",
    "255": "luserme",
    "256": "adminme",
    "257": "adminloc1",
    "258": "adminloc2",
    "259": "adminemail",
    "261": "tracelog",
    "262": "endoftrace",
    "263": "tryagain",
    "265": "n_local",
    "266": "n_global",
    "300": "none",
    "301": "away",
    "302": "userhost",
    "303": "ison",
    "305": "unaway",
    "306": "nowaway",
    "311": "whoisuser",
    "312": "whoisserver",
    "313": "whoisoperator",
    "314": "whowasuser",
    "315": "endofwho",
    "316": "whoischanop",
    "317": "whoisidle",
    "318": "endofwhois",
    "319": "whoischannels",
    "321": "liststart",
    "322": "list",
    "323": "listend",
    "324": "channelmodeis",
    "329": "channelcreate",
    "331": "notopic",
    "332": "currenttopic",
    "333": "topicinfo",
    "341": "inviting",
    "342": "summoning",
    "346": "invitelist",
    "347": "endofinvitelist",
    "348": "exceptlist",
    "349": "endofexceptlist",
    "351": "version",
    "352": "whoreply",
    "353": "namreply",
    "361": "killdone",
    "362": "closing",
    "363": "closeend",
    "364": "links",
    "365": "endoflinks",
    "366": "endofnames",
    "367": "banlist",
    "368": "endofbanlist",
    "369": "endofwhowas",
    "371": "info",
    "372": "motd",
    "373": "infostart",
    "374": "endofinfo",
    "375": "motdstart",
    "376": "endofmotd",
    "377": "motd2",        # 1997-10-16 -- tkil
    "381": "youreoper",
    "382": "rehashing",
    "384": "myportis",
    "391": "time",
    "392": "usersstart",
    "393": "users",
    "394": "endofusers",
    "395": "nousers",
    "401": "nosuchnick",
    "402": "nosuchserver",
    "403": "nosuchchannel",
    "404": "cannotsendtochan",
    "405": "toomanychannels",
    "406": "wasnosuchnick",
    "407": "toomanytargets",
    "409": "noorigin",
    "411": "norecipient",
    "412": "notexttosend",
    "413": "notoplevel",
    "414": "wildtoplevel",
    "421": "unknowncommand",
    "422": "nomotd",
    "423": "noadmininfo",
    "424": "fileerror",
    "431": "nonicknamegiven",
    "432": "erroneusnickname", # Thiss iz how its speld in thee RFC.
    "433": "nicknameinuse",
    "436": "nickcollision",
    "437": "unavailresource",  # "Nick temporally unavailable"
    "441": "usernotinchannel",
    "442": "notonchannel",
    "443": "useronchannel",
    "444": "nologin",
    "445": "summondisabled",
    "446": "usersdisabled",
    "451": "notregistered",
    "461": "needmoreparams",
    "462": "alreadyregistered",
    "463": "nopermforhost",
    "464": "passwdmismatch",
    "465": "yourebannedcreep", # I love this one...
    "466": "youwillbebanned",
    "467": "keyset",
    "471": "channelisfull",
    "472": "unknownmode",
    "473": "inviteonlychan",
    "474": "bannedfromchan",
    "475": "badchannelkey",
    "476": "badchanmask",
    "477": "nochanmodes",  # "Channel doesn't support modes"
    "478": "banlistfull",
    "481": "noprivileges",
    "482": "chanoprivsneeded",
    "483": "cantkillserver",
    "484": "restricted",   # Connection is restricted
    "485": "uniqopprivsneeded",
    "491": "nooperhost",
    "492": "noservicehost",
    "501": "umodeunknownflag",
    "502": "usersdontmatch",
}

generated_events = [
    # Generated events
    "dcc_connect",
    "dcc_disconnect",
    "dccmsg",
    "disconnect",
    "ctcp",
    "ctcpreply",
]

protocol_events = [
    # IRC protocol events
    "error",
    "join",
    "kick",
    "mode",
    "part",
    "ping",
    "privmsg",
    "privnotice",
    "pubmsg",
    "pubnotice",
    "quit",
    "invite",
    "pong",
    "topic",
    "nick"
]

all_events = generated_events + protocol_events + numeric_events.values()
