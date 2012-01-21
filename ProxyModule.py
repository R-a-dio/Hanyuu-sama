import logging

loaded_modules = {}
loaded_proxies = {}
def get(name):
    if (loaded_modules.has_key(name)):
        return loaded_proxies[name]
    else:
        try:
            module = __import__(name)
        except (ImportError):
            logging.critical("Attempted module get: {name}".format(name))
            proxy = ProxyModule(None)
        else:
            proxy = ProxyModule(module)
            loaded_modules[name] = module
        loaded_proxies[name] = proxy
        return proxy
class ProxyModule(object):
    """Wraps around a module, so that the module can be reloaded without
    the user noticing this.
     
     """
    def __init__(self, module):
        self.__proxy_module = module
    def __getattr__(self, name):
        if (hasattr(self.__proxy_module, name)):
            return getattr(self.__proxy_module, name)
        else:
            return self.__proxy_dummyattr
    def __proxy_dummyattr(self, *args, **kwargs):
        pass