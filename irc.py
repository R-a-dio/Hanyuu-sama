from threading import Thread
import logging
import config
import time
import re
import irclib

# Handler constants
# Channels
ALL_CHANNELS = 0
MAIN_CHANNELS = ["#r/a/dio"]
# Nicks
ALL_NICKS = 0 # All nicknames can trigger this
ACCESS_NICKS = 1 # Nicks with halfop or higher can trigger this
OP_NICKS = 2 # Only operators or higher can trigger this
HALFOP_NICKS = 3 # Only half operators can trigger this
VOICE_NICKS = 4 # Only voiced people can trigger this
REGULAR_NICKS = 5 # Only regulars can trigger this
DEV_NICKS = 6 # Only the nicknames defined in config.irc_devs can trigger this

def start():
    global session
    session = Session()
    return session

def proxy():
    return Proxy(session)

def shutdown():
    session.shutdown()

class Session(object):
    def __init__(self):
        logging.info("Creating IRC Session")
        self.ready = False
        self.commands = None
        self._handlers = []
        self.irc = irclib.IRC()
        self.load_handlers()
        self.irc.add_global_handler("all_events", self._dispatcher)
        
        # initialize our process thread
        self.processor_thread = Thread(target=self.processor)
        self.processor_thread.daemon = 1
        self.processor_thread.start()
    def processor(self):
        # Our shiny thread that processes the socket
        while (self._active):
            # Call the process once
            self.irc.process_once(timeout=1)
    def connect(self):
        # We really only need one server
        self.server = self.irc.server()
        self.server.connect(config.irc_server,
                            config.irc_port,
                            config.irc_name)
    def shutdown(self):
        self._active = False
        self.irc.disconnect_all("Leaving...")
    def load_handlers(self, load=False):
        if (load) and (self.commands != None):
            try:
                commands = reload(self.commands)
            except (ImportError):
                # Report this to caller
                raise
        else:
            commands = __import__("hanyuu_commands")
        from types import FunctionType
        for name in dir(commands):
            func = getattr(commands, name)
            if (type(func) == FunctionType):
                try:
                    handler = getattr(func, "handler")
                except (AttributeError):
                    # no handler
                    pass
                else:
                    event, regex, nicks, channels = handler
                    cregex = re.compile(regex)
                    # tuple is:
                    # (Compiled regex, function, event type, allowed nicks,
                    # allowed channels, plain-text regex)
                    self._handlers.append(
                                          (
                                           cregex,
                                           func,
                                           event,
                                           nicks,
                                           channels,
                                           regex
                                           )
                                          )
                try:
                    expose = getattr(func, "exposed")
                except (AttributeError):
                    pass
                else:
                    if (expose == True):
                        # Expose our method please
                        pass
        
    def reload_handlers(self):
        self._handlers = []
        self.load_handlers(load=True)
    def set_topic(self, channel, topic):
        self.server.topic(channel, topic)
    def wait(self, timeout=None):
        if (self.ready):
            return
        else:
            from time import sleep
            if (timeout == None):
                while True:
                    if (self.ready):
                        break
                    sleep(0.2)
            else:
                for i in xrange(timeout*5):
                    if (self.ready):
                        break
                    sleep(0.2)
            return
    def _dispatcher(self, server, event):
        etype = event.eventtype()
        try:
            if ('!' in event.source()):
                nick = irclib.nm_to_n(event.source())
                userhost = irclib.nm_to_uh(event.source())
                host = irclib.nm_to_h(event.source())
        except (TypeError):
            #Source is None
            pass
        channel = event.target()
        if (etype == 'ctcp'):
            request = event.arguments()[0]
            if (request == 'VERSION'):
                if (hasattr(config, "irc_version")):
                    if (isinstance(config.irc_version, basestring)):
                        server.ctcp_reply(nick, 'VERSION {version}'\
                                  .format(version=config.irc_version))
                    else:
                        logging.info("IRC Version configuration incorrect")
                else:
                    server.ctcp_reply(nick, 'VERSION irclib 4.8')
        elif (etype == 'invite'):
            server.join(event.arguments()[0])
        elif (etype == 'disconnect'):
            # We disconnected ;_;
            self.ready = False
        elif (etype == 'endofmotd'):
            if (hasattr(config, "irc_pass")):
                if (isinstance(config.irc_pass, basestring)):
                    server.privmsg('nickserv', 'identify {pwd}'\
                           .format(pwd=config.irc_pass))
                else:
                    logging.info("IRC Password configuration incorrect")
            if (hasattr(config, "irc_channels")):
                try:
                    channels = ", ".join(config.irc_channels)
                except (TypeError):
                    logging.info("IRC Channel configuration incorrect")
                else:
                    server.join(channels)
            self.ready = True
        elif (etype == "pubmsg"):
            # TEXT OH SO MUCH TEXT
            text = event.arguments()[0]
            for handler in [handlers for handlers in self._handlers if \
                            handlers[2] == "on_text"]:
                if (handler[0].match(text)):
                    # matchy
                    nicks, chans = handler[3:5]
                    if (not nicks == ALL_NICKS):
                        if (type(nicks) == list):
                            # normal list man
                            if (not nick in nicks):
                                continue
                        elif (type(nicks) == int):
                            # constant
                            # TODO:
                            # We can make this all a dictionary most likely at
                            # the top of the module
                            if (nicks in [ACCESS_NICKS,
                                          OP_NICKS,
                                          HALFOP_NICKS,
                                          VOICE_NICKS,
                                          REGULAR_NICKS]):
                                if (not {
                                        ACCESS_NICKS: server.hasaccess,
                                        OP_NICKS: server.isop,
                                        HALFOP_NICKS: server.ishop,
                                        VOICE_NICKS: server.isvoice,
                                        REGULAR_NICKS: server.isnormal,
                                        }[nicks](channel, nick)):
                                    continue
                            elif (nicks == DEV_NICKS):
                                if (not nick in config.irc_devs):
                                    continue
                        else:
                            # We don't even know just ignore it
                            # Send to debugging for cleanness
                            logging\
                        .debug("HandlerError: {type} on 'nick' not accepted"\
                                          .format(type=str(type(nicks))))
                            continue
                    if (not chans == ALL_CHANNELS):
                        # Do channel filtering
                        if (type(chans) == list):
                            # normal list
                            if (not channel in chans):
                                continue
                        elif (type(chans) == int):
                            # constant (WE DON'T HAVE ANY RIGHT NOW)
                            continue
                        else:
                            # We don't even know just ignore it
                            # Send to debugging for cleanness
                            logging\
                        .debug("HandlerError: {type} on 'channel' not accepted"\
                                          .format(type=str(type(chans))))
                            continue
                    # Call our func here since the above filters will call
                    # 'continue' if the filter fails
                    handler[1](server, nick, channel, text, userhost)
                    
streamer = "" # Should be set with shoutmain.instance
class IRCMain(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.init_irc()
        self.start()
    def init_irc(self):
        logging.info("Creating IRC Objects")
        self.handlers = IRCSubHandlers()
        self.irc = ircwrapper.IRC()
        self.irc.version = config.irc_version
        self.serverid = self.irc.connect(config.irc_server, config.irc_port, config.irc_name,
                                config.irc_pass, config.irc_channels)
        self.server = self.irc.serverlist[self.serverid]
        commands.streamer = streamer
        commands.irc = self
        self.irc.serverlist[self.serverid].add_global_handler('pubmsg', self.handlers.call_on_text, 0)
    def check_irc(self):
        if (not self.server.is_connected()):
            logging.info(u"IRC is not connected, trying to reconnect")
            self.server.reconnect(u"Not connected")
    def run(self):
        while True:
            self.check_irc()
            time.sleep(60)
    def reload_irc_handlers(self):
        global streamer
        # unregister the original handlers
        # Just recreate the SubClass
        self.handlers = IRCSubHandlers()
        # reload module
        reload(commands)
        # set variables it requires again
        # streamer = Should be assigned with shoutmain.instance
        commands.streamer = streamer
        # irc = Should be assigned with irc.IRCSubHandlers
        commands.irc = self
    def __getattr__(self, name):
        if (hasattr(self.irc, name)):
            return getattr(self.irc, name)
        else:
            raise AttributeError
class IRCSubHandlers:
    def __init__(self):
        self._handlers = {}
    def add_handler(self, handler, event, **kwargs):
        """Adds a handler to be called when event happens with the appropriate parameters.
        Parameters are different for each event.
        
        Following events are supported for now:
            'on_text': Activates when there is a message, additional parameters should
                always be added with keywords. The following are available:
                    
                    'nick': The nick that triggered the event. Can be left out for all nicks
                    'channel': The channel the event origined from.
                    'text': a regex pattern that this event should be triggered with
                            i.e. text='Hello.*' will trigger on all messages that begin
                                                with 'Hello'.
        """
        info = {'nick':'*', 'channel':'*', 'text':''}
        info.update(kwargs)
        info['compiled'] = re.compile(info['text'], re.I|re.U)
        if not event in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append((handler, info))
    
    def clean_handlers(self):
        self._handlers = {}
        
    def call_on_text(self, conn, event):
        if (not hasattr(commands, "irc") and not hasattr(commands, "streamer")):
            logging.error("IRC Commands have no access to 'irc' or 'streamer'")
            return
        if ('on_text' in self._handlers):
            nick = unicode(nm_to_n(event.source()), errors="replace")
            userhost = unicode(nm_to_uh(event.source()), errors="replace")
            host = unicode(nm_to_h(event.source()), errors="replace")
            target = unicode(event.target(), errors="replace")
            text = event.arguments()[0].decode('utf-8', 'replace')
            for handler in self._handlers['on_text']:
                call, info = handler
                if (info['nick'] != nick) and (nick not in info['nick']) and (info['nick'] != '*'):
                    continue
                if (info['channel'] != target) and (target not in info['channel']) and (info['channel'] != '*'):
                    continue
                if (info['text'] != ''):
                    compiled = info['compiled']
                    result = compiled.match(text)
                    if (result == None):
                        continue
                print event.arguments()
                try:
                    call(conn, nick, target, text, userhost)
                except:
                    logging.exception("IRC Command error'd")