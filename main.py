import bootstrap
import config
import logging

def main():
    bootstrap.start()
    # First the manager to start up the status thread and other functionality
    bootstrap.controller.load("manager")
    # We can now safely import manager here
    # get IRC ready
    bootstrap.controller.load("requests")
    bootstrap.controller.load("watcher")
    bootstrap.controller.load("irc")
    
if __name__ == "__main__":
    main()