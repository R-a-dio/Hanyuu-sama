import threading
import time
import pylibshout
from . import logger


logger = logger.getChild('icecast')


class Icecast(object):
    connecting_timeout = 5.0
    def __init__(self, source, config):
        super(Icecast, self).__init__()
        self.config = (config if isinstance(config, IcecastConfig)
                       else IcecastConfig(config))
        self.source = source
        
        self._shout = self.setup_libshout()
    
    def connect(self):
        """Connect the libshout object to the configured server."""
        try:
            self._shout.open()
        except (pylibshout.ShoutException) as err:
            logger.exception("Failed to connect to Icecast server.")
            raise IcecastError("Failed to connect to icecast server.")
            
    def connected(self):
        """Returns True if the libshout object is currently connected to
        an icecast server."""
        try:
            return True if self._shout.connected() == -7 else False
        except AttributeError:
            return False
        
    def read(self, size, timeout=None):
        raise NotImplementedError("Icecast does not support reading.")
    
    def nonblocking(self, state):
        pass
        
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
            
    def switch_source(self, new_source):
        """Tries to change the source without disconnect from icecast."""
        self._should_run.set() # Gracefully try to get rid of the thread
        try:
            self._thread.join(5.0)
        except RuntimeError as err:
            logger.exception("Got called from my own thread.")
        self.source = new_source # Swap out our source
        self.start() # Start a new thread (so roundabout)
        
    def set_metadata(self, metadata):
        try:
            self._shout.metadata = {'song': metadata} # Stupid library
        except (pylibshout.ShoutException) as err:
            logger.exception("Failed sending metadata. No action taken.")
            self._saved_meta = metadata
            
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
    """Simple dict subclass that knows how to apply the keys to a
    libshout object.
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