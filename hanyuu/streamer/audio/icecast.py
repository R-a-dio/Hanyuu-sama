"""
A module that adds some extra useful wrapping around the **libshout** library.
"""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from . import logger
logger = logger.getChild('icecast')

import threading
import time
import pylibshout


class Icecast(object):
    """
    ======
    Source
    ======
    
    The :class:`Icecast` class expects a source that returns encoded MP3 audio
    data. Use of other formats as of now is not supported.
    
    The source requires the following attributes:
        :func:`read`:
            A method that returns encoded MP3 audio data.
            
            :param size: An :const:`int` signifying the amount of bytes to read.
            :returns: :const:`bytes` containing the requested MP3 audio data.
            
    =======
    Options
    =======
    
    We accept a single option that is a full fletched configuration for the
    underlying **libshout** library.
    
        - icecast_config: 
            A :const:`dict` containing the configuration for **libshout**.
            For the exact contents of the dictionary see :class:`IcecastConfig`.
            
    ========
    Handlers
    ========
    
    The following handler hooks are supported by :class:`Icecast`.
    
        - icecast_start(icecast):
            Called when the :meth:`Icecast.start` is called.
            
            :param icecast: :class:`Icecast` instance.
        - icecast_close(icecast):
            Called when the :meth:`Icecast.close` is called.
            
            :param icecast: :class:`Icecast` instance.
        - icecast_connect(icecast, options):
            Called when :meth:`Icecast.connect` is called.
            
            :param icecast: :class:`Icecast` instance.
            :param options: :class:`IcecastConfig` instance used.
        - icecast_metadata(icecast, metadata):
            Called when metadata is send to the server.
            
            :param icecast: :class:`Icecast` instance.
            :param metadata: :const:`unicode` instance containing the metadata send.
    """
    options = [('icecast_config', {})]
    #: The time to wait when we lose connection by cause of external behaviour.
    connecting_timeout = 5.0
    def __init__(self, source, options, handlers):
        super(Icecast, self).__init__()
        self.config = IcecastConfig(options['icecast_config'])
        
        self.handler = handlers
        
        self.source = source
        
        self._shout = self.setup_libshout()
    
    def connect(self):
        """Connect the libshout object to the configured server."""
        try:
            self._shout.open()
        except (pylibshout.ShoutException) as err:
            logger.exception("Failed to connect to Icecast server.")
            raise IcecastError("Failed to connect to icecast server.")
        finally:
            self.handler.icecast_connect(self, self.config)
            
    def connected(self):
        """Returns True if the libshout object is currently connected to
        an icecast server."""
        try:
            return True if self._shout.connected() == -7 else False
        except AttributeError:
            return False
        
    def read(self, size, timeout=None):
        raise NotImplementedError("Icecast does not support reading.")
        
    def close(self):
        """Closes the libshout object and tries to join the thread if we are
        not calling this from our own thread."""
        self._should_run.set()
        try:
            self._shout.close()
        except (pylibshout.ShoutException) as err:
            if err[0] == pylibshout.SHOUTERR_UNCONNECTED:
                pass
            else:
                logger.exception("Exception in pylibshout close call.")
                raise IcecastError("Exception in pylibshout close.")
        finally:
            self.handler.icecast_close(self)
        try:
            self._thread.join(5.0)
        except (RuntimeError) as err:
            pass
        
    def run(self):
        while not self._should_run.is_set():
            while self.connected():
                if hasattr(self, '_saved_meta'):
                    self.set_metadata(self._saved_meta)
                    del self._saved_meta
                    
                buff = self.source.read(4096)
                if not buff:
                    # EOF
                    self.close()
                    logger.exception("Source EOF, closing ourself.")
                    break
                try:
                    self._shout.send(buff)
                    self._shout.sync()
                except (pylibshout.ShoutException) as err:
                    logger.exception("Failed sending stream data.")
                    self.reboot_libshout()
                    
            if not self._should_run.is_set():
                time.sleep(self.connecting_timeout)
                self.reboot_libshout()
                
    def start(self):
        """Starts the thread that reads from source and feeds it to icecast."""
        if not self.connected():
            self.connect()
        self._should_run = threading.Event()
        
        self._thread = threading.Thread(target=self.run)
        self._thread.name = "Icecast"
        self._thread.daemon = True
        self._thread.start()
        
        self.handler.icecast_start(self)
        
    def switch_source(self, new_source):
        """Tries to change the source without disconnect from icecast."""
        self._should_run.set() # Gracefully try to get rid of the thread
        try:
            self._thread.join(5.0)
        except RuntimeError as err:
            logger.exception("Got called from my own thread.")
        self.source = new_source # Swap out our source
        self.start() # Start a new thread (so roundabout)
        
    def metadata(self, metadata):
        try:
            self._shout.metadata = {'song': metadata} # Stupid library
        except (pylibshout.ShoutException) as err:
            logger.exception("Failed sending metadata. No action taken.")
            self._saved_meta = metadata
        finally:
            self.handler.icecast_metadata(self, metadata)
            
    def setup_libshout(self):
        """Internal method
        
        Creates a libshout object and puts the configuration to use.
        """
        shout = pylibshout.Shout(tag_fix=False)
        self.config.setup(shout)
        return shout
        
    def reboot_libshout(self):
        """Internal method
        
        Tries to recreate the libshout object.
        """
        try:
            self._shout = self.setup_libshout()
        except (IcecastError) as err:
            logger.exception("Configuration failed.")
            self.close()
        try:
            self.connect()
        except (IcecastError) as err:
            logger.exception("Connection failure.")
            
class IcecastConfig(dict):
    """
    Simple dict subclass that knows how to apply the keys to a
    libshout object.
    
    The following dictionary items are supported:
        
        - host: 
            The hostname of the icecast server to connect to.
            (defaults to localhost)
        - port:
            The port the icecast server is running on.
            (defaults to 8000)
        - user:
            The icecast user.
        - password:
            The password for the icecast server.
        - mount:
            The mountpoint to connect to.
        - format:
            The format we are going to stream in.
            
            Can be one of the following:
                - 0 = OGG encoded data.
                - 1 = MP3 encoded data.
        - protocol:
            The protocol to use to connect to the icecast server.
            
            Can be one of the following:
                - 0 = HTTP protocol
                - 1 = XAUDIOCAST protocol
                - 2 = ICY protocol
                
            If you are unsure of which one to use, you are most likely after
            the HTTP protocol.
            
        - name:
            An optional name to show on the icecast page.
        - url:
            An optional URL to be placed on the icecast page.
        - genre:
            An optional genre to be shown on the icecast page.
        - agent:
            The useragent to connect with.
            (defaults to libshout/version)
        - description:
            An optional small description to show on the icecast page.
        - charset:
            An optional charset to use for sending metadata.
            (defaults to UTF-8)
        - public:
            An optional boolean specifying if this stream is to be marked as
            public in icecast. (This affects indexing on external sites.)
        - dumpfile:
            A file to dump the streamed data to.
        - audio_info:
            Can be ignored, see libshout docs for info.
        - metadata:
            Can be ignored, see libshout docs for info.
    """
    def __init__(self, attributes=None):
        super(IcecastConfig, self).__init__(attributes or {})
        
    def setup(self, shout):
        """Setup 'shout' configuration by setting attributes on the object.
        
        'shout' is a pylibshout.Shout object.
        """
        for key, value in self.iteritems():
            try:
                setattr(shout, key, value)
            except pylibshout.ShoutException as err:
                raise IcecastError(("Incorrect configuration option '{:s}' or "
                                   " value '{:s}' used.").format(key, value))
                
                
class IcecastError(Exception):
    pass