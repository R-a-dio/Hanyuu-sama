from __future__ import absolute_import
import threading
import time
import logging

from .status import Status

def start_updater():
    global updater_event, updater_thread
    updater_event = threading.Event()
    updater_thread = threading.Thread(name="Streamstatus Updater",
                            target=updater,
                            args=(updater_event,))
    updater_thread.daemon = 1
    updater_thread.start()


def updater(event):
    logging.info("THREADING: Starting now playing updater")
    status = Status()
    while not event.is_set():
        if (status.online):
            status.update()
        time.sleep(10)
    logging.info("THREADING: Stopping now playing updater")


def stop_updater():
    updater_event.set()
    updater_thread.join(11)
