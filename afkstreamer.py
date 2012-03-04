import pyices
import logging
import config
import manager
from multiprocessing import Queue, Process
from threading import Thread
from Queue import Empty

def start(state):
    global streamer, queue
    if (state):
        queue = state
    else:
        queue = manager.get_queue()
    streamer = Streamer(config.icecast_attributes(), queue)
    return streamer

class Streamer(Process):
    """Streamer class that streams to a certain server and mountpoint specified
    with attributes which is a dictionary of ... attributes.
    """
    def __init__(self, attributes, queue):
        Process.__init__(self)
        self._queue = queue # Get our queue before we start
        self._instance = None
        self.attributes = attributes
        self._shutdown = Queue()
        self.finish_shutdown = False
        self.start()
        
    def run(self):
        # Tell the manager module to use the queue from earlier
        import bootstrap
        bootstrap.get_logger("AFKStreamer") # Set logger
        manager.use_queue(self._queue)
        self.connect()
        force = self._shutdown.get()
        if (force):
            self._instance.close()
            self.finish_shutdown = True
            try:
                self._shutdown.get(block=False)
            except Empty:
                pass
        else:
            self.finish_shutdown = True
            self._shutdown.get()
            self._instance.close() # Clean up after we get back
            try:
                self._shutdown.get(block=False) # Empty the queue if there is any
            except Empty:
                pass
            
    def connect(self):
        self._playing = False
        instance = pyices.instance(self.attributes)
        self._instance = instance
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
        self._shutdown.put(force)
        self.join()
        return self._queue
            
    def on_disconnect(self, instance):
        """Handler for streamer disconnection"""
        manager.stream.down(manager.stream.STREAMER)
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
        self._playing = False
        if (self.finish_shutdown):
            self._shutdown.put(True)