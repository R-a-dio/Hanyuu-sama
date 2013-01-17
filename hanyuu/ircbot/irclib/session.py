"""
A high level session object to the lower level irclib.connection module.
"""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from . import logger
from . import utils
from . import connection
from . import dcc

import time
import select
import bisect
import collections
import re

logger = logger.getChild(__name__)

class Session:
    """Class that handles one or several IRC server connections.

    When a Session object has been instantiated, it can be used to create
    Connection objects that represent the IRC connections.  The
    responsibility of the Session object is to provide a high-level
    event-driven framework for the connections and to keep the connections
    alive. It runs a select loop to poll each connection's TCP socket and
    hands over the sockets with incoming data for processing by the
    corresponding connection. It then encapsulates the low level IRC
    events generated by the Connection objects into higher level
    versions.

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
        self.delayed_commands = [] # list of tuples in the format (time, function, arguments)
        self.encoding = encoding
        
    def server(self):
        """Creates and returns a ServerConnection object."""

        c = connection.ServerConnection(self)
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
            if c.send_time >= 1.3:
                c.send_time = 0
                c.sent_bytes = 0
            
            while not c.message_queue.empty():
                if c.sent_bytes <= 2500:
                    message = c.message_queue.get()
                    try:
                        if c.ssl:
                            c.send_raw_instant(message)
                        else:
                            c.send_raw_instant(message)
                    except (AttributeError):
                        c.reconnect()
                    c.sent_bytes += len(message.encode('utf-8'))
                    #if DEBUG:
                    #    print("TO SERVER:" + message)
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
            if (_difference >= 260.0):
                print("Good morning, client-side ping is here")
                connection.reconnect("Ping timeout: 260 seconds")
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
        c = dcc.DCCConnection(self, dcctype, dccinfo)
        self.connections.append(c)
        return c

    def _handle_event(self, server, event):
        """[Internal]"""
        
        # PONG any incoming PING event
        if event.eventtype == 'ping':
            self._ping_ponger(server, event)
        
        # Preparse MODE events, we want them separate in high level
        if event.eventtype in ['mode', 'umode']:
            modes = server._parse_modes(event.arguments.join(' '))
            if len(modes) > 1:
                for sign, mode, param in modes:
                    new_event = connection.Event(event.eventtype,
                                                 event.source,
                                                 event.target,
                                                 [sign+mode, param])
                    # Reraise the individual events as low level
                    self._handle_event(server, new_event)
                # If we had to preparse, end here
                return
        
        # Rebuild the low level event into a high level one
        high_event = HighEvent.from_low_event(server, event)
        
        handlers = Session.handlers
        
        for handler, events, channels, nicks, modes, regex in handlers:
            if high_event.command not in events:
                continue
            if high_event.channel not in channels:
                continue
            if high_event.nickname.name not in nicks:
                continue
            if high_event.channel and high_event.nickname and modes != '':
                # If the triggering nick does not have any of the needed modes
                if not server.hasanymodes(high_event.channel,
                                          high_event.nickname.name,
                                          modes):
                    # Don't trigger the handler
                    continue
            if high_event.message and regex:
                if not regex.match(high_event.message):
                    continue
            
            # If we get here, that means we met all the requirements for
            # triggering this handler
            try:
                handler(high_event)
            except:
                logger.exception('Exception in IRC handler')

    def _remove_connection(self, connection):
        """[Internal]"""
        self.connections.remove(connection)
        if self.fn_to_remove_socket:
            self.fn_to_remove_socket(connection._get_socket())
    
    def _ping_ponger(self, connection, event):
        """[Internal]"""
        connection._last_ping = time.time()
        connection.pong(event.target())

Session.handlers = {}

class HighEvent(object):
    """
    A abstracted event of the IRC library.
    """
    def __init__(self, server, command, nickname, channel, message):
        super(HighEvent, self).__init__()
        
        self.command = command
        self.nickname = nickname
        self.server = server
        self.channel = channel
        self.message = message
        
    @classmethod
    def from_low_event(cls, server, low_event):
        command = low_event.eventtype
        
        # We supply the source and server already to reduce code repetition.
        # Just use it as the HighEvent constructor but with partial applied.
        creator = lambda *args, **kwargs: cls(server,
                                              command,
                                              *args,
                                              **kwargs)
        
        if command == 'welcome':
            # We treat this as a "connected" event
            # The name of the server we are connected to
            server_name = low_event.source
            # Our nickname - this might be different than the one we wanted!
            nickname = Nickname(low_event.target, nickname_only=True)
            # The welcome message
            message = low_event.arguments[0]
            
            event = creator(nickname, None, message)
            event.command = 'connect'
            event.server_name = server_name
            return event
        elif command == 'nick':
            # A nickname change.
            old_nickname = Nickname(low_event.source)
            
            # We cheat here by using the original host and replacing the
            # name attribute with our new nickname.
            # TODO: Make sure this works correctly with the hostmask
            new_nickname = Nickname(low_event.source)
            new_nickname.name = low_event.arguments[0]
            
            event = creator(old_nickname, None, None)
            event.new_nickname = new_nickname
            return event
        elif command in ["pubmsg", "pubnotice"]:
            # A channel message
            nickname = Nickname(low_event.source)
            channel = low_event.target
            message = low_event.arguments[0]
            event = creator(nickname, channel, message)
            event.text_command = command
            event.command = 'text'
            return event
        elif command in ["privmsg", "privnotice"]:
            # Private message
            # The target is set to our own nickname in privmsg.
            nickname = Nickname(low_event.source)
            message = low_event.arguments[0]
            event = creator(nickname, None, message)
            event.text_command = command
            event.command = 'text'
            return event
        elif command == 'ctcp':
            # A CTCP to us.
            # Same as privmsg/notice the target is our own nickname
            nickname = Nickname(low_event.source)
            # The irclib splits off the first space delimited word for us.
            # This is the CTCP command name
            ctcp = low_event.arguments[0]
            # The things behind the command are then indexed behind it.
            message = low_event.arguments[1]
            
            event = creator(nickname, None, message)
            event.ctcp = ctcp
            return event
        elif command == 'action':
            # ACTION CTCP are parsed differently than others (for some reason)
            nickname = Nickname(low_event.source)
            # The target is present in an ACTION
            # However, this may be our nick; discard in that case
            channel = low_event.target
            # TODO: Should this follow featurelist? Is it necessary?
            if not utils.is_channel(channel):
                channel = None
            # Message is in the arguments
            message = low_event.arguments[0]
            
            event = creator(nickname, channel, message)
            return event
        elif command == 'ctcpreply':
            # A CTCP reply.
            # Same as privmsg/notice the target is our own nickname
            nickname = Nickname(low_event.source)
            # The irclib splits off the first space delimited word for us.
            # This is the CTCP command name
            ctcp = low_event.arguments[0]
            # The things behind the command are then indexed behind it.
            message = low_event.arguments[1]
            
            event = creator(nickname, None, message)
            event.ctcp = ctcp
            return event
        elif command == 'quit':
            # A quit from an user.
            nickname = Nickname(low_event.source)
            message = low_event.arguments[0]
            
            return creator(nickname, None, message)
        elif command == 'join':
            # Someone joining our channel
            nickname = Nickname(low_event.source)
            channel = low_event.target
            
            return creator(nickname, channel, None)
        elif command == 'part':
            # Someone leaving our channel
            nickname = Nickname(low_event.source)
            message = low_event.arguments[0]
            channel = low_event.target
            
            return creator(nickname, channel, message)
        elif command == 'kick':
            # Someone forcibly leaving our channel.
            # The person kicking here
            kicker = Nickname(low_event.source)
            # The person being kicked
            target = Nickname(low_event.arguments[0], nickname_only=True)
            # The reason given by the kicker
            reason = low_event.arguments[1]
            # The channel this all went wrong in!
            channel = low_event.target
            
            event = creator(target, channel, reason)
            event.kicker = kicker
            return event
        elif command == 'invite':
            # Someone has invited us to a channel.
            # The inviter
            nickname = Nickname(low_event.source)
            # Target contains our nickname
            # First argument is the channel we were invited to
            channel = low_event.arguments[0]
            return creator(nickname, channel, None)
        elif command in ['mode', 'umode']:
            # Mode change in the channel
            # The nickname that set the mode
            mode_setter = Nickname(low_event.source)
            # Simple channel
            channel = low_event.target
            
            # ServerConnection._parse_modes returns a list of tuples with
            # (operation, mode, param)
            # HOWEVER, we preparse the modes, so we (preferably) only want the
            # first one. Let's make sure we can still get all of them, though
            event = creator(mode_setter, channel, None)
            modes = server._parse_modes(low_event.arguments.join(' '))
            if len(modes) > 1:
                event.modes = modes
            else:
                event.modes = modes[0]
            return event
        elif command in ['topic', 'currenttopic', 'notopic']:
            # Any message that tells us what the topic is.
            # The channel that had its topic set.
            channel = low_event.target            
            # The person who set the topic.
            # If this isn't a topic command, there is no setter
            topic_setter = None
            if command == 'topic':
                setter = Nickname(low_event.source)            
            # The argument contains the topic string
            # Treat notopic as empty string
            topic = ''
            if not command == 'notopic':
                topic = low_event.arguments[0]
            event = creator(topic_setter, channel, topic)
            event.command = 'topic'
            return event
        elif command == 'all_raw_messages':
            # This event contains all messages, unparsed
            server_name = low_event.source
            event = creator(None, None, low_event.arguments[0])
            event.command = 'raw'
            return event
        
        # The event was not high level: thus, it's not raw, but simply unparsed
        # You will probably be able to register to these, but they won't have
        # much use
        event = creator(None, None, low_event.arguments[0])
        event.source = low_event.source
        event.target = low_event.target
        return event
    
    
class Nickname(object):
    """
    A simple class that represents a nickname on IRC.
    
    Contains information such as actual nickname, hostmask and more.
    """
    def __init__(self, host, nickname_only=False):
        """
        The constructor really just expects the raw host send by IRC servers.
        
        it parses this for you into segments.
        
        if `nickname_only` is set to True it expects a bare nickname unicode
        object to be used as nickname and nothing more.
        """
        super(Nickname, self).__init__()
        
        if nickname_only:
            self.name = host
        else:
            self.name = utils.nm_to_n(host)
            self.host = host

def event_handler(events, channels=[], nicks=[], modes='', regex=''):
    """
    The decorator for high level event handlers. By decorating a function
    with this, the function is registered in the global :class:`Session` event
    handler list, :attr:`Session.handlers`.
    
        :params events: The events that the handler should subscribe to.
                        This can be both a string and a list; if a string
                        is provided, it will be added as a single element
                        in a list of events.
                        This rule applies to `channels` and `nicks` as well.
        
        :params channels: The channels that the events should trigger on.
                          Given an empty list, all channels will trigger
                          the event.
        
        :params nicks: The nicknames that this handler should trigger for.
                       Given an empty list, all nicknames will trigger
                       the event.
        
        :params modes: The required channel modes that are needed to trigger
                       this event.
                       If an empty mode string is specified, no modes are needed
                       to trigger the event.
        
        :params regex: The event will only be triggered if the
                       :attr:`HighEvent.message` matches the specified regex.
                       If no regex is specified, any :attr:`HighEvent.message`
                       will do.
    
    
    
    
    """
    Handler = collections.namedtuple('Handler', ['handler',
                                                 'events',
                                                 'channels',
                                                 'nicks',
                                                 'modes',
                                                 'regex'])
    
    # If you think the type checking here is wrong, please fix it,
    # i have no idea what i'm doing
    if not isinstance(events, list):
        events = [events]
    if not isinstance(channels, list):
        channels = [channels]
    if not isinstance(nicks, list):
        nicks = [nicks]
    if not isinstance(modes, str) and not isinstance(modes, unicode):
        raise TypeError('invalid type for mode string: {}'.format(modes))
    if not isinstance(regex, str) and not isinstance(regex, unicode):
        raise TypeError('invalid type for regex: {}'.format(regex))
    
    for event in events:
        if not isinstance(event, str) and not isinstance(event, unicode):
            raise TypeError('invalid type for event name: {}'.format(event))
    for channel in channels:
        if not isinstance(channel, str) and not isinstance(channel, unicode):
            raise TypeError('invalid type for channel name: {}'.format(channel))
    for nick in nicks:
        if not isinstance(nick, str) and not isinstance(nick, unicode):
            raise TypeError('invalid type for nickname: {}'.format(nick))
    
    def decorator(fn):
        if regex != '':
            cregex = re.compile(regex, re.I)
        else:
            cregex = None
        handler = Handler(fn, events, channels, nicks, modes, cregex)
        Session.handlers[fn.__module__ + ":" + fn.__name__] = handler
        return fn
    return decorator
