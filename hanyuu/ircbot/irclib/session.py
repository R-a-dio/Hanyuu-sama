"""
A high level session object to the lower level irclib.connection module.
"""
from . import utils, connection

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
    def __init__(self, server, nickname, channel, message):
        super(HighEvent, self).__init__()
        
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
        elif command == 'welcome':
            # Event used for the welcome message
            pass
        elif command == 'pubmsg':
            # A channel message
            nickname = Nickname(low_event.source)
            channel = low_event.target
            message = low_event.arguments[0]
            return creator(nickname, channel, message)
        elif command == 'privmsg':
            # Private message
            # The target is set to our own nickname in privmsg.
            nickname = Nickname(low_event.source)
            message = low_event.arguments[0]
            return creator(nickname, None, message)
        elif command == 'pubnotice':
            # A notice to a channel
            nickname = Nickname(low_event.source)
            channel = low_event.target
            message = low_event.arguments[0]
            return creator(nickname, channel, message)
        elif command == 'privnotice':
            # A notice to only us.
            # The target is set to our own nickname in privnotice.
            nickname = Nickname(low_event.source)
            message = low_event.arguments[0]
            return creator(nickname, None, message)
        elif command == 'ctcp' or command == 'action':
            # A CTCP to us.
            # Same as privmsg/notice the target is our own nickname
            nickname = Nickname(low_event.source)
            # The irclib splits off the first space delimited word for us.
            command = low_event.arguments[0]
            # The things behind the command are then indexed behind it.
            message = low_event.arguments[1]
            
            event = creator(nickname, None, message)
            event.command = command
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
        elif command == 'mode':
            # Mode change in the channel
            # The nickname that set the mode
            mode_setter = Nickname(low_event.source)
            # Simple channel
            channel = low_event.target
            # This is a raw mode string that we need to parse and add to
            # the targeted individuals.
            modes = utils.parse_modes(low_event.arguments[0])
            # This is a list of targets instead of one item so common
            targets = low_event.arguments[1:]
            
            event = creator(mode_setter, channel, None)
            event.modes = utils.intertwine_modes(modes, targets)
        elif command == 'umode':
            # A user mode was set.
            pass
        elif command == 'currenttopic':
            # A response/welcome telling us what the topic is.
            pass
        elif command == 'notopic':
            # A response of when there is no topic.
            pass
        elif command == 'featurelist':
            # TODO: What is this.
            # I have no idea what this does
            pass
        elif command == 'endofmotd':
            # Signifies the end of the message of the day
            pass
        elif command == 'namreply':
            # A name info reply.
            pass

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