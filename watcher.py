#!/usr/bin/python

import pyinotify as pi
import webcom as web
import time
import __main__
import config

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
		timedur = 0
		with open(config.watcher_path + '/queue.txt') as file:
			djid = file.readline().strip()
			if (djid != ''):
				if (__main__.shout.djid == djid):
					firstline = file.readline().strip()
					
					timedur = int(firstline)
					timedur = timedur + int(time.time())
					
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
						
						song = __main__.shoutmain.fix_encoding(song)
						queue.append((stime, song))
		print queue
		if (len(queue) > 0):
			web.send_queue(timedur, queue)
			
class handler(pi.ProcessEvent):
	def process_IN_MODIFY(self, event):
		if (event.name == 'queue.txt'):
			parse_queue_file()

