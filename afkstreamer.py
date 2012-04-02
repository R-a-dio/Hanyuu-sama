import pyices
import logging
import config
import bootstrap
from manager import manager
from multiprocessing.managers import BaseManager

    
class Streamer(object):
    """Streamer class that streams to a certain server and mountpoint specified
    with attributes which is a dictionary of ... attributes.
    """
    __metaclass__ = bootstrap.Singleton
    def __init__(self, attributes):
        object.__init__(self)
        self.name = "AFK Streamer"
        self.instance = None
        self.attributes = attributes
        
        self.finish_shutdown = False
        logging.info("PROCESS: Started AFK Streamer")
        self.connect()
        
    def __del__(self):
        self.shutdown(force=True)
        
    def connect(self):
        self._playing = False
        instance = pyices.instance(self.attributes)
        self.instance = instance
        instance.add_handle("disconnect", self.on_disconnect)
        instance.add_handle("start", self.on_start)
        instance.add_handle("finishing", self.on_finishing)
        instance.add_handle("finish", self.on_finish)
        song = manager.queue.pop()
        if (song.id == 0L):
            manager.queue.clear()
            song = manager.queue.pop()
        self._next_song = song
        instance.add_file(song.filename, song.metadata)
        manager.stream.up(manager.stream.STREAMER)
        
    def shutdown(self, force=False):
        """Shuts down the AFK streamer and process"""
        if force:
            self.instance.close()
        else:
            self.finish_shutdown = True
        logging.info("PROCESS: Stopped AFK Streamer")
        
    def on_disconnect(self, instance):
        """Handler for streamer disconnection"""
        self._playing = False
    
    def on_start(self, instance):
        """Handler for when a file starts playing on the streamer"""
        # Update our now playing after last played
        self._playing = True
        manager.np.change(self._next_song)
        
    def on_finishing(self, instance):
        """Handler for when a file has been played for 90%"""
        song = manager.queue.pop()
        instance.add_file(song.filename, song.metadata)
        self._next_song = song
        
    def on_finish(self, instance):
        """Handler for when a file finishes playing completely"""
        manager.queue.clear_pops()
        self._playing = False
        if (self.finish_shutdown):
            self.shutdown(force=True)
            
class StreamerManager(BaseManager):
    pass

StreamerManager.register("stats", bootstrap.stats)
StreamerManager.register("streamer", Streamer)