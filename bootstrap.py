import config
import os
import logging
from threading import Thread, Event
from Queue import Empty

OKAY = 0
UNKNOWN_ERR = 1
START_ERR = 2
STOP_ERR = 3
NOTSUPPORTED_ERR = 4

logging.getLogger().setLevel(config.loglevel)
def get_logger(name=None):
    """returns a process safe logger, best set to the global variable
    'logging' when used in a separate process"""
    import logging
    import logging.handlers
    logger = logging.getLogger()
    try:
        logger.setLevel(config.loglevel)
    except (AttributeError):
        logger.setLevel(logging.INFO)
    if (not os.path.exists("./logs")):
        os.makedirs("./logs")
    handler = logging.handlers.RotatingFileHandler("./logs/{name}.log"\
                                         .format(name=name), maxBytes=5120,
                                         backupCount=5)
    logger.addHandler(handler)
    return logger
    
class Controller(Thread):
    """The controller of all the modules, should only be used from the public
    methods"""
    _loaded_modules = {} # Loaded mods
    _state_save = {} # For saving states
    def load(self, name, **kwargs):
        """Load a module"""
        try:
            self._queue.put((0, name, kwargs))
        except:
            logging.exception("Don't do this you ass")
            
    def stop(self, name, **kwargs):
        """Stop a module"""
        try:
            self._queue.put((1, name, kwargs))
        except:
            logging.exception("Don't do this you ass")
            
    def stop_all(self):
        """Stops all modules"""
        try:
            self._queue.put((2, None, None))
        except:
            logging.exception("Don't do this you ass")
            
    def reload(self, name, **kwargs):
        """Reloads a module"""
        try:
            self._queue.put((3, name, kwargs))
        except:
            logging.exception("Don't do this you ass")
            
            
    def _processor(self):
        while not self._alive.is_set():
            try:
                id, name, kwargs = self._queue.get(timeout=2)
            except Empty:
                pass
            else:
                with self._lock:
                    if (id == 0): # load
                        self._load(name, **kwargs)
                    elif (id == 1): # stop
                        self._stop(name, **kwargs)
                    elif (id == 2): # stop_all
                        self._stop_all()
                    else: # reload
                        self._reload(name, **kwargs)
    def _load(self, name, **kwargs):
        """Internal method"""
        try:
            mod = __import__(name)
        except (ImportError):
            raise
        else:
            state = self._state_save.get(name, None)
            try:
                item = mod.start(state)
            except:
                # Something went derpiedoo, put it into the log instead of re-raising
                logging.exception("{name} failed to start".format(name=name))
                return START_ERR
            else:# Add return item because it can be the class we should use for cleaning
                self._loaded_modules[name] = (item, mod)
                return OKAY
        return UNKNOWN_ERR
    def _stop(self, name, **kwargs):
        """Internal method"""
        if (name in self._loaded_modules):
            obj, module = self._loaded_modules[name]
            if (hasattr(module, "shutdown")):
                callee = module.shutdown
            else:
                try:
                    callee = obj.shutdown
                except (AttributeError):
                    # Remove them since the module doesn't require cleanup
                    del self._loaded_modules[name]
                    return NOTSUPPORTED_ERR
            try:
                state = callee(**kwargs)
            except:
                # Put it into logging so it can be examined
                logging.exception("{name} failed to shutdown cleanly"\
                                  .format(name=name))
                return STOP_ERR
            else:
                self._state_save[name] = state
                del self._loaded_modules[name]
                return OKAY
        else:
            return OKAY
    def _stop_all(self):
        """Internal method"""
        for name in self._loaded_modules:
            kwargs = {}
            if (name == "afkstreamer"):
                kwargs = {"force": True}
            value = self._stop(name, **kwargs)
            if (value != OKAY):
                logging.error("Failed to cleanly stop {name}".format(name=name))
            else:
                logging.info("Stopped {name} correctly".format(name=name))
    
    def _reload(self, name, **kwargs):
        """Internal method"""
        obj = module = None
        if (name in self._loaded_modules):
            obj, module = self._loaded_modules[name]
        value = self._stop(name)
        if (module):
            module = reload(module)
        value = self._load(name)
        return value

# Return values for various functions

