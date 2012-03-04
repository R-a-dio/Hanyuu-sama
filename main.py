import bootstrap
import config
import logging

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
    # get IRC ready
    bootstrap.load("irc")
    import irc
    irc.session.wait(timeout=30)
    bootstrap.load("requests")
    bootstrap.load("watcher")
    
if __name__ == "__main__":
    main()