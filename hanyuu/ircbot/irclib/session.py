from __future__ import unicode_literals
"""
A high level session object to the lower level irclib.connection module.
"""


class Session(object):
    """
    A session object that can join multiple IRC networks and multiple IRC
    channels with a high level interface.
    """
    def __init__(self):
        super(Session, self).__init__()
        self.irclib = connection.IRC()
        
    def high_level_handler(self, event):
        """
        Registered handler for all lowlevel events.
        
        This should make higher level abstractions of the Event type passed.
        
        """
        command = event.eventtype
        
        if command == 'nick':
            # A nickname change.
            pass
        elif command == 'welcome':
            # Event used for the welcome message
            pass
        elif command == 'pubmsg':
            # A channel message
            pass
        elif command == 'pubnotice':
            # A notice to a channel
            pass
        elif command == 'privnotice':
            # A notice to only us.
            pass
        elif command == 'ctcp':
            # A CTCP to us.
            pass
        elif command == 'ctcpreply':
            # A reply to one of our own CTCPs
            pass
        elif command == 'action':
            # An action (/me) really just a CTCP
            pass
        elif command == 'quit':
            # A quit from an user.
            pass
        elif command == 'ping':
            # A ping request
            pass
        elif command == 'join':
            # Someone joining our channel
            pass
        elif command == 'part':
            # Someone leaving our channel
            pass
        elif command == 'kick':
            # Someone forcibly leaving our channel.
            pass
        elif command == 'topic':
            # Someone changing the channel topic.
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
        elif command == 'mode':
            # Mode change in the channel
            pass
        # TODO: Check for missing commands.
        return