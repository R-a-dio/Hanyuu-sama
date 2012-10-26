import threading
import logging
import time


logger = logging.getLogger('garbage')


class Singleton(type):
    def __init__(mcs, name, bases, dict):
        super(Singleton, mcs).__init__(name, bases, dict)
        mcs.instance = None

    def __call__(mcs, *args, **kw):
        if mcs.instance is None:
            mcs.instance = super(Singleton, mcs).__call__(*args, **kw)
        return mcs.instance
    
    
class Collector(object):
    __metaclass__ = Singleton
    def __init__(self):
        super(Collector, self).__init__()
        self.items = set()
        
        self.collecting = threading.Event()
        self.thread = threading.Thread(target=self.run,
                                       name="Garbage Collection Thread")
        self.thread.daemon = True
        self.thread.start()
        
    def add(self, garbage):
        self.items.add(garbage)
        
    def run(self):
        while not self.collecting.is_set():
            removal = set()
            for item in self.items:
                try:
                    code = item.collect() # Try collecting
                except:
                    logger.exception("Collection Failure.")
                else:
                    if code: # If it returned True it was successful
                        removal.add(item)
            self.items -= removal # We remove our set from the item one
            time.sleep(15.0)
            
    def info(self):
        """Returns a list of GarbageInfo objects containing information
        about current pending garbage."""
        yield None # Not implemented
        
        
class Garbage(object):
    collector = Collector()
    def __init__(self, item=None):
        super(Garbage, self).__init__()
        self.item = item
        self.collector.add(self)
        
    def collect(self):
        """Gets called on each collection cycle. 
        
        Should return True if the garbage got cleaned up properly,
        False if it requires another collect in the next cycle.
        """
        raise NotImplementedError("collect method not overridden.")