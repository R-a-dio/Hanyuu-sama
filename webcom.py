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

def save_request(trackid, ip="0.0.0.0"):
	"""Puts a request into the MySQL requests table"""
	with MySQLCursor() as cur:
		cur.execute("INSERT INTO `requests` (`trackid`, `ip`) VALUES ('{trackid}', '{ip}');".format(trackid=trackid, ip=ip))
def update_lastplayed(id):
	"""Changes the lastplayed of `id` to current time"""
	with MySQLCursor() as cur:
		cur.execute("UPDATE `tracks` SET `lastplayed`=NOW() WHERE `id`=%s LIMIT 1;" % (id))
def get_request_tracks():
	""""Gets all saved requests in the `requests` table"""
	with MySQLCursor() as cur:
		cur.execute("SELECT trackid FROM `requests` ORDER BY `time` ASC;")
		for row in cur:
			yield int(row['trackid'])
		cur.execute("DELETE FROM `requests`;")
def get_random_tracks(amount=1, func=lambda x: False):
	"""Gets `amount` of tracks from the `tracks` table
		func has to be a function to check if the ID is
		allowed to be returned.
		
		if func returns False the ID will be given
		else if func returns True the ID is purged
		
		Default is to give all IDs
		
		returns a generator"""
	with MySQLCursor() as cur:
		for n in xrange(amount):
			cur.execute("SELECT * FROM `tracks` WHERE `usable`=1 ORDER BY `lastplayed` ASC, `lastrequested` ASC LIMIT 100;")
			while(1):
				sid = None
				pos = randint(0, 99)
				cur.scroll(pos, 'absolute')
				result = cur.fetchone()
				if (result):
					sid = int(result['id'])
				else:
					continue
				if not func(sid):
					break
			yield sid
def generate_hash(meta):
	return sha1(meta.encode("utf-8", "replace")).hexdigest()
def fix_encoding(meta):
	try:
		try:
			return unicode(meta, 'utf-8', 'strict')
		except (UnicodeDecodeError):
			return unicode(meta, 'shiftjis', 'replace')
	except (TypeError):
		return meta
def make_replacer(**replacements):
	locator = re.compile('|'.join(re.escape(s) for s in replacements))
	def _doreplace(mo):
		return replacements[mo.group()]
	def replace(s):
		return locator.sub(_doreplace, s)
	return replace

class MySQLCursor:
	"""Return a connected MySQLdb cursor object"""
	def __init__(self, cursortype=mysql.cursors.DictCursor):
		self.conn = mysql.connect(host=config.dbhost,
								user=config.dbuser,
								passwd=config.dbpassword,
								db=config.dbtable,
								charset='utf8',
								use_unicode=True)
		self.curtype = cursortype
	def __enter__(self):
		self.cur = self.conn.cursor(self.curtype)
		self.cur.escape_string = mysql.escape_string
		return self.cur
		
	def __exit__(self, type, value, traceback):
		self.cur.close()
		self.conn.commit()
		self.conn.close()
		return
		
search_replacer = make_replacer(**{r"\\": "", r"(": "", r")": "", r"*": ""})
search_regex = re.compile(r"^[+\-<>~]")
def search_tracks(search, limit=5):
	query_raw = search
	with MySQLCursor() as cur:
		search = search_replacer(search)
		query = []
		search = search.split(" ")
		for item in search:
			result = search_regex.sub("", item)
			query.append("+" + result)
		query = " ".join(query)
		try:
			query = query.encode("utf-8")
			query_raw = query_raw.encode("utf-8")
		except (UnicodeEncodeError):
			return []
		cur.execute("SELECT * FROM `tracks` WHERE `usable`='1' AND MATCH \
			(tags, artist, track, album) AGAINST ('{search_bin}' IN BOOLEAN MODE) \
			ORDER BY `priority` DESC, MATCH (tags, artist, track, \
			album) AGAINST ('{search_raw}') DESC LIMIT {limit};"\
			.format(search_bin=mysql.escape_string(query),
					search_raw=mysql.escape_string(query_raw),
					limit=limit))
		result = []
		for row in cur:
			result.append(row)
		return result
		
lastplayed = deque(["&nbsp;", "&nbsp;", "&nbsp;", "&nbsp;", "&nbsp;"], 5)
def fetch_lastplayed():
	with MySQLCursor() as cur:
		cur.execute("SELECT esong.meta FROM eplay JOIN esong ON esong.id = eplay.isong ORDER BY eplay.dt DESC LIMIT 5;")
		for result in cur:
			yield result['meta']
			
def send_status(np=None, djid=None, listeners=None, bitrate=None, is_afk=0, st_time=None, ed_time=None):
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
			path = "{0}/{1}".format(config.music_directory, row['path']) #omg it's absolute | hehe
			
			meta = title
			if artist != '':
				meta = artist + ' - ' + title
			
			#print "loading song '%s'" % (meta)
			return (path, meta)
		else:
			return None

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

def get_djuser(djid):
	djid = int(djid)
	with MySQLCursor() as cur:
		cur.execute("SELECT `user` FROM `users` WHERE `djid`='{id}';"\
				.format(id=djid))
		if (cur.rowcount > 0):
			return cur.fetchone()['user']
		else:
			return None
def get_djid(username=None):
	if (not username):
		with MySQLCursor() as cur:
			cur.execute("SELECT `djid` FROM `streamstatus`")
			djid = cur.fetchone()['djid']
			return str(djid)
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
def get_mountstatus(mount="/{0}".format(config.icecast_mountpoint)):
	try:
		req = urllib2.Request(config.icecast_server, headers={'User-Agent': 'Mozilla'})
		c = urllib2.urlopen(req)
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

def get_favelist(nick):
	"""Return list of titles that are faved"""
	with MySQLCursor as cur:
		meta = []
		query = "SELECT esong.meta FROM enick,efave,esong WHERE enick.id = efave.inick AND efave.isong = esong.id AND lower(enick.nick) = lower('{nick}');"
		cur.execute(query.format(nick=mysql.escape_string(nick)))
		for result in cur:
			meta.append(result['meta'])
		return meta

hash_row_tracker = {}
hash_faves = []
def get_hash(digest):
	"""Return playcount, length, lastplayed, favorites
	
		playcount int (count)
		length int (seconds)
		lastplayed int (unixtime)
	
	"""
	global hash_row_tracker
	with MySQLCursor() as cur:
		playcount = length = lastplayed = 0
		songid = None
		# Length first
		query = "SELECT id, len FROM `esong` WHERE `hash`='{digest}';"
		cur.execute(query.format(digest=digest))
		if (cur.rowcount > 0):
			hash_row_tracker.update({digest:True})
			result = cur.fetchone()
			songid = result['id']
			length = result['len']
			# last played
			query = "SELECT unix_timestamp(`dt`) AS ut FROM eplay,esong WHERE eplay.isong = esong.id AND esong.hash = '{digest}' ORDER BY `dt` DESC LIMIT 1;"
			cur.execute(query.format(digest=digest))
			lastplayed = cur.fetchone()['ut']
			# playcount
			query = "SELECT count(*) playcount FROM eplay,esong where eplay.isong = esong.id AND esong.hash = '{digest}';"
			cur.execute(query.format(digest=digest))
			playcount = cur.fetchone()['playcount']
		else:
			hash_row_tracker.update({digest:False})
		return (songid, playcount, length, lastplayed)
		
def get_lastplayed(digest):
	with MySQLCursor() as cur:
		query = "SELECT unix_timestamp(`dt`) AS ut FROM eplay,esong WHERE eplay.isong = esong.id AND esong.hash = '{digest}' ORDER BY `dt` DESC LIMIT 1;"
		cur.execute(query.format(digest=digest))
		if (cur.rowcount > 0):
			return cur.fetchone()['ut']
		return None
def send_hash(digest, title, length, lastplayed):
	global hash_row_tracker
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
			del hash_row_tracker[digest]
									
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

def get_faves(digest):
	"""Return a list of nicknames that have 'digest' favorited"""
	with MySQLCursor() as cur:
		cur.execute("SELECT enick.nick FROM esong JOIN efave ON efave.isong \
					= esong.id JOIN enick ON efave.inick = enick.id WHERE esong.hash \
			 			= '{digest}'".format(digest=digest))
		faves = []
		for result in cur:
			faves.append(result['nick'])
		return faves
def count_fave(songid):
	"""Return the amount of favorites for 'songid'"""
	if (not songid):
		return 0
	with MySQLCursor() as cur:
		cur.execute("SELECT count(*) AS favecount FROM efave WHERE isong={songid}".format(songid=songid))
		return cur.fetchone()['favecount']
	
def check_fave(nick, songid):
	"""Check if specified nick has 'songid' favorited"""
	if (not songid):
		return False
	with MySQLCursor() as cur:
		nick = mysql.escape_string(nick)
		cur.execute("SELECT * FROM enick WHERE nick='{nick}';".format(nick=nick))
		if (cur.rowcount == 0):
			return False
		else:
			nickid = cur.fetchone()['id']
			cur.execute("SELECT * FROM efave WHERE inick={nickid} AND isong={songid};".format(nickid=nickid, songid=songid))
			if (cur.rowcount == 0):
				return False
			else:
				return True
def add_fave(nick, songid, trackid=None):
	"""Add specified 'nick' to the list for song 'songid'
	in the 'efave' table
	"""
	if (not songid):
		return
	with MySQLCursor() as cur:
		nick = mysql.escape_string(nick)
		cur.execute("SELECT * FROM enick WHERE nick='{nick}';".format(nick=nick))
		if (cur.rowcount == 0):
			cur.execute("INSERT INTO enick (`nick`) VALUES('{nick}');".format(nick=nick))
			cur.execute("SELECT * FROM enick WHERE nick='{nick}';".format(nick=nick))
			nickid = cur.fetchone()['id']
			cur.execute("INSERT INTO efave (`inick`, `isong`) VALUES({nickid}, {songid});".format(nickid=nickid, songid=songid))
		elif (cur.rowcount == 1):
			nickid = cur.fetchone()['id']
			cur.execute("INSERT INTO efave (inick, isong) VALUES({nickid}, {songid});".format(nickid=nickid, songid=songid))
		if (trackid):
			cur.execute("UPDATE `tracks` SET `priority`=priority+2 WHERE `id`={trackid};".format(trackid=trackid))
		
def del_fave(nick, songid):
	"""Delete specified 'nick' from the list of favorites off 'songid'
	"""
	if (not songid):
		return
	with MySQLCursor() as cur:
		nick = mysql.escape_string(nick)
		cur.execute("SELECT * FROM enick WHERE nick='{nick}';".format(nick=nick))
		if (cur.rowcount == 0):
			return
		elif (cur.rowcount == 1):
			nickid = cur.fetchone()['id']
			cur.execute("DELETE FROM efave WHERE inick={nickid} AND isong={songid};".format(nickid=nickid, songid=songid))

def get_djname(djname):
	with open(config.djfile) as djs:
		djname = None
		for line in djs:
			temp = line.split('@')
			wildcards = temp[0].split('!')
			djname_temp = temp[1].strip()
			for wildcard in wildcards:
				wildcard = re.escape(wildcard)
				'^' + wildcard
				wildcard = wildcard.replace('*', '.*')
				if (re.search(wildcard, djname_temp, re.IGNORECASE)):
					djname = djname_temp
					break
			if (djname):
				return djname
		return djname	