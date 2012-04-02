import config
import logging

logging.getLogger().setLevel(config.loglevel)
    
installed = ["irc", "manager", "requests", "afkstreamer"]
if __name__ == "__main__":
    for module in installed:
        try:
            __import__(module).launch_server()
        except:
            logging.exception("Fucking loading broke, FIX YOUR SHIT")
            
def logging_setup():
    logging.getLogger().setLevel(config.loglevel)
    
def stats():
    """Returns information about the process"""
    from threading import active_count, enumerate
    try:
        threads = active_count()
        names = [(thread.name, hex(id(thread))) for thread in enumerate()]
    except:
        threads = 0
        names = []
    return (names, threads)

class Singleton(type):
    def __init__(mcs, name, bases, dict):
        super(Singleton, mcs).__init__(name, bases, dict)
        mcs.instance = None

    def __call__(mcs, *args, **kw):
        if mcs.instance is None:
            mcs.instance = super(Singleton, mcs).__call__(*args, **kw)
        return mcs.instance
