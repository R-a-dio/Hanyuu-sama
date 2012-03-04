import bootstrap
import config
import logging

def main():
    bootstrap.start()
    # First the manager to start up the status thread and other functionality
    bootstrap.controller.load("manager")
    # We can now safely import manager here
    # get IRC ready

    bootstrap.controller.load("irc")
    import time
    time.sleep(1)
    import irc
    while (not hasattr(irc, "session")):
        time.sleep(0.1)
    irc.session.wait(timeout=30)
    bootstrap.controller.load("requests")
    bootstrap.controller.load("watcher")
    
if __name__ == "__main__":
    main()