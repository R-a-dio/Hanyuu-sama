from threading import Thread
from irclib import nm_to_n, nm_to_uh, nm_to_h
import ircwrapper
import hanyuu_commands as commands
import logging
import config
import time
import re

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