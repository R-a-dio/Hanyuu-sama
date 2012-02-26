# -*- coding: utf-8 -*-
import socket
import urllib2
from urllib import quote
import time
from threading import Thread, Lock
from collections import deque
import re
from hashlib import sha1
import chardet
import codecs
import webcom
import traceback
import __main__
import pyices as streamer
from mutagen.mp3 import MP3
import config
import streamstatus
import logging

shouturl = config.icecast_server + '/' + config.icecast_mountpoint
radiourl = config.base_host
audio_info = {'bitrate': config.icecast_bitrate,
				'channels': config.icecast_channels}
stream_login = {'host': config.icecast_host,
			'port': config.icecast_port, 'password': config.icecast_pass, 'format': config.icecast_format,
			'protocol': config.icecast_protocol, 'name': config.meta_name,
			'url': config.meta_url, 'genre': config.meta_genre,
			'description': config.meta_desc,
			'audio_info': audio_info, 'mount': config.icecast_mount }
# Amount of seconds to wait before socket and AFK streamer
_connection_timeout = config.icecast_timeout
def web_update(instance):
	if (instance.current != 'Placeholder') and (instance.current != ''):
		if (instance.length == 0):
			ed_time = 0
		else:
			ed_time = instance._start_time + instance.length
		webcom.send_nowplaying(np=instance.current, djid=instance.djid,
		listeners=instance.listeners, bitrate=instance.bitrate,
		is_afk=instance.isafk(), st_time=instance._start_time,
		ed_time=ed_time)

def fix_encoding(meta):
	try:
		try:
			return unicode(meta, 'utf-8', 'strict')
		except (UnicodeDecodeError):
			return unicode(meta, 'shiftjis', 'replace')
	except (TypeError):
		return meta
	result = chardet.detect(meta)
	encoding_original = meta
	encoding_result = result
	if (not result['encoding']):
		new = unicode(meta, errors="replace")
	else:
		decoder = codecs.getdecoder(result['encoding'])
		try:
			if (result['encoding'] != 'utf-8'):
				new = decoder(meta, 'replace')[0]
			else:
				new = unicode(meta, result['encoding'], errors="replace")
			encoding_new = new
			return new
		except:
			new = unicode(meta, errors="replace")
			encoding_new = new
	return new
	
class StreamInstance(Thread):
	def __init__(self):
		global main
		Thread.__init__(self)
		
		main = __main__.main
		self.bytecount = 0
		self.read = ''
		self.reconnect = True
		
		self.current = 'Placeholder'
		self.listeners = '0'
		self.bitrate = '0'
		self.peak = ''
		self.first = True
		
		self.request = False
		self.afk_streaming = False
		self.connected = True
		self.exit = True
		
		self._start_time = 0
		self._end_time = 0
		self.length = 0
		self.playcount = 0
		self.songid = None
		self.digest = ''
		self.lp = 0
		self.digest = ''
		
		self._reconnect_counter = None
		# fix lastplayed
		webcom.fetch_lastplayed()
		# receiving DJid
		try:
			topic = main.irc.topic(main.irc.serverlist[main.irc_serverid], '#r/a/dio')
			regex = re.compile(r"DJ:.*?\s(.*?)\s.*?http")
			match = regex.search(topic)
			self.djid = webcom.get_djid(__main__.get_dj(match.group(1)))
			if not self.djid:
				self.djid = '0'
			print("DJid: {0}".format(self.djid))
		except:
			self.djid = '0'
		if (self.djid == '18'):
			_connection_timeout = 0.0
		#self.connect()
		
		self.thread = Thread(target=self.updateinfo)
		self.thread.daemon = 1
		self.thread.start()
		
		self.daemon = 1
		self.start()
	
	def cleanup(self):
		self.exit = False
		self.reconnect = False
		self.connected = False
		self.thread.join()
		self.join()
	def active(self):
		return self._updateinfo()
	def connect(self):
		self.time_current = time.time()
		response = ''
		response_headers = ''
		response_body = ''
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.settimeout(_connection_timeout)
		self.socket.connect((config.icecast_host, config.icecast_port))
		headers = 'GET {mount} HTTP/1.1\r\nHOST: {host}\r\nUser-Agent: Hanyuu-sama\r\nIcy-MetaData: 1\r\n\r\n'.format(mount=config.icecast_mount, host=config.icecast_host)
		self.socket.send(headers)
		while ('\r\n\r\n' not in response):
			response = self.socket.recv(128)
			response_headers += response
		else:
			n = response.find('\r\n\r\n')
			if (n != -1):
				response_headers += response[:n]
				response_body = response[n+4:]
			else:
				print('Error: Not connecting stream socket to stream.')
				return
		header_dict = {}
		status = response_headers.split('\r\n')[0]
		if (status.split(' ')[1] != '200'):
			self.connected = False
			self.reconnect = True
			time.sleep(_connection_timeout)
			self._reconnect()
		else:
			response_headers = response_headers.split('\r\n')[1:]
			for h in response_headers:
				if (not h):
					break
				header = h.split(':')
				header_dict[header[0].strip()] = header[1].strip()
			self.info = header_dict
			self.metaint = int(header_dict['icy-metaint'])
			self.read = response_body
			self.bytecount = len(self.read)
			self.connected = True
		
	def _reconnect(self):
		print("Reconnect: Trying reconnecting")
		result = streamstatus.get_status(config.icecast_server)
		if (config.icecast_mount in result):
			print("Reconnect: Found mountpoint")
			self._reconnect_counter = None
			self.connect()
		else:
			print("Reconnect: No mountpoint, waiting on AFK streamer")
			if (self._reconnect_counter != None):
				self._reconnect_counter += 1
			else:
				self._reconnect_counter = 0
			print("Reconnect: Counter: {0}".format(self._reconnect_counter))
			if (self._reconnect_counter > 1):
				self._reconnect_counter = None
				_connection_timeout = 7.5
				self.afk_streamer()
	def run(self):
		while (self.exit):
			while (self.connected):
				while (self.bytecount < self.metaint):
					try:
						r = self.socket.recv(128)
					except socket.timeout:
						print('Connection: Shout socket timed out receiving data')
						self.connected = False
						self.reconnect = True
						break
					if (not r):
						print('Connection: Shout socket received no data')
						self.connected = False
						self.reconnect = True
						break
					self.read += r
					self.bytecount = len(self.read)
				if (self.connected):
					if (self.bytecount == self.metaint):
						data = self.socket.recv(128)
					else:
						data = self.read[self.metaint:]
					metalen = ord(data[0]) * 16
					data = data[1:]
					while (len(data) < metalen):
						data += self.socket.recv(128)
					leftover = data[metalen:]
					meta = data[0:metalen]
					if (len(meta) > 0):
						#Strip from keys
						if (len(meta) > 200):
							self.meta = u'Long tags'
						meta = meta[:meta.rfind("';")]
						if (meta[:13].lower() == "streamtitle='"):
							meta = meta[13:]
						else:
							break
						# Check if we reconnected or it is a new song
						if (len(meta) > 0):
							self.newmeta = webcom.fix_encoding(meta)
						else:
							self.newmeta = u''
						self.newmeta = self.newmeta.strip()
						if (meta == 'fallback'):
							break
						if (self.digest != self.__get_hash(self.newmeta)):
							self.__finish_track()
							self.__meta_update(meta)
							self.__start_track()
					self.bytecount = len(leftover)
					self.read = leftover
			print("Connection: Shout disconnected")
			if (self.reconnect):
				self._reconnect()
			if (self.exit):
				time.sleep(_connection_timeout)
		print("Thread Exit: Shout")
	
	def shut_afk_streamer(self, force=False):
		if (force == True):
			self.afkstreamer.close()
			self.afk_streaming = False
		else:
			self._shut_afkstreamer = True
		self.request = False
	def afk_streamer(self):
		### NEED TO FIX QUEUE ISSUE WITH FINISHING_SONG
		print("AFK: Starting client")
		self._shut_afkstreamer = False
		self.afk_streaming = True
		self.request = True
		self.first = True
		stream = streamer.instance(stream_login)
		self.afkstreamer = stream
		self.queue = webcom.SongQueue()
		def set_irc():
			def color(n=u''):
				return unichr(3) + n
			irc = main.irc
			server = irc.serverlist[main.irc_serverid]
			if (self.djid != '18'):
				topic = irc.topic(server, '#r/a/dio')
				regex = re.compile(r"((.*?r/)(.*)(/dio.*?))\|(.*?)\|(.*)")
				result = regex.match(topic)
				if (result != None):
					result = list(result.groups())
					parameters = (color('07'), color('04'), "UP", color('07'), color('04'), "AFK Streamer", color('11'), color())
					result[1:5] = u'|%s Stream:%s %s %sDJ:%s %s %s http://r-a-dio.com%s |' % parameters
					newtopic = "".join(result)
					irc.set_topic(server, '#r/a/dio', newtopic)
				self.djid = '18'
			server.privmsg('#r/a/dio', "AFK Streamer activating")
		def song_length(file):
			try:
				audio = MP3(file)
				return audio.info.length
			except:
				return 0
		def afk_start_song(object):
			self.queue.set_lastplayed(self._songid)
			self.__meta_update(object.metadata)
			self.__start_track()
			self.length = self._length
			print("AFK: Starting song: {0}".format(object.metadata))
		def afk_finishing_song(object):
			self._songid = self.queue.pop()
			self.file, meta = webcom.get_song(self._songid)
			self._next_length = song_length(self.file)
			if (not self._shut_afkstreamer):
				object.add_file(self.file, meta)
			print("AFK: Finishing song")
		def afk_finish_song(object):
			self._accurate_songid = self._songid
			self._length = self._next_length
			self.queue.send_queue(self._length)
			self.__finish_track()
			if (self._shut_afkstreamer):
				object.close()
				self.afk_streaming = False
			print("AFK: Finished song")
		def afk_disconnect(object):
			self.afk_streaming = False
			object.close()
			print("AFK: Disconnected")
		stream.add_handle('start', afk_start_song)
		stream.add_handle('finishing', afk_finishing_song)
		stream.add_handle('finish', afk_finish_song)
		stream.add_handle('disconnect', afk_disconnect)
		self._songid = self.queue.pop()
		self._accurate_songid = self._songid
		self.file, meta = webcom.get_song(self._songid)
		self._length = song_length(self.file)
		self.__finish_track()
		try:
			set_irc()
		except (TypeError):
			logging.debug("No motherfucking topic today")
		stream.add_file(self.file, meta)
		self.queue.send_queue(self._length)
		while (self.afk_streaming):
			time.sleep(0.5)
		# Cleanup stuff for when it exits (Like putting requests back in the db)
		del self.afkstreamer
		self.request = False
		self.queue.clean_requests()
		try:
			del self.queue, self.file, self._songid, self._length, self._next_length
		except (AttributeError):
			pass
	def __meta_update(self, meta):
		if (not self.first):
			self.__submit_data()
		# Add last song to last played list
		webcom.lastplayed.appendleft(self.current)
		# Set current song data
		if (len(meta) > 0):
			self.current = webcom.fix_encoding(meta)
		else:
			self.current = u''
		self.current = self.current.strip()
		#print self.current
		#print type(self.current)
		self.__acquire_data()
		#print u'Starting: ' + self.current
		# Send to r-a-dio server
		web_update(self)
	def __get_hash(self, meta):
		m = sha1()
		#print type(meta)
		if (type(meta) == unicode):
			d = codecs.getencoder('utf-8')
			meta = d(meta, 'replace')[0]
		#else:
		#	d = codecs.getdecoder('utf-8')
		#	meta = d(meta, 'replace')[0]
		m.update(meta)
		return m.hexdigest()
	
	def __submit_data(self):
		"""Submit all data in memory to the mysqldb
		
			Hash, title, playcount, length, fave, lastplayed
			
			Hash = sha1 hexdigest of self.current
			Title = self.current
			Playcount = self.playcount
			Length = self.length
			Fave = "!".join(self.fave)
			Lastplayed = self.lp
			
		CALL BEFORE UPDATING MEMORY DATA
		"""
		webcom.send_hash(self.digest, self.current, self.length, self.lp)
		
	def __acquire_data(self):
		"""Acquire all data and save it in memory
		
		 CALL AFTER UPDATING MEMORY DATA
		"""
		self.digest = self.__get_hash(self.current)
		
		self.songid, self.playcount, self.length, self.lp = webcom.get_hash(self.digest)
		
	def __start_track(self):
		"""Initialize stuff for the new track"""
		self.playcount += 1
		self._start_time = int(time.time())
		self.first = False
		main.irc_announce(webcom.get_faves(self.digest))
		
	def __finish_track(self):
		"""Wrap up data"""
		if (not self.first):
			self._end_time = int(time.time())
			if (self._start_time):
				self.length = self._end_time - self._start_time
			self.lp = int(time.time())
	
	def _updateinfo(self):
		if (self.afk_streaming) or (self.connected):
			return True
		return False
	def updateinfo(self):
		"""Get new information from the stream every 20 seconds
		
			Handles: Bitrate, Listeners"""
		while (self.exit):
			z = False
			while (self._updateinfo()):
				if (z == False):
					z = True
					print("Status: Updateinfo enter")
				try:
					req = urllib2.Request(config.icecast_server, headers={'User-Agent': 'Mozilla'})
					c = urllib2.urlopen(req)
				except:
					print("Status: Updateinfo error")
				else:
					next = ''
					for line in c:
						if (line.find('Bitrate') != -1):
							next = 'bitrate'
						elif (line.find('Current Listeners') != -1):
							next = 'listeners'
						elif (next != '') and (len(line) > 0):
							if (next == 'bitrate'):
								self.bitrate = line[23:][:-6]
							elif (next == 'listeners'):
								self.listeners = line[23:][:-6]
							next = ''
					if (self.length == 0):
						ed_time = 0
					else:
						ed_time = self._start_time + self.length
					if (self.current != 'Placeholder'):
						webcom.send_nowplaying(None, self.djid,
						self.listeners, self.bitrate, self.isafk(),
						self._start_time, ed_time)
				time.sleep(10)
			print "Status: Updateinfo exit"
			print "AFK: {0}, CONN: {1}".format(self.afk_streaming, self.connected)
			if (self.exit):
				time.sleep(20)
	def isafk(self):
		if (self.request):
			return 1
		return 0
	def lastplayed(self):
		return list(webcom.lastplayed)
		
	def nowplaying(self):
		return self.current
		
	def get_length(self):
		return self.__get_ms(self.length)
	
	def get_left(self):
		return self.length - (int(time.time()) - self._start_time)
		
	def get_duration(self):
		seconds = int(time.time()) - self._start_time
		return self.__get_ms(seconds)
	
	def get_playcount(self):
		return unicode(self.playcount)
		
	def get_fave_count(self):
		return unicode(webcom.count_fave(self.songid))
	
	def get_lastplayed(self):
		return self.__parse_lastplayed(self.lp)
		
	def _encode(self, meta):
		pass
	
	def __get_ms(self, seconds):
		m, s = divmod(seconds, 60)
		return u"%02d:%02d" % (m, s)
		
	def __parse_lastplayed(self, seconds):
		if (seconds > 0):
			difference = int(time.time()) - seconds
			year, month = divmod(difference, 31557600)
			month, week = divmod(month, 2629800)
			week, day = divmod(week, 604800)
			day, hour = divmod(day, 86400)
			hour, minute = divmod(hour, 3600)
			minute, second = divmod(minute, 60)
			result = ''
			if (year): result += u'%d year(s) ' % year
			if (month): result += u'%d month(s) ' % month
			if (week): result += u'%d week(s) ' % week
			if (day): result += u'%d day(s) ' % day
			if (hour): result += u'%d hour(s) ' % hour
			if (minute): result += u'%d minute(s) ' % minute
			if (second): result += u'%d second(s) ' % second
			return result.strip()
		else:
			return u'Never before'
