#!/usr/bin/python

import pyinotify as pi
import webcom
import time
import config
from os import path

def start_watcher():
	global notifier
	wm = pi.WatchManager()
	notifier = pi.ThreadedNotifier(wm, handler())
	notifier.start()
	wdd = wm.add_watch(config.watcher_path, pi.IN_MODIFY)
	
def stop_watcher():
	notifier.stop()
def parse_queue_file():
	with web.MySQLCursor() as cur:
		queue = []
		remaining = 0
		with open(path.join(config.watcher_path, config.watcher_file)) as file:
			djid = file.readline().strip()
			firstline = file.readline().strip()
			
			if (djid != ''):
				remaining = int(firstline)
				current_djid = webcom.get_djid()
				if (current_djid == djid):
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
						
						song = webcom.fix_encoding(song)
						queue.append((stime, song))
		if (len(queue) > 0):
			webcom.send_queue(remaining, queue)
			
class handler(object, pi.ProcessEvent):
	def process_IN_MODIFY(self, event):
		if (event.name == 'queue.txt'):
			parse_queue_file()

