import logging

loaded_modules = {}
def get(name):
    if (loaded_modules.has_key(name)):
        return loaded_modules[name]
    else:
        try:
            module = __import__(name)
        except (ImportError):
            logging.critical("Attempted module get: {name}".format(name))
            return ProxyModule(None)
        return ProxyModule(module)

class ProxyModule:
    def __init__(self, module):
        self.__proxy_module = module
    def __getattr__(self, name):
        if (hasattr(self.__proxy_module, name)):
            return getattr(self.__proxy_module, name)
        else:
            return self.__proxy_dummyattr
    def __proxy_dummyattr(self, *args, **kwargs):
        pass