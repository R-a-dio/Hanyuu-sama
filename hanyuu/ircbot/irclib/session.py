"""
A high level session object to the lower level irclib.connection module.
"""
from . import utils, connection

textual_commands = ["privmsg",
                    "pubmsg",
                    "privnotice",
                    "pubnotice"]

class Session(object):
    """
    A session object that can join multiple IRC networks and multiple IRC
    channels with a high level interface.
    """
    def __init__(self):
        super(Session, self).__init__()
        self.irclib = connection.IRC()
        
    def low_level_handler(self, event):
        """
        Registered handler for all lowlevel events.
        
        This should make higher level abstractions of the Event type passed.
        
        """
        event = HighEvent.from_low_event(event)


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
    def from_low_event(cls, low_event):
        command = low_event.eventtype
        
        # We supply the source and server already to reduce code repetition.
        # Just use it as the HighEvent constructor but with partial applied.
        creator = lambda *args, **kwargs: cls(low_event.server,
                                              command,
                                              *args,
                                              **kwargs)
        
        if command == 'nick':
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
            return creator(nickname, channel, message)
        elif command in ["privmsg", "privnotice"]:
            # Private message
            # The target is set to our own nickname in privmsg.
            nickname = Nickname(low_event.source)
            message = low_event.arguments[0]
            return creator(nickname, None, message)
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
            # A reply to one of our own CTCPs
            pass
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
        elif command == 'topic':
            # Someone changing the channel topic.
            nickname = Nickname(low_event.source)
            channel = low_event.target
            topic = low_event.arguments[0]
            
            return creator(nickname, channel, topic)
        elif command in ['mode', 'umode']:
            # Mode change in the channel
            # The nickname that set the mode
            mode_setter = Nickname(low_event.source)
            # Simple channel
            channel = low_event.target
            
            #utils._parse_modes returns a list of tuples with (operation, mode, param)
            event = creator(mode_setter, channel, None)
            event.modes = utils._parse_modes(low_event.arguments.join(' '))
        elif command in ['topic', 'currenttopic', 'notopic']:
            # Any message that tells us what the topic is.
            # The channel that had its topic set.
            channel = low_event.target            
            # The person who set the topic.
            # If this isn't a topic command, there is no setter
            topic_setter = None
            if command == 'topic':
                setter = Nickname(low_event.source)            
            # The argument contains the 
            # Treat notopic as empty string
            topic = ''
            if not command == 'notopic':
                topic = low_event.arguments[0]
            event = creator(topic_setter, channel, topic)
            return event

        # TODO: Check for missing commands.
        return
    
    
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