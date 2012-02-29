#!/usr/bin/python
# -*- coding: utf-8 -*-

import codecs
import MySQLdb as mysql
import MySQLdb.cursors
from time import time
import re
from collections import deque
import urllib2
from random import randint
from hashlib import sha1
import config
"""Module to handle all communication with the website, all data directed to the website
	should go through this module."""

class MySQLCursor:
	"""Return a connected MySQLdb cursor object"""
	def __init__(self, cursortype=mysql.cursors.DictCursor, lock=None):
		self.conn = mysql.connect(host=config.dbhost,
								user=config.dbuser,
								passwd=config.dbpassword,
								db=config.dbtable,
								charset='utf8',
								use_unicode=True)
		self.curtype = cursortype
		self.lock = lock
	def __enter__(self):
		if (self.lock != None):
			self.lock.acquire()
		self.cur = self.conn.cursor(self.curtype)
		self.cur.escape_string = mysql.escape_string
		return self.cur
		
	def __exit__(self, type, value, traceback):
		self.cur.close()
		self.conn.commit()
		self.conn.close()
		if (self.lock != None):
			self.lock.release()
		return
		
def nick_request_song(songid, host=None):
	"""Gets data about the specified song, for the specified hostmask.
	If the song didn't exist, it returns 1.
	If the host needs to wait before requesting, it returns 2.
	If there is no ongoing afk stream, it returns 3.
	Else, it returns (artist, title).
	"""
	with MySQLCursor() as cur:
		can_request = True
		if host:
			host = mysql.escape_string(host)
			cur.execute("SELECT UNIX_TIMESTAMP(time) as timestamp FROM `nickrequesttime` WHERE `host`='{host}' LIMIT 1;".format(host=host))
			if cur.rowcount == 1:
				row = cur.fetchone()
				if int(time.time()) - int(row['timestamp']) < 1800:
					can_request = False
		
		can_afk = True
		cur.execute("SELECT isafkstream FROM `streamstatus`;")
		if cur.rowcount == 1:
			row = cur.fetchone()
			afk = row['isafkstream']
			if not afk == 1:
				can_afk = False
		else:
			can_afk = False
		if (not can_request):
			return 2
		if (not can_afk):
			return 3
		cur.execute("SELECT * FROM `tracks` WHERE `id`={id};".format(id=songid))
		if (cur.rowcount == 1):
			row = cur.fetchone()
			artist = row['artist']
			title = row['track']
			return (artist, title)
		return 1

def send_curthread(url):
	with MySQLCursor() as cur:
		url = mysql.escape_string(url)
		query = "UPDATE `radvars` SET `value`='%s' WHERE `name`='curthread' LIMIT 1;" % (url)
		cur.execute(query)

def get_curthread():
	with MySQLCursor() as cur:
		query = "SELECT `value` FROM `radvars` WHERE `name`='curthread' LIMIT 1;"
		cur.execute(query)
		return cur.fetchone()['value']