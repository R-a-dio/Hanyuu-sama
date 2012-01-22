#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm.util"

from collections import defaultdict
from decorator import decorator
from threading import Lock

_lock = Lock()

class Wormhole(object):
    _entrances = defaultdict(set)
    _exits = defaultdict(set)
    _enabled = False
    
    @staticmethod
    def disable():
        with _lock:
            Wormhole._enabled = False
        
    @staticmethod
    def enable():
        with _lock:
            Wormhole._enabled = True
    
    @staticmethod
    def add_entrance(topic, entrance):
        wrapped = Wormhole.entrance(topic)(entrance)
        wrapped._orginal = entrance
        return wrapped
    
    @staticmethod
    def add_exit(topic, exit):
        Wormhole._exits[topic].add(exit)
    
    @staticmethod
    def remove_entrance(topic, entrance):
        entrance = entrance._orginal
        if topic in Wormhole._entrances:
            if entrance in Wormhole._entrances[topic]:
                Wormhole._entrances[topic].remove(entrance)
        return entrance
    
    @staticmethod
    def remove_exit(topic, exit):
        if topic in Wormhole._exits:
            if exit in Wormhole._exits[topic]:
                Wormhole._exits[topic].remove(exit)
    
    @classmethod
    def entrance(cls, topic):
        @decorator
        def wrapper(func, *args, **kwargs):
            Wormhole._entrances[topic].add(func)
            retval = func(*args, **kwargs)
            if topic in Wormhole._exits:
                if Wormhole._enabled:
                    if func in Wormhole._entrances[topic]:
                        cls._jump(topic, retval, *args, **kwargs)
            return retval
        return wrapper
    
    @staticmethod
    def exit(topic):
        def wrapper(func):
            Wormhole._exits[topic].add(func)
            return func
        return wrapper
    
    @staticmethod
    def _jump(topic, retval, *args, **kwargs):
        exceptions = []
        for f in Wormhole._exits[topic]:
            try:
                f(retval, *args, **kwargs)
            except Exception as e:
                exceptions.append(e)
        for e in exceptions:
            raise e
        
class ThreadedWormhole(Wormhole):
    @staticmethod
    def _jump(topic, retval, *args, **kwargs):
        import threading
        for f in Wormhole._exits[topic]:
            threading.Thread(target = lambda: f(retval, *args, **kwargs)).start()