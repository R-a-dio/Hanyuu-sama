import pyices
import logging
import config
import manager
from multiprocessing import Queue, Process
from threading import Thread
from Queue import Empty

def start():
    global streamer
    streamer = Streamer(config.icecast_attributes)
    return streamer

class Streamer(Process):
    """Streamer class that streams to a certain server and mountpoint specified
    with attributes which is a dictionary of ... attributes.
    """
    def __init__(self, attributes):
        self._queue = manager.get_queue() # Get our queue before we start
        self._instance = None
        self.attributes = attributes
        self.connect()
        self._shutdown = Queue()
        self.finish_shutdown = False
        Thread(target=self.check_shutdown, args=(self._shutdown,)).start()
        self.start()
        
    def run(self):
        # Tell the manager module to use the queue from earlier
        manager.use_queue(self._queue)
    def connect(self, attributes):
        instance = pyices.instance(self.attributes)
        self._instance = instance
        instance.add_handle("disconnect", self.on_disconnect)
        instance.add_handle("start", self.on_start)
        instance.add_handle("finishing", self.on_finishing)
        instance.add_handle("finish", self.on_finish)
        
    def shutdown(self, force=False):
        """Shuts down the AFK streamer and process"""
        self._shutdown.put(force)
        self.join()
        
    def check_shutdown(self, shutdown):
        """Internal"""
        force = shutdown.get()
        if (force):
            self._instance.close()
            self.finish_shutdown = True
            try:
                shutdown.get(block=False)
            except Empty:
                pass
        else:
            self.finish_shutdown = True
            shutdown.get()
    def on_disconnect(self, instance):
        """Handler for streamer disconnection"""
        if (not self.finish_shutdown):
            self.connect()
    
    def on_start(self, instance):
        """Handler for when a file starts playing on the streamer"""
        # Update our now playing after last played
        manager.np.change(self._next_song)
    def on_finishing(self, instance):
        """Handler for when a file has been played for 90%"""
        song = manager.queue.pop()
        instance.add_file(song.filename, song.metadata)
        self._next_song = song
    def on_finish(self, instance):
        """Handler for when a file finishes playing completely"""
        if (self.finish_shutdown):
            instance.close()
            self._shutdown.put(True)