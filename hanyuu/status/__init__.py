from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from .. import utils, config
import logging
import pylibmc
import ConfigParser
import contextlib


logger = logging.getLogger('hanyuu.status')


def memcache_client():
    """
    Returns a :class:`pylibmc.Client` object.
    """
    try:
        options = config.get('memcache', 'servers')
    except ConfigParser.NoSectionError:
        raise ConfigParser.Error("Missing memcache configuration. "
                                 "Please add a [memcache] section "
                                 "with at least the `servers` option "
                                 "specified.")
    except ConfigParser.NoOptionError:
        raise ConfigParser.Error("Missing memcache.servers configuration. "
                                 "Please add a `servers` option to the "
                                 "[memcache] section.")
    except ConfigParser.Error:
        raise
    
    servers = []
    for server in options.split(','):
        servers.append(server.strip())
    return pylibmc.Client(servers)


class Base(object):
    """
    Simple base class that sets the attribute :attr:cache to a
    :class:memcache.Client ready to be used.
    """
    def __init__(self):
        super(Base, self).__init__()
        client = memcache_client()
        self._mem_pool = pylibmc.ClientPool(client, 4)
        
    @property
    def cache(self):
        @contextlib.contextmanager
        def locked_client():
            with self._mem_pool.reserve() as client:
                yield client
        return locked_client()
        
        
@utils.instance_decorator
class Stream(Base):
    """
    Wrapping class around the memcache server and variables relevant to
    the status of the streaming server.
    
    """
    @property
    def listeners(self):
        """
        Returns the total amount of listeners as an integer.
        
        This is the listeners combined from all relay servers.
        """
        with self.cache as client:
            return client.get(b'status.current_listeners') or 0
    
    @listeners.setter
    def listeners(self, value):
        """
        Sets the current listeners value.
        
        :obj:value should be an integer type.
        """
        with self.cache as client:
            client.set(b'status.current_listeners', value)
        
    @property
    def peak_listeners(self):
        with self.cache as client:
            return client.get(b'status.peak_listeners') or 0
    
    @peak_listeners.setter
    def peak_listeners(self, value):
        """
        Sets the current peak listeners value.
        
        :obj:value should be an integer type.
        """
        with self.cache as client:
            client.set(b'status.peak_listeners', value)
        
    @property
    def online(self):
        """
        Returns if the master server is online or not.
        
        Returns a boolean type.
        """
        with self.cache as client:
            return bool(client.get(b'status.online')) or False
    
    @online.setter
    def online(self, value):
        """
        Sets the status of the master server.
        
        :obj:value is passed to :func:bool
        """
        with self.cache as client:
         client.set(b'status.online', bool(value))
        
    @property
    def current(self):
        """
        Gets the current song metadata playing on the master server.
        
        Returns a unicode object.
        """
        with self.cache as client:
            value = client.get(b'status.current')
        if value:
            value = value.decode('utf-8')
        else:
            value = ''
        return value
    
    @current.setter
    def current(self, value):
        """
        Sets the current song metadata.
        
        Expects a utf-8 bytestring. If passed an unicode type will
        be encoded to utf-8 while replacing errornous characters.
        """
        if isinstance(value, unicode):
            value = value.encode('utf-8', 'replace')
        with self.cache as client:
            client.set(b'status.current', value)
    
    
@utils.instance_decorator
class Site(Base):
    """
    Object that encapsulates state of the website.
    
    """
    @property
    def thread(self):
        """
        Returns the current thread URL.
        
        Returns a unicode string or None
        """
        with self.cache as client:
            return client.get(b'site.thread').decode('utf-8') or None
        
    @thread.setter
    def thread(self, value):
        """
        Sets the current thread URL.
        
        :obj:value should be a bytestring, an unicode string will be encoded
        with ('utf-8', 'replace') as arguments.
        """
        if isinstance(value, unicode):
            value = value.encode('utf-8', 'replace')
        with self.cache as client:
            client.set(b'site.thread', value)

    @property
    def dj(self):
        """
        Returns the current DJ that is live.
        
        Returns a :class:encapsulations.DJ object.
        """
        with self.cache as client:
            return encapsulations.DJ(client.get(b'site.dj'))
        
    @dj.setter
    def dj(self, value):
        """
        Sets the current DJ that is live.
        
        :obj:value should be an :class:`encapsulations.DJ` object.
        
        or
        
        :obj:value is required to be an object that supports casting to an
            integer as the value will be passed to :func:`int`
        """
        if isinstance(value, encapsulations.DJ):
            value = value.id
        else:
            value = int(value)
        with self.cache as client:
            client.set(b'site.dj', value)
            
            
@utils.instance_decorator
class Streamer(Base):
    """
    Object that encapsulates state of the AFK streamer.
    """
    @property
    def requests_enabled(self):
        """
        Returns a bool indicating if the AFK streamer accepts requests.
        
        This is False if either Requests got disabled explicitely or
        the AFK streamer is not streaming at the moment.
        """
        with self.cache as client:
            return bool(client.get(b'streamer.requests_enabled')) or False
    
    @requests_enabled.setter
    def requests_enabled(self, value):
        """
        Sets the requests capability to :obj:value
        
        :obj:value is passed to :func:bool before updating.
        """
        with self.cache as client:
            client.set(b'streamer.requests_enabled', bool(value))