from threading import Thread, Event
import logging
import config
import re
import irclib
from multiprocessing.managers import BaseManager
import bootstrap

# Handler constants
# Channels
ALL_CHANNELS = 0
MAIN_CHANNELS = ["#r/a/dio", "#r/a/dio-dev"]
PRIVATE_MESSAGE = 1
# Nicks
ALL_NICKS = 0 # All nicknames can trigger this
ACCESS_NICKS = 1 # Nicks with halfop or higher can trigger this
OP_NICKS = 2 # Only operators or higher can trigger this
HALFOP_NICKS = 3 # Only half operators can trigger this
VOICE_NICKS = 4 # Only voiced people can trigger this
REGULAR_NICKS = 5 # Only regulars can trigger this
DEV_NICKS = 6 # Only the nicknames defined in config.irc_devs can trigger this

class Session(object):
    __metaclass__ = bootstrap.Singleton
    def __init__(self):
        logging.info("Creating IRC Session")
        self.ready = False
        self.commands = None
        self._handlers = []
        self.active = Event()
        self.exposed = {}
        self._irc = irclib.IRC()
        self.load_handlers()
        self._irc.add_global_handler("all_events", self._dispatcher)
        self.connect()
        # initialize our process thread
        self.processor_thread = Thread(target=self.processor)
        self.processor_thread.name = "IRC Processor"
        self.processor_thread.daemon = 1
        self.processor_thread.start()
    def server(self):
        return self._server
    def irc(self):
        return self._irc
    def processor(self):
        # Our shiny thread that processes the socket
        logging.info("THREADING: Started IRC processor")
        while (not self.active.is_set()):
            # Call the process once
            self._irc.process_once(timeout=1)
            # We also check for new proxy calls from here
        logging.info("THREADING: Stopped IRC processor")
    def connect(self):
        # We really only need one server
        if (not self.active.is_set()):
            self._server = self._irc.server()
            self._server.connect(config.irc_server,
                                config.irc_port,
                                config.irc_name)
        else:
            raise AssertionError("Can't connect closed Session")
        
    def connected(self):
        return self._server.is_connected()
    
    def disconnect(self):
        self._irc.disconnect_all("Disconnected on command")
        
    def shutdown(self):
        self.active.set()
        self._irc.disconnect_all("Leaving...")
        self.processor_thread.join()
        
    def load_handlers(self, load=False):
        # load was ment to be reload, but that fucks up the reload command
        logging.debug("Loading IRC Handlers")
        if (load):
            try:
                self.commands = reload(self.commands)
            except (ImportError):
                # Report this to caller
                raise
        else:
            self.commands = __import__("hanyuu_commands")
        from types import FunctionType
        for name in dir(self.commands):
            func = getattr(self.commands, name)
            if (type(func) == FunctionType):
                try:
                    handler = getattr(func, "handler")
                except (AttributeError):
                    # no handler
                    pass
                else:
                    event, regex, nicks, channels = handler
                    cregex = re.compile(regex, re.I)
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
                    logging.debug("Loaded IRC handler: {name}"\
                                  .format(name=name))
                expose = False
                try:
                    expose = getattr(func, "exposed")
                except (AttributeError):
                    pass
                else:
                    if (expose == True):
                        # Expose our method please
                        if (hasattr(self, name)):
                            logging.debug("We can't assign you to something that already exists")
                        else:
                            def create_func(self, func):
                                return lambda *s, **k: func(self._server, *s, **k)
                            setattr(self, name,
                                create_func(self, func))
                            self.exposed[name] = func
    def reload_handlers(self):
        self._handlers = []
        for name in self.exposed:
            try:
                delattr(self, name)
            except (AttributeError):
                pass
        self.exposed = {}
        self.load_handlers(load=True)
    def set_topic(self, channel, topic):
        self._server.topic(channel, topic)
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
        if (etype != "all_raw_messages"):
            logging.debug("%s: %s - %s: %s" % (event._eventtype,
                                   event._source,
                                   event._target,
                                   event._arguments))
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
                for channel in config.irc_channels:
                    try:
                        server.join(channel)
                    except:
                        logging.info("IRC Channel configuration incorrect")
            self.ready = True
        elif (etype == "pubmsg") or (etype == "privmsg"):
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
                            if (etype == "privmsg" and chans != PRIVATE_MESSAGE):
                                continue
                                # a private message, special privilege yo
                                
                        else:
                            # We don't even know just ignore it
                            # Send to debugging for cleanness
                            logging\
                        .debug("HandlerError: {type} on 'channel' not accepted"\
                                          .format(type=str(type(chans))))
                            continue
                    # Call our func here since the above filters will call
                    # 'continue' if the filter fails
                    try:
                        handler[1](server, nick, channel, text, userhost)
                    except:
                        logging.exception("IRC Handler exception")
                        
class IRCManager(BaseManager):
    pass

IRCManager.register("stats", bootstrap.stats)
IRCManager.register("session", Session,
                    method_to_typeid={"server": "generic",
                                      "irc": "generic"})
IRCManager.register("generic")

def connect():
    global manager, session
    manager = IRCManager(address=config.manager_irc, authkey=config.authkey)
    manager.connect()
    session = manager.session()
    return session

def start():
    s = Session()
    manager = IRCManager(address=config.manager_irc, authkey=config.authkey)
    server = manager.get_server()
    server.serve_forever()
    
def launch_server():
    manager = IRCManager(address=config.manager_irc, authkey=config.authkey)
    manager.start()
    global _unrelated_
    _unrelated_ = manager.session()
    return manager

if __name__ == "__main__":
    launch_server()