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
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
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
import collections
from . import utils, tracker
# from . import dcc

from . import logger

logger = logger.getChild(__name__)

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


class ServerConnection(Connection):
    """This class represents an IRC server connection.

    ServerConnection objects are instantiated by calling the server
    method on an IRC object.
    """

    def __init__(self, irclibobj):
        Connection.__init__(self, irclibobj)
        self.tracker = tracker.IRCTracker()
        self.connected = 0  # Not connected yet.
        self.socket = None
        self.ssl = None
        self.message_queue = Queue.Queue()
        self.sent_bytes = 0
        self.send_time = 0
        self.last_time = time.time()
        self._last_ping = time.time()
        self.encoding = irclibobj.encoding
        self.featurelist = {}
        
        
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

        self.previous_buffer = b""
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
        self.featurelist = {}
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
            raise ServerConnectionError, "Couldn't connect to socket: {}".format(x)
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
        
        try:
            lines = utils._linesep_regexp.split(self.previous_buffer + new_data)
        except UnicodeDecodeError:
            logger.exception('error')

        # Save the last, unfinished line.
        self.previous_buffer = lines.pop()

        for line in lines:
            line = line.decode(self.encoding, 'replace')

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
                old_nick = utils.nm_to_n(prefix)
                if old_nick == self.real_nickname:
                    # We changed our own nick
                    self.real_nickname = arguments[0]
                self.tracker.nick(old_nick, arguments[0])
            elif command == "welcome":
                # Record the nickname in case the client changed nick
                # in a nicknameinuse callback.
                self.real_nickname = arguments[0]

            if command in ["privmsg", "notice"]:
                target, message = arguments[0], arguments[1]
                messages = utils._ctcp_dequote(message)

                if command == "privmsg":
                    if self.is_channel(target):
                        command = "pubmsg"
                else:
                    if self.is_channel(target):
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
                        
                        if command == "ctcp" and m[0] == "ACTION":
                            self._handle_event(Event("action", prefix, target, m[1:]))
                        else:
                            self._handle_event(Event(command, prefix, target, m))
                    else:
                        self._handle_event(Event(command, prefix, target, [m]))
            else:
                target = None

                if command == "quit":
                    arguments = [arguments[0]]
                    self.tracker.quit(utils.nm_to_n(prefix))
                elif command == "ping":
                    target = arguments[0]
                else:
                    target = arguments[0]
                    arguments = arguments[1:]

                if command in ["join", "part"]:
                    getattr(self.tracker, command)(target, utils.nm_to_n(prefix))
                elif command == "kick":
                    self.tracker.part(target, arguments[0])
                elif command == "topic":
                    self.tracker.topic(target, arguments[0])
                elif command == "currenttopic":
                    self.tracker.topic(arguments[0], " ".join(arguments[1:]))
                elif command == "notopic":
                    self.tracker.topic(target, "")
                elif command == "featurelist":
                    for feature in arguments:
                        split = feature.split("=")
                        if (len(split) == 2):
                            self.featurelist[split[0]] = split[1]
                        elif (len(split) == 1):
                            self.featurelist[split[0]] = ""
                elif command == "endofmotd":
                    if 'CHANMODES' in self.featurelist:
                        chanmodes = self.featurelist['CHANMODES']
                        chansplit = chanmodes.split(',')
                        self.tracker.argmodes += ''.join(chansplit[:3]) #first three groups are argmodes
                    if 'PREFIX' in self.featurelist:
                        match = re.match(r"\((.*?)\)(.*?)$", self.featurelist['PREFIX'])
                        self.tracker.nickchars = match.groups()[1]
                        self.tracker.nickmodes = match.groups()[0]
                        self.tracker.argmodes += self.tracker.nickmodes #nickmodes are also argmodes
                elif command == "namreply":
                    chan = arguments[1]
                    names = arguments[2].strip().split(' ')
                    for name in names:
                        split = 0
                        for c in name:
                            if c not in self.tracker.nickchars:
                                break
                            split += 1
                        modes = name[:split]
                        nick = name[split:]
                        self.tracker.join(chan, nick)
                        for mode in modes:
                            pos = self.tracker.nickchars.index(mode)
                            self.tracker.add_mode(chan, nick,
                                                 self.tracker.nickmodes[pos])
                if command == "mode":
                    chan = target
                    if not self.is_channel(target):
                        command = "umode"
                    modes = self._parse_modes(''.join(arguments))
                    for (sign, mode, param) in modes:
                        if mode in self.tracker.nickmodes:
                            if sign == '+':
                                self.tracker.add_mode(chan, param, mode)
                            else:
                                self.tracker.rem_mode(chan, param, mode)
                self._handle_event(Event(command, prefix, target, arguments))

    def _handle_event(self, event):
        """[Internal]"""
        self.irclibobj._handle_event(self, event)

    def is_connected(self):
        """Return connection status.

        Returns true if connected, otherwise false.
        """
        return self.connected

    def action(self, target, action):
        """Send a CTCP ACTION command."""
        self.ctcp("ACTION", target, action)

    def admin(self, server=""):
        """Send an ADMIN command."""
        self.send_raw(" ".join(["ADMIN", server]).strip())

    def ctcp(self, ctcptype, target, parameter=""):
        """Send a CTCP command."""
        ctcptype = ctcptype.upper()
        self.privmsg(target, "\001{}{}\001".format(ctcptype, parameter and (" " + parameter) or ""))

    def ctcp_reply(self, target, parameter):
        """Send a CTCP REPLY command."""
        self.notice(target, "\001{}\001".format(parameter))

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
        return self.tracker.topic(channel)
    
    def globops(self, text):
        """Send a GLOBOPS command."""
        self.send_raw("GLOBOPS :" + text)

    def hasaccess(self, channel, nick):
        """Check if nick is halfop or higher"""
        return self.tracker.has_modes(channel, nick, 'oaqh', 'or')
    
    def hasanymodes(self, channel, nick, modes):
        """Check if a nick has any of the specified modes"""
        return self.tracker.has_modes(channel, nick, modes, 'or')
    
    def inchannel(self, channel, nick):
        """Check if nick is in channel"""
        return self.tracker.in_chan(channel, nick)
        
    def info(self, server=""):
        """Send an INFO command."""
        self.send_raw(" ".join(["INFO", server]).strip())

    def invite(self, nick, channel):
        """Send an INVITE command."""
        self.send_raw(" ".join(["INVITE", nick, channel]).strip())

    def ishop(self, channel, nick):
        """Check if nick is half operator on channel"""
        return self.tracker.has_modes(channel, nick, 'h')
    
    def isnormal(self, channel, nick):
        """Check if nick is a normal on channel"""
        return not self.tracker.has_modes(channel, nick, 'oaqvh', 'or')
    
    def ison(self, nicks):
        """Send an ISON command.

        Arguments:

            nicks -- List of nicks.
        """
        self.send_raw("ISON " + " ".join(nicks))
    def isop(self, channel, nick):
        """Check if nick is operator or higher on channel"""
        return self.tracker.has_modes(channel, nick, 'oaq', 'or')

    def isvoice(self, channel, nick):
        """Check if nick is voice on channel"""
        return self.tracker.has_modes(channel, nick, 'v')
    
    def join(self, channel, key=""):
        """Send a JOIN command."""
        self.send_raw("JOIN {}{}".format(channel, (key and (" " + key))))

    def kick(self, channel, nick, comment=""):
        """Send a KICK command."""
        self.send_raw("KICK {} {}{}".format(channel, nick, (comment and (" :" + comment))))

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
        self.send_raw(u"MODE {} {}".format(target, command))

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
        self.send_raw(u"NOTICE {} :{}".format(target, text))

    def oper(self, nick, password):
        """Send an OPER command."""
        self.send_raw(u"OPER {} {}".format(nick, password))

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
        self.send_raw_instant(u"PING {}{}".format(target, target2 and (u" " + target2)))

    def pong(self, target, target2=""):
        """Send a PONG command."""
        self.send_raw_instant(u"PONG {}{}".format(target, target2 and (u" " + target2)))

    def privmsg(self, target, text):
        """Send a PRIVMSG command."""
        # Should limit len(text) here!
        self.send_raw(u"PRIVMSG {} :{}".format(target, text))

    def privmsg_many(self, targets, text):
        """Send a PRIVMSG command to multiple targets."""
        # Should limit len(text) here!
        self.send_raw(u"PRIVMSG {} :{}".format(u",".join(targets), text))

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
                logger.debug("TO SERVER:" + message)
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
        except (Queue.Full):
            # Ouch!
            self.disconnect("Queue is full.")

    def squit(self, server, comment=""):
        """Send an SQUIT command."""
        self.send_raw(u"SQUIT {}{}".format(server, comment and (u" :" + comment)))

    def stats(self, statstype, server=""):
        """Send a STATS command."""
        self.send_raw(u"STATS {}{}".format(statstype, server and (u" " + server)))

    def time(self, server=""):
        """Send a TIME command."""
        self.send_raw(u"TIME" + (server and (u" " + server)))

    def topic(self, channel, new_topic=None):
        """Send a TOPIC command."""
        if new_topic is None:
            self.send_raw(u"TOPIC " + channel)
        else:
            self.send_raw(u"TOPIC {} :{}".format(channel, new_topic))

    def trace(self, target=""):
        """Send a TRACE command."""
        self.send_raw(u"TRACE" + (target and (u" " + target)))

    def user(self, username, realname):
        """Send a USER command."""
        self.send_raw(u"USER {} 0 * :{}".format(username, realname))

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
        self.send_raw(u"WHO{}{}".format(target and (u" " + target), op and (u" o")))

    def whois(self, targets):
        """Send a WHOIS command."""
        self.send_raw(u"WHOIS " + ",".join(targets))

    def whowas(self, nick, max="", server=""):
        """Send a WHOWAS command."""
        self.send_raw(u"WHOWAS {}{}{}".format(nick,
                                         max and (u" " + max),
                                         server and (u" " + server)))
    
    def _parse_modes(self, mode_string):
        """
        This function parses a mode string based on a set of mode types.
        It returns a list of tuples like (prefix, mode, parameter), where
        prefix is either + or -, mode is a character that specifies a mode,
        and parameter is an optional parameter to the mode. If no parameter
        was specified, the value is None.
        
        The default values are taken from Rizon's ircd.
        """
        

        if 'CHANMODES' in self.featurelist:
            chanmodes = self.featurelist['CHANMODES'].split(',')
            always_param = chanmodes[0]+chanmodes[1]+self.tracker.nickmodes
            set_param = chanmodes[2]
            no_param = chanmodes[3]
        else:
            always_param = 'beIkqaohv'
            set_param = 'l'
            no_param='BCMNORScimnpstz'
        
        
        modes = []
        sign = ''
        param_index = 0;
        
        split = mode_string.split()
        if len(split) == 0:
            return []
        else:
            mode_part, args = split[0], split[1:]
        
        if mode_part[0] not in "+-":
            return []
        
        for ch in mode_part:
            if ch in "+-":
                sign = ch
            elif (ch in always_param) or (ch in set_param and sign == '+'):
                if param_index < len(args):
                    modes.append((sign, ch, args[param_index]))
                    param_index += 1
                else:
                    modes.append((sign, ch, None))
            else: # assume that any unknown mode is no_param
                modes.append((sign, ch, None))
        return modes
    def is_channel(self, string):
        """Check if a string is a channel name.
    
        Returns True if the argument is a channel name, otherwise False.
        """
        chan_prefixes = self.featurelist('CHANTYPES', None)        
        return string and string[0] in (chan_prefixes or "#&+!")



    

Event = collections.namedtuple('Event', ('eventtype', 'source',
                                         'target', 'argument'))

class Event(Event):
    """Class representing an IRC event."""
    def __init__(self, eventtype, source, target, arguments=None):
        """Constructor of Event objects.

        Arguments:

            eventtype -- A string describing the event.

            source -- The originator of the event (a nick mask or a server).

            target -- The target of the event (a nick or a channel).

            arguments -- Any event specific arguments.
        """
        arguments = arguments if arguments else []
        super(Event, self).__init__(eventtype, source, target, arguments)

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
    "307": "whoisidentified",
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
