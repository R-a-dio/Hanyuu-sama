#!/usr/bin/python
# -*- coding: utf-8 -*-

import codecs
import MySQLdb as mysql
import MySQLdb.cursors
from time import time, strftime, gmtime
import re
from collections import deque
import urllib2
from random import randint
from config import music_directory, dbhost, dbuser, dbpassword as dbpass, dbtable as dbname, icecast_server, icecast_mountpoint
"""Module to handle all communication with the website, all data directed to the website
	should go through this module."""

class MySQLCursor:
	"""Return a connected MySQLdb cursor object"""
	def __init__(self, cursortype=mysql.cursors.DictCursor):
		self.conn = mysql.connect(host=dbhost, user=dbuser, passwd=dbpass, db=dbname,\
									charset='utf8', use_unicode=True)
		self.curtype = cursortype
	def __enter__(self):
		self.cur = self.conn.cursor(self.curtype)
		return self.cur
		
	def __exit__(self, type, value, traceback):
		self.cur.close()
		self.conn.commit()
		self.conn.close()
		return
def fetchgenerator(cursor):
	fetch = cursor.fetchone()
	while (fetch):
		yield fetch
		fetch = cursor.fetchone()
		
lastplayed = deque(["&nbsp;", "&nbsp;", "&nbsp;", "&nbsp;", "&nbsp;"], 5)
def fetch_lastplayed():
	with MySQLCursor() as cur:
		cur.execute("SELECT esong.meta FROM eplay JOIN esong ON esong.id = eplay.isong ORDER BY eplay.dt DESC LIMIT 5;")
		for result in cur:
			lastplayed.appendleft(result['meta'])
			
def send_nowplaying(np=None, djid=None, listeners=None, bitrate=None, is_afk=0, st_time=None, ed_time=None):
	#global np, djid, listeners, bitrate
	with MySQLCursor() as cur:
		changes = []
		if np != None:
			d = codecs.getencoder('utf-8')
			np = d(np, 'replace')[0]
			np = mysql.escape_string(np)
			changes.append("`np`='%s'" % (np))
		if djid != None:
			djid = mysql.escape_string(djid)
			changes.append("`djid`=%s" % (djid))
		if listeners != None:
			listeners = mysql.escape_string(listeners)
			changes.append("`listeners`=%s" % (listeners))
		if bitrate != None:
			bitrate = mysql.escape_string(bitrate)
			changes.append("`bitrate`=%s" % (bitrate))
		if st_time != None:
			changes.append("`start_time`=%d" % (st_time))
		if ed_time != None:
			changes.append("`end_time`=%d" % (ed_time))
		changes.append("`isafkstream`=%d" % (is_afk))
		cur.execute("SELECT * FROM `streamstatus`;")
		if cur.rowcount == 0:
				sdCheck = 0
		else:
				sdCheck = cur.fetchone()['isstreamdesk']
		if sdCheck == 1: # we can't interrupt streamdesk data
				return
		if cur.rowcount == 0:
				cur.execute("INSERT INTO `streamstatus` (lastset) VALUES (NOW());")
		imploded = ", ".join(changes)
		cur.execute("UPDATE `streamstatus` SET `lastset`=NOW(), %s WHERE `id`=0;" % (imploded))
		
queue = []
def send_queue(timeleft, _queue):
	global queue
	queue = ["&nbsp;", "&nbsp;", "&nbsp;", "&nbsp;", "&nbsp;"]
	with MySQLCursor() as cur:
		cur.execute("DELETE FROM `curqueue`;")
		start = time()
		contime = start + timeleft
		count = 0
		d = codecs.getencoder('utf-8')
		for length, item in _queue:
			midtime = contime
			item = d(item, 'replace')[0]
			cur.execute("INSERT INTO `curqueue` (timestr, track) VALUES (from_unixtime(%d), '%s');" % (midtime, mysql.escape_string(item)))
			contime += length
			if (count <= 4):
				queue[count] = item
				count += 1

def get_song(songid):
	"""Retrieve song path and metadata from the track ID"""
	with MySQLCursor() as cur:
		cur.execute("SELECT * FROM `tracks` WHERE `id`=%s LIMIT 1;" % (songid))
		if cur.rowcount == 1:
			row = cur.fetchone()
			artist = row['artist']
			title = row['track']
			path = "{0}/{1}".format(music_directory, row['path']) #omg it's absolute | hehe
			
			meta = title
			if artist != '':
				meta = artist + ' - ' + title
			
			#print "loading song '%s'" % (meta)
			return (path, meta)
		else:
			return None

class SongQueue:
	def __init__(self):
		self.__regular = deque()
		self.__request = deque()
		self.__get_requests()
		self.__fill()
	def pop(self):
		if (len(self.__request) > 0):
			result = self.__request.popleft()
		else:
			result = self.__regular.popleft()
		self.__fill()
		return result
	def add_request(self, id):
		if (self.has_reg(id)) and (not self.has_req(id)):
			self.del_regular(id)
		if (not self.has(id)):
			self.__request.append(id)
	def del_request(self, id):
		# DELETES ARE EXPENSIVE
		try:
			self.__request.remove(id)
		except (ValueError):
			pass
	def add_regular(self, id):
		if (not self.has(id)):
			self.__regular.append(id)
	def del_regular(self, id):
		# DELETES ARE EXPENSIVE
		try:
			self.__regular.remove(id)
		except (ValueError):
			pass
	def length(self):
		return len(self.__request) + len(self.__regular)
	def has(self, id):
		if (id in self.__request) or (id in self.__regular):
			return True
		return False
	def has_reg(self, id):
		return id in self.__regular
	def has_req(self, id):
		return id in self.__request
		
	def send_queue(self, timedur=0):
		# [(length, meta)]
		# We need to know the length somehow
		def song_info(id):
			from mutagen.mp3 import MP3
			path, meta = get_song(id)
			try:
				file = MP3(path)
				length = file.info.length
			except:
				length = 0
			return (length, meta)
		ids = list(self.__request)
		ids.extend(list(self.__regular))
		# WE ONLY GOT IDs!!!! need to resolve them
		songs = []
		for id in ids:
			length, meta = song_info(id)
			songs.append((length, meta))
		send_queue(timedur, songs)
	def clean_requests(self):
		with MySQLCursor() as cur:
			for req in self.__request:
				cur.execute("INSERT INTO `requests` (`trackid`, `ip`) VALUES \
						('{trackid}', '0.0.0.0')".format(trackid=req))
	def set_lastplayed(self, id):
		with MySQLCursor() as cur:
			cur.execute("UPDATE `tracks` SET `lastplayed`=NOW() WHERE `id`=%s LIMIT 1;" % (id))
	def __fill(self):
		self.__get_requests()
		if (self.length() < 20):
			self.__get_items(20 - self.length())
	def __get_items(self,amount):
		with MySQLCursor() as cur:
			for n in xrange(amount):
				cur.execute("SELECT * FROM `tracks` WHERE `usable`=1 ORDER BY `lastplayed` ASC, `lastrequested` ASC LIMIT 100;")
				while(1):
					pos = randint(0, 99)
					cur.scroll(pos, 'absolute')
					result = cur.fetchone()
					if (result):
						sid = int(result['id'])
					else:
						continue
					if not self.has(sid):
						break
				self.add_regular(sid)
	def __get_requests(self):
		with MySQLCursor() as cur:
			cur.execute("SELECT trackid FROM `requests` ORDER BY `time` ASC;")
			for row in fetchgenerator(cur):
				self.add_request(int(row['trackid']))
			cur.execute("DELETE FROM `requests`;")
djid = '0'
def get_djid(username):
	global djid
	if (not username):
		djid = '0'
	with MySQLCursor() as cur:
		username = mysql.escape_string(username)
		query = "SELECT `djid` FROM `users` WHERE `user`='%s' LIMIT 1;" % (username)
		cur.execute(query)
		if cur.rowcount > 0:
			djid = cur.fetchone()['djid']
			if djid != None:
					djid = str(djid)
			else:
					djid = '0'
		else:
			djid = '0'
	return djid
	
regex_mountstatus = re.compile(r"<td><h3>Mount Point (.*)</h3></td>")
def get_mountstatus(mount="/{0}".format(icecast_mountpoint)):
	try:
		req = urllib2.Request(icecast_server, headers={'User-Agent': 'Mozilla'})
		c = urllib2.urlopen(req)
		next = ''
		for line in c:
			result = regex_mountstatus.match(line)
			if (not result):
				continue
			else:
				if (result.groups()[0] == mount):
						return True
		return False
	except:
		return False

def get_faves(nick):
	"""Return list of titles that are faved"""
	with MySQLCursor as cur:
		meta = []
		query = "SELECT esong.meta FROM enick,efave,esong WHERE enick.id = efave.inick AND efave.isong = esong.id AND enick.nick = '{nick}';"
		cur.execute(query.format(nick=mysql.escape_string(nick)))
		with fetchgenerator(cur) as result:
			meta.append(result['meta'])
		return meta

hash_row_tracker = {}
hash_faves = []
def get_hash(digest):
	"""Return playcount, length, lastplayed, favorites
	
		playcount int (count)
		length int (seconds)
		lastplayed int (unixtime)
		fave list (nicks)
	
	"""
	global hash_row_tracker, hash_faves
	with MySQLCursor() as cur:
		playcount = length = lastplayed = 0
		fave = []
		# Length first
		query = "SELECT len FROM `esong` WHERE `hash`='{digest}';"
		cur.execute(query.format(digest=digest))
		if (cur.rowcount > 0):
			hash_row_tracker.update({digest:True})
			length = cur.fetchone()['len']
			# last played
			query = "SELECT unix_timestamp(`dt`) AS ut FROM eplay,esong WHERE eplay.isong = esong.id AND esong.hash = '{digest}' ORDER BY `dt` DESC LIMIT 1;"
			cur.execute(query.format(digest=digest))
			lastplayed = cur.fetchone()['ut']
			# playcount
			query = "SELECT count(*) playcount FROM eplay,esong where eplay.isong = esong.id AND esong.hash = '{digest}';"
			cur.execute(query.format(digest=digest))
			playcount = cur.fetchone()['playcount']
			# faves
			query = "SELECT enick.nick FROM enick,efave,esong WHERE enick.id = efave.inick AND efave.isong = esong.id AND esong.hash = '{digest}';"
			cur.execute(query.format(digest=digest))
			for result in cur:
				fave.append(result['nick'])
		else:
			hash_row_tracker.update({digest:False})
		hash_faves = list(fave)
		return (playcount, length, lastplayed, fave)
		
def get_hash_old(digest):
	"""Return playcount, length, lastplayed and favorites with hash"""
	global hash_row_tracker
	print(get_hash_new(digest))
	with MySQLCursor() as cur:
		playcount = length = lastplayed = 0
		fave = []
		cur.execute("SELECT * FROM `streamsongs` WHERE `hash`='%s' LIMIT 1;" % (digest))
		if (cur.rowcount > 0):
			hash_row_tracker.update({digest:True})
			result = cur.fetchone()
			playcount = result['playcount']
			length = result['length']
			lastplayed = result['lastplayed']
			fave = result['fave']
			if (fave == ''):
				fave = []
			else:
				fave = fave.split('!')
		else:
			hash_row_tracker.update({digest:False})
		return (playcount, length, lastplayed, fave)
		
def send_hash(digest, title, length, lastplayed, fave):
	global hash_row_tracker, hash_faves
	if (digest not in hash_row_tracker):
		return
	else:
		with MySQLCursor() as cur:
			digest = mysql.escape_string(digest)
			title = mysql.escape_string(title.encode('utf-8', 'replace'))
			if (not hash_row_tracker[digest]):
				# Create song entry
				cur.execute("INSERT INTO esong VALUES('', '{hash}', {len}, '{title}');".format(hash=digest, title=title, len=length))
			# Get songid
			cur.execute("SELECT id FROM esong WHERE hash='{hash}'".format(hash=digest))
			songid = cur.fetchone()['id']
			
			# last played
			cur.execute("INSERT INTO eplay VALUES('', {songid}, FROM_UNIXTIME({lp}));".format(songid=songid, lp=lastplayed))
			print fave
			print hash_faves
			for nick in fave:
				print nick
				if (nick not in hash_faves):
					nick = mysql.escape_string(nick)
					cur.execute("SELECT * FROM enick WHERE nick='{nick}';".format(nick=nick))
					print cur.rowcount
					if (cur.rowcount == 0):
						cur.execute("INSERT INTO enick VALUES('', '{nick}', '', '');".format(nick=nick))
						cur.execute("SELECT * FROM enick WHERE nick='{nick}';".format(nick=nick))
						cur.execute("INSERT INTO efave VALUES('', {nickid}, {songid});".format(nickid=nickid, songid=songid))
					elif (cur.rowcount == 1):
						nickid = cur.fetchone()['id']
						cur.execute("INSERT INTO efave VALUES('', {nickid}, {songid});".format(nickid=nickid, songid=songid))
			del hash_row_tracker[digest]
			
def send_hash_old(digest, title, playcount, length, lastplayed, fave):
	global hash_row_tracker
	print(send_hash_new(digest, title, length, lastplayed, fave))
	with MySQLCursor() as cur:
		if (digest not in hash_row_tracker):
			return
		else:
			if (hash_row_tracker[digest]):
				query = "UPDATE `streamsongs` SET `title`='{title}', \
						`playcount`={playcount}, `length`={length}, `lastplayed`={lastplayed}, \
						`fave`='{fave}' WHERE `hash`='{digest}';"
			else:
				query = "INSERT INTO `streamsongs` (`hash`, `title`, `playcount`,\
						`length`, `lastplayed`, `fave`) VALUES \
						('{digest}', '{title}', {playcount}, {length}, {lastplayed}, '{fave}');"
			del hash_row_tracker[digest]
			digest = mysql.escape_string(digest)
			fave = mysql.escape_string("!".join(fave))
			#exclamation mark bug fix
			if(len(fave) > 0 and fave[:1] == "!"):
				fave = fave[1:]
			title = mysql.escape_string(codecs.getencoder('utf-8')(title, 'replace')[0])
			cur.execute(query.format(digest=digest, title=title, fave=fave, playcount=playcount,\
									length=length, lastplayed=lastplayed))
									
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
