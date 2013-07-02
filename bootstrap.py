import config
import logging
import time
from raven.handlers.logging import SentryHandler
from raven.conf import setup_logging

logging.getLogger().setLevel(config.loglevel)

installed = ["irc", "manager", "requests_", "afkstreamer"]
if __name__ == "__main__":
    for module in installed:
        try:
            __import__(module).launch_server()
        except:
            logging.exception("Fucking loading broke, FIX YOUR SHIT")


def logging_setup():
    root = logging.getLogger()
    root.setLevel(config.loglevel)
    client = SentryHandler(config.sentry_key)
    setup_logging(client)


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


class Switch(object):

    def __init__(self, initial, timeout=15):
        object.__init__(self)
        self.state = initial
        self.timeout = time.time() + timeout

    def __nonzero__(self):
        return False if self.timeout <= time.time() else self.state

    def __bool__(self):
        return False if self.timeout <= time.time() else self.state

    def reset(self, timeout=15):
        self.timeout = time.time() + timeout
