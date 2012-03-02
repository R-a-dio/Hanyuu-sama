import bootstrap
import config
import logging

LISTENER = 0
STATUS = 1
STREAMER = 2

DOWN = False
UP = True
INIT = 0
stream_status = INIT
loaded_status = {}

def stream_up_handler(reporter):
    global stream_status
    if (stream_status == INIT):
        stream_status = UP
        logging.info("Starting listener, INIT")
        bootstrap.load("listener")
        loaded_status['listener'] = True
    elif (not stream_status):
        # we have it as down
        if (reporter == STREAMER):
            stream_status = UP
        elif (reporter == STATUS):
            if (not loaded_status.get('afkstreamer', False)) \
                    and (not loaded_status.get('listener', False)):
                logging.info("Starting listener, neither online")
                bootstrap.load('listener')
                
def stream_down_handler(reporter):
    global stream_status
    if (stream_status == INIT):
        stream_status = DOWN
        logging.info("Starting streamer INIT")
        bootstrap.load("afkstreamer")
        loaded_status['afkstreamer'] = True
    elif (not stream_status):
        if (reporter == STATUS):
            if (loaded_status.get('afkstreamer', False)):
                logging.info("Loading streamer STATUS")
                bootstrap.load('afkstreamer')
                loaded_status['afkstreamer'] = True
            else:
                logging.info("Reloading streaming STATUS")
                bootstrap.stop('afkstreamer')
                bootstrap.load('afkstreamer')
                loaded_status['afkstreamer'] = True
        
def main():
    modules = ["manager",
               "listener",
               "afkstreamer",
               "watcher",
               "requests",
               "irc",
               "hanyuu_commands",
               "config"]
    # First the manager to start up the status thread and other functionality
    bootstrap.load("manager")
    # We can now safely import manager here
    import manager
    manager.stream.add_handle(manager.stream.UP, stream_up_handler)
    manager.stream.add_handle(manager.stream.DOWN, stream_down_handler)
    # get IRC ready
    bootstrap.load("irc")
    import irc
    irc.session.wait(timeout=30)
    bootstrap.load("requests")
    bootstrap.load("watcher")
    
if __name__ == "__main__":
    main()