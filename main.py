#!/usr/bin/python
# -*- coding: utf-8 -*-

_profile_app = False
import irc
import shoutmain
import re
import webcom
import watcher
import time
import threading
import config
	
def main_start():
	global shout, main
	hy = HanyuuHandlers()
	# IRC part
	print("Starting AlternativeMainLoop")
	main = AlternativeMainLoop()
	# Setup AFK Streamer and Stream Listener
	time.sleep(15)
	print("Starting StreamInstance")
	shout = shoutmain.StreamInstance()
	# Queue watcher
	print("Starting watcher")
	watcher.start_watcher()
	print "FCGI Server Starting"
	WSGIServer(external_request, bindAddress='/tmp/fastcgi.pywessie.sock',umask=0).run()
		
if __name__ == '__main__':
	main_start()
