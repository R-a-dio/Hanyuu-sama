#!/usr/bin/python
import logging
import pyinotify as pi
import config
import manager
from os import path

def start(state):
    global notifier
    wm = pi.WatchManager()
    notifier = pi.ThreadedNotifier(wm, handler())
    notifier.name = "Queue Watcher"
    notifier.start()
    wdd = wm.add_watch(config.watcher_path, pi.IN_MODIFY)
    
def shutdown():
    notifier.stop()
    return None

def parse_queue_file():
    queue = []
    remaining = 0
    with open(path.join(config.watcher_path, config.watcher_file)) as file:
        djid = file.readline().strip()
        firstline = file.readline().strip()
        
        if (djid != ''):
            remaining = int(firstline)
            try:
                djid = int(djid)
            except ValueError:
                djid = None
            if (manager.DJ().id == djid):
                for line in file:
                    line = line.strip()
                    if line == "":
                        continue
                    
                    try:
                        spacepos = line.index(' ')
                    except:
                        continue
                    stime = int(line[:spacepos])
                    song = line[spacepos+1:]
                    
                    queue.append(manager.Song(meta=song, length=stime))
            else:
                logging.info("Queue discarded because djid {id} does not match".format(id=djid))
    if (len(queue) > 0):
        _queue = manager.Queue()
        _queue.clear()
        manager.NP().remaining(remaining)
        _queue.append_many(queue)
        try:
            logging.info("Finished queue from {name}".format(name=manager.DJ().name))
        except:
            logging.info("Finished queue update by Unknown")
            
class handler(pi.ProcessEvent):
    def process_IN_MODIFY(self, event):
        if (event.name == 'queue.txt'):
            try:
                parse_queue_file()
            except:
                logging.exception("Problem parsing the queue file")
