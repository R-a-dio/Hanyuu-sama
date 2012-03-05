def main():
    import bootstrap
    controller = bootstrap.Controller()
    # First the manager to start up the status thread and other functionality
    controller.load("manager")
    # We can now safely import manager here
    # get IRC ready

    controller.load("irc")
    import time
    time.sleep(1)
    import irc
    while (not hasattr(irc, "session")):
        time.sleep(0.1)
    irc.session.wait(timeout=30)
    controller.load("requests")
    controller.load("watcher")
    
    # Get ready to make our interpreter
    import code
    try:
        say = lambda text: controller.get("irc").server.privmsg("#r/a/dio", text)
    except (AttributeError):
        say = lambda text: "IRC Failed to initialize"
    int_local = {"controller": controller,
              "irc": controller.get("irc"),
              "manager": controller.get("manager"),
              'say': say,
              'stats': controller.stats,
              'shutdown': controller.shutdown
              }
    code.InteractiveConsole(int_local)\
        .interact("Welcome to the Hanyuu console"
                  " , the following variables are"
                  " defined for your convenience:"
                  "\n\n\t'irc': the irc.Session object"
                  "\n\t'manager': the manager module"
                  "\n\t'controller': the bootstrap.Controller object"
                  "\n\n\t'say': Talk in #r/a/dio channel"
                  "\n\t'stats': Returns a small overview of the current state"
                  "\n\t'shutdown': Tries to shut down everything")
if __name__ == "__main__":
    main()