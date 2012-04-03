import manager as m
import irc
import watcher
import requests
import afkstreamer
import time
import listener
from multiprocessing.managers import BaseManager
import bootstrap
import config

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
            print "NO /main.mp3"
            # There is no /main.mp3 mountpoint right now
            # Create afk streamer
            if (self.streamer.connected):
                print "Streamer is already up"
                # The streamer is already up? but no mountpoint?
                # close it
                self.streamer.shutdown(force=True)
                # are we switching DJ?
                if (not self.switching):
                    print "trying to connect"
                    self.streamer.connect()
            else:
                # no streamer up, and no mountpoint
                print "Streamer isn't up"
                if (not self.switching):
                    print "Trying connection"
                    self.streamer.connect()
        elif (not self.streamer.connected):
            print "there is a DJ streaming?"
            # No streamer is active, there is a DJ streaming
            if (not self.listener):
                print "Listener not here, creating it"
                # There is no listener active, create one
                self.listener = listener.start()
            elif (not self.listener.active):
                # The listener died restart it
                print "listener died, creating a new one"
                self.listener.shutdown()
                self.listener = listener.start()
                    
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
    manager = StreamManager(address=config.manager_stream, authkey=config.authkey)
    manager.start()
    global _unrelated_
    _unrelated_ = manager.Stream()
    return manager

def main():
    # Start IRC server
    irc.launch_server()
        
    # Start listener/streamer
    launch_server()
    
    # Start queue watcher ? why is this even in hanyuu
    watcher.start()
    
    # Start request server
    #requests.launch_server()
    
if __name__ == "__main__":
    main()