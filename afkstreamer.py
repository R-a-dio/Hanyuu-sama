import pyices
import logging
import config
import updater
import webcom

def afkstreamer(attributes, queue):
    return pyices.instance(attributes)

class Streamer(object):
    """Streamer class that streams to a certain server and mountpoint specified
    with attributes which is a dictionary of ... attributes.
    """
    def __init__(self, attributes):
        instance = pyices.instance(attributes)
        self._instance = instance
        instance.add_handle("disconnect", self.on_disconnect)
        instance.add_handle("start", self.on_start)
        instance.add_handle("finishing", self.on_finishing)
        instance.add_handle("finish", self.on_finish)
        
    def on_disconnect(self, instance):
        """Handler for streamer disconnection"""
        pass
    
    def on_start(self, instance):
        """Handler for when a file starts playing on the streamer"""
        # Update last played before updating now playing
        updater.lp.update(id=updater.np.id, digest=updater.np.digest,
                          title=updater.np.title, length=updater.np.length,
                          lastplayed=None)
        # Update our now playing after last played
        updater.np.update(*self._info_next)
    def on_finishing(self, instance):
        """Handler for when a file has been played for 90%"""
        sid, meta, length = updater.queue.pop()
        file = webcom.get_song(sid)[0]
        instance.add_file(file, meta)
        self._info_next = (sid, digest, meta)
    def on_finish(self, instance):
        """Handler for when a file finishes playing completely"""
        pass