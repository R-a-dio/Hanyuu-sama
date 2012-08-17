import manager as m
import irc
import watcher
import afkstreamer
import time
import listener
from multiprocessing.managers import BaseManager
import bootstrap
import config
import logging

class Switch(object):
    def __init__(self, initial, timeout=15):
        object.__init__(self)
        self.state = initial
        self.timeout = time.time() + timeout
    def __nonzero__(self):
        return False if self.timeout <= time.time() else self.state
    def __bool__(self):
        return False if self.timeout <= time.time() else self.state
    
class StatusUpdate(object):
    __metaclass__ = bootstrap.Singleton
    def __init__(self):
        object.__init__(self)
        
        # Start streamstatus updater
        m.start_updater()
        
        self.mode = None
        
        self.status = m.Status()
        self.status.add_handler(self)
        self.streamer = afkstreamer.Streamer(config.icecast_attributes())
        self.listener = None
        self.switching = False
    def switch_dj(self, force=False):
        if (force):
            self.switching = Switch(True)
        else:
            np = m.NP()
            self.switching = Switch(True, (np.length - np.position) + 15)
        # Call shutdown
        self.streamer.shutdown(force)
    def __call__(self, info):
        if ("/main.mp3" not in info):
            self.debug("No /main.mp3 mountpoint found.")
            # There is no /main.mp3 mountpoint right now
            # Create afk streamer
            if (self.streamer.connected):
                self.debug("Streamer is already connected")
                # The streamer is already up? but no mountpoint?
                # close it
                self.streamer.shutdown(force=True)
                # are we switching DJ?
                if (not self.switching):
                    self.debug("Streamer trying to reconnect")
                    self.streamer.connect()
            else:
                # no streamer up, and no mountpoint
                self.debug("Streamer is not connected")
                if (not self.switching):
                    logging.debug("Streaming trying to connect")
                    self.streamer.connect()
        elif (not self.streamer.connected):
            self.debug("We have a /main.mp3 mountpoint and no streamer, must be DJ")
            # No streamer is active, there is a DJ streaming
            if (not self.listener):
                self.debug("Listener isn't active, starting it")
                # There is no listener active, create one
                self.listener = listener.start()
            elif (not self.listener.active):
                # The listener died restart it
                self.debug("Listener isn't active anymore, restarting it")
                self.listener.shutdown()
                self.listener = listener.start()
    def debug(self, mode):
        if mode != self.mode:
            self.mode = mode
            logging.debug(mode)
class StreamManager(BaseManager):
    pass

StreamManager.register("stats", bootstrap.stats)
StreamManager.register("Stream", StatusUpdate)

def connect():
    global manager, stream
    manager = StreamManager(address=config.manager_stream, authkey=config.authkey)
    manager.connect()
    stream = manager.Stream()
    return stream

def start():
    s = StatusUpdate()
    manager = StreamManager(address=config.manager_stream, authkey=config.authkey)
    server = manager.get_server()
    server.serve_forever()
    
def launch_server():
    import os
    try:
        os.remove('/tmp/hanyuu_stream')
    except:
        pass
    manager = StreamManager(address=config.manager_stream, authkey=config.authkey)
    manager.start()
    global _unrelated_
    _unrelated_ = manager.Stream()
    return manager

def main():
    # Start IRC server
    #irc.launch_server()
        
    # Start listener/streamer
    global manager
    manager = launch_server()
    
    # Start queue watcher ? why is this even in hanyuu
    watcher.start()
    
    # Start request server
    #requests.launch_server()
    
if __name__ == "__main__":
    main()