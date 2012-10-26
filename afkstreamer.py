import logging
import threading
import audio

import manager
import bootstrap


logger = logging.getLogger('afkstreamer')


class Streamer(object):
    def __init__(self, attributes):
        super(Streamer, self).__init__()
        self.instance = None
        self.icecast_config = attributes
        
        self.close_at_end = threading.Event()
        
    @property
    def connected(self):
        try:
            return self.instance.connected()
        except (AttributeError):
            return False
        
    def connect(self):
        self.queue = manager.Queue()
        self.close_at_end.clear()
        
        self.instance = audio.Manager(self.icecast_config, self.supply_song)
        
    def shutdown(self, force=False):
        if force:
            self.instance.close()
            logger.info("Closed audio manager.")
        else:
            self.close_at_end.set()
            logger.info("Set close at end of song flag.")
            
    def supply_song(self):
        # check for shutdown
        if (self.close_at_end.is_set()):
            self.shutdown(force=True)
        else:
            try:
                song = self.queue.pop()
            except manager.QueueError:
                self.queue.clear_pops()
                return self.supply_song()
            else:
                if (song.id == 0L):
                    self.queue.clear()
                    song = self.queue.pop()
                self.queue.clear_pops()
                # update now playing
                manager.NP.change(song)
                
                return (song.filename, song.metadata)
        return (None, None)