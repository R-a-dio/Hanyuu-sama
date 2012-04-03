import pyices
import logging
import bootstrap
import manager
    
class Streamer(object):
    """Streamer class that streams to a certain server and mountpoint specified
    with attributes which is a dictionary of ... attributes.
    """
    __metaclass__ = bootstrap.Singleton
    def __init__(self, attributes):
        object.__init__(self)
        self.instance = None
        self.attributes = attributes
        
        self.finish_shutdown = False
        
    def __del__(self):
        self.shutdown(force=True)
    @property
    def connected(self):
        return self.instance.connected()
    def connect(self):
        self.queue = manager.Queue()
        self.finish_shutdown = False
        self.instance = pyices.instance(self.attributes,
                                        file_method=self.supply_song)
        
    def shutdown(self, force=False):
        """Shuts down the AFK streamer and process"""
        if force:
            self.instance.close()
            logging.info("Stopped AFK Streamer")
        else:
            self.finish_shutdown = True
            logging.info("Tried stopping AFK Streamer")
        
    def supply_song(self):
        # check for shutdown
        if (self.finish_shutdown):
            self.shutdown(force=True)
            
        self.queue.clear_pops()
        song = self.queue.pop()
        if (song.id == 0L):
            self.queue.clear()
            song = self.queue.pop()
        # update now playing
        manager.NP.change(song)
        
        return (song.filename, song.metadata)