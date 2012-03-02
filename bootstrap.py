import config
import os
import logging

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
    
module_list = ["config"]

_reload = reload
loaded_modules = [] # For module names
_loaded_modules = {} # For the actual module objects
_state_saves = {} # For state saving of modules

# Return values for various functions
OKAY = 0
UNKNOWN_ERR = 1
START_ERR = 2
STOP_ERR = 3
NOTSUPPORTED_ERR = 4

def load(name, **kwargs):
    """Tries to load and call the module.start() of 'name'"""
    global _loaded_modules, loaded_modules, _state_saves
    try:
        mod = __import__(name)
    except (ImportError):
        raise
    else:
        state = _state_saves.get(name, None)
        try:
            item = mod.start(state)
        except:
            # Something went derpiedoo, put it into the log instead of re-raising
            logging.exception("{name} failed to start".format(name=name))
            return START_ERR
        else:# Add return item because it can be the class we should use for cleaning
            loaded_modules.append(name)
            _loaded_modules[name] = (item, mod)
            return OKAY
    return UNKNOWN_ERR

def stop(name, **kwargs):
    global _loaded_modules, loaded_modules, _state_saves
    if (name in loaded_modules):
        obj, module = _loaded_modules[name]
        if (hasattr(module, "shutdown")):
            callee = module.shutdown
        else:
            try:
                callee = obj.shutdown
            except (AttributeError):
                return NOTSUPPORTED_ERR
        try:
            state = callee(**kwargs)
        except:
            # Put it into logging so it can be examined
            logging.exception("{name} failed to shutdown cleanly"\
                              .format(name=name))
            return STOP_ERR
        else:
            _state_saves[name] = state
            del _loaded_modules[name]
            loaded_modules.remove(name)
            return OKAY
    else:
        return OKAY # It isn't even loaded, so it's okay to return OKAY
    
def stop_all():
    global loaded_modules
    for name in loaded_modules:
        kwargs = {}
        if (name == "afkstreamer"):
            kwargs = {"force": True}
        value = stop(name, **kwargs)
        if (value != OKAY):
            logging.error("Failed to cleanly stop {name}".format(name=name))
        else:
            logging.info("Stopped {name} correctly".format(name=name))

def reload(name, **kwargs):
    """Stops a module, reloads, and then starts a module"""
    obj = module = None
    if (name in loaded_modules):
        obj, module = _loaded_modules[name]
    value = stop(name)
    if (module):
        module = _reload(module)
    value = load(name)
    return value