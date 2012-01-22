#!/usr/bin/python
# -*- coding: utf-8 -*-

_profile_app = False
import irc as _irc
import shoutmain
import re
import webcom as web
from flup.server.fcgi import WSGIServer
import watcher
import time
from traceback import format_exc
import threading
import config
djfile = './dj.conf' # Where to get the list of DJs

handle = ''
class HanyuuHandlers:
	def __init__(self):
		self.__handlers = {}
	def add_global_handler(self, handler, event, **kwargs):
		"""Adds a handler to be called when event happens with the appropriate parameters.
		Parameters are different for each event.
		
		Following events are supported for now:
			'on_text': Activates when there is a message, additional parameters should
				always be added with keywords. The following are available:
					
					'nick': The nick that triggered the event. Can be left out for all nicks
					'channel': The channel the event origined from.
					'text': a regex pattern that this event should be triggered with
							i.e. text='Hello.*' will trigger on all messages that begin
												with 'Hello'.
		"""
		info = {'nick':'*', 'channel':'*', 'text':''}
		info.update(kwargs)
		info['compiled'] = re.compile(info['text'], re.I|re.U)
		if not event in self.__handlers:
			self.__handlers[event] = []
		self.__handlers[event].append((handler, info))
	
	def clean_handlers(self):
		self.__handlers = {}
		
	def call_on_text(self, conn, event):
		if 'on_text' in self.__handlers:
			nick = unicode(_irc.irclib.nm_to_n(event.source()), errors="replace")
			userhost = unicode(_irc.irclib.nm_to_uh(event.source()), errors="replace")
			host = unicode(_irc.irclib.nm_to_h(event.source()), errors="replace")
			target = unicode(event.target(), errors="replace")
			text = event.arguments()[0].decode('utf-8', 'replace')
			for handler in self.__handlers['on_text']:
				call, info = handler
				if (info['nick'] != nick) and (nick not in info['nick']) and (info['nick'] != '*'):
					continue
				if (info['channel'] != target) and (target not in info['channel']) and (info['nick'] != '*'):
					continue
				if (info['text'] != ''):
					compiled = info['compiled']
					result = compiled.match(text)
					if (result == None):
						continue
				print event.arguments()
				try:
					call(conn, nick, target, text)
				except:
					print format_exc()

def external_request(environ, start_response):
	if (shout.afk_streaming):
		def is_int(num):
			try:
				int(num)
				return True
			except:
				return False
		try:
			postdata = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))
		except:
			postdata = ""
		splitdata = postdata.split('=')
		sitetext = ""
		if len(splitdata) == 2 and splitdata[0] == 'songid' and is_int(splitdata[1]):
			songid = int(splitdata[1])
			canrequest_ip = False
			canrequest_song = False
			with web.MySQLCursor() as cur:
				# SQL magic
				cur.execute("SELECT * FROM `requesttime` WHERE `ip`='%s' LIMIT 1;" % (environ["REMOTE_ADDR"]))
				ipcount = cur.rowcount
				if cur.rowcount >= 1:
					try:
						iptime = int(time.mktime(time.strptime(str(cur.fetchone()["time"]), "%Y-%m-%d %H:%M:%S" )))
					except:
						iptime = 0
				else:
					iptime = 0
				now = int(time.time())
				if now - iptime > 1800:
					canrequest_ip = True
				
				cur.execute("SELECT * FROM `tracks` WHERE `id`=%s LIMIT 1;" % (songid))
				if cur.rowcount >= 1:
					try:
						lptime = int(time.mktime(time.strptime(str(cur.fetchone()["lastrequested"]), "%Y-%m-%d %H:%M:%S" )))
					except:
						lptime = 0
				else:
					lptime = now
				if now - lptime > 3600 * 8:
					canrequest_song = True
				
				if cur.rowcount >= 1:
					try:
						lptime = int(time.mktime(time.strptime(str(cur.fetchone()["lastplayed"]), "%Y-%m-%d %H:%M:%S" )))
					except:
						lptime = 0
				else:
					lptime = now
				if now - lptime > 3600 * 8:
					canrequest_song = canrequest_song and True

				
				if not canrequest_ip or not canrequest_song:
					if not canrequest_ip:
						sitetext = "You need to wait longer before requesting again."
					elif not canrequest_song:
						sitetext = "You need to wait longer before requesting this song."
				else:
					sitetext = "Thank you for making your request!"
					#SQL magic
					if ipcount >= 1:
						cur.execute("UPDATE `requesttime` SET `time`=NOW() WHERE `ip`='%s';" % (environ["REMOTE_ADDR"]))
					else:
						cur.execute("INSERT INTO `requesttime` (`ip`) VALUES ('%s');" % (environ["REMOTE_ADDR"]))
					cur.execute("UPDATE `tracks` SET `lastrequested`=NOW(), `priority`=priority+4 WHERE `id`=%s;" % (songid))
					main.irc_request_announce(songid)
					shout.queue.add_request(songid)
					shout.queue.send_queue(shout.get_left())
		else:
			sitetext = "Invalid parameter."
	else:
		sitetext = "You can't request songs at the moment."
	start_response('200 OK', [('Content-Type', 'text/html')])
	yield '<html>'
	yield '<head>'
	yield '<title>r/a/dio</title>'
	yield '<meta http-equiv="refresh" content="5;url=/search/">'
	yield '<link rel="shortcut icon" href="/favicon.ico" />'
	yield '</head>'
	yield '<body>'
	yield '<center><h2>%s</h2><center><br/>' % (sitetext)
	yield '<center><h3>You will be redirected shortly.</h3></center>'
	yield '</body>'
	yield '</html>'
	
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
	main._init_handlers()
	# Queue watcher
	print("Starting watcher")
	watcher.start_watcher()
	print "FCGI Server Starting"
	WSGIServer(external_request, bindAddress='/tmp/fastcgi.pywessie.sock',umask=0).run()
		
def get_dj(dj):
	with open(djfile) as djs:
		djname = None
		for line in djs:
			temp = line.split('@')
			wildcards = temp[0].split('!')
			djname_temp = temp[1].strip()
			for wildcard in wildcards:
				wildcard = re.escape(wildcard)
				'^' + wildcard
				wildcard = wildcard.replace('*', '.*')
				if (re.search(wildcard, dj, re.IGNORECASE)):
					djname = djname_temp
					break
			if (djname):
				return djname
		return djname
def color(n=u''):
	return unichr(3) + n
class AlternativeMainLoop(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		self._init_irc()
		self.start()
	def _init_handlers(self):
		print(u"Initializing IRC Handlers")
		self.irc_handlers.add_global_handler(self.irc_np, 'on_text', text=r'[.!@]np.*')
		self.irc_handlers.add_global_handler(self.irc_lp, 'on_text', text=r'[.!@]lp.*')
		self.irc_handlers.add_global_handler(self.irc_queue, 'on_text', text=r'[.!@]q(ueue)?.*')
		self.irc_handlers.add_global_handler(self.irc_dj, 'on_text', text=r'[.!@]dj.*')
		self.irc_handlers.add_global_handler(self.irc_favorite, 'on_text', text=r'[.!@]fave.*')
		self.irc_handlers.add_global_handler(self.irc_unfavorite, 'on_text', text=r'[.!@]unfave.*')
		self.irc_handlers.add_global_handler(self.irc_set_curthread, 'on_text', text=r'[.!@]thread(\s.*)?')
		self.irc_handlers.add_global_handler(self.irc_topic, 'on_text', text=r'[.!@]topic(\s.*)?')
		self.irc_handlers.add_global_handler(self.irc_kill_afk, 'on_text', text=r'[.!@]kill', nick=["Wessie", "Vin"])
		self.irc_handlers.add_global_handler(self.irc_shut_afk, 'on_text', text=r'[.!@]cleankill', channel=['#r/a/dio', '#r/a/dio-dev'])
		self.irc_handlers.add_global_handler(self.irc_request_help, 'on_text', text=r'.*how.+request')
	def _init_irc(self):
		print(u"Initializing IRC")
		self.irc_handlers = HanyuuHandlers()
		self.irc = _irc.IRC()
		self.irc.version = config.irc_version
		self.irc_serverid = self.irc.connect(config.irc_server, config.irc_port, config.irc_name,
								config.irc_pass, config.irc_channels)
		self.irc_server = self.irc.serverlist[self.irc_serverid]
		self.irc.serverlist[self.irc_serverid].add_global_handler('pubmsg', self.irc_handlers.call_on_text, 0)
	def _check_irc(self):
		if (not self.irc_server.is_connected()):
			print(u"IRC is not connected, trying to reconnect")
			self.irc_server.reconnect(u"Not connected")
	def run(self):
		while True:
			self._check_irc()
			time.sleep(60)
			
			
			
			
	# IRC Responses and handler methods start name with 'irc_'
	def irc_np(self, conn, nick, channel, text):
		if (shout.active()):
			try:
				message = u"Now playing:%s '%s' %s[%s/%s](%s/200), %s faves, played %s time(s), %s" % (color('4'),
						shout.nowplaying(), color(),
						shout.get_duration(), shout.get_length(), shout.listeners,
						shout.get_fave_count(), shout.get_playcount(),
						u'%sLP:%s %s' % (color('03'), color(), shout.get_lastplayed()))
			except UnicodeDecodeError:
				message = u"We have an encoding problem, borked tags."
		else:
			message = u"Stream is currently down."
		try:
			conn.privmsg(channel, message)
		except:
			print traceback.format_exc()
			conn.privmsg(channel, u"Encoding errors go here")
	def irc_lp(self, conn, nick, channel, text):
		lp = shout.lastplayed()
		string = u"{0}Last Played: {1}{3} {2}|{1} {4}{0} {2}|{1} {5} {2}|{1} {6} {2}|{1} {7}".format(color('3'),color(),color('15'), lp[0], lp[1], lp[2], lp[3], lp[4])
		conn.privmsg(channel, string)
	def irc_queue(self, conn, nick, channel, text):
		string = u"No queue at the moment (lazy Wessie)"
		queue = shoutmain.web.queue
		try:
			if (len(queue) >= 5):
				string = u"{0}Queue: {1}{3} {2}|{1} {4}{0} {2}|{1} {5} {2}|{1} {6} {2}|{1} {7}".format(color('3'),
						color(),color('15'), queue[0].decode('utf-8', 'replace'),
											queue[1].decode('utf-8', 'replace'),
											queue[2].decode('utf-8', 'replace'),
											queue[3].decode('utf-8', 'replace'),
											queue[4].decode('utf-8', 'replace'))
		except (UnicodeDecodeError):
			string = u"Derped on Unicode"
		conn.privmsg(channel, string)
	def irc_dj(self, conn, nick, channel, text):
		tokens = text.split(' ')
		new_dj = " ".join(tokens[1:])
		if (new_dj != ''):
			if (self.irc.hasaccess(conn, channel, nick)):
				if (new_dj):
					if (new_dj == 'None'):
						new_status = 'DOWN'
					elif (new_dj):
						new_status = 'UP'
					topic = self.irc.topic(conn, channel)
					print("Topic: {0}".format(topic))
					regex = re.compile(r"((.*?r/)(.*)(/dio.*?))\|(.*?)\|(.*)")
					result = regex.match(topic)
					if (result != None):
						result = list(result.groups())
						parameters = (color('07'), color('04'), new_status, color('07'), color('04'), new_dj, color('11'), color())
						result[1:5] = u'|%s Stream:%s %s %sDJ:%s %s %s http://r-a-dio.com%s |' % parameters
						self.irc.set_topic(conn, channel, u"".join(result))
						self.current_dj = new_dj
						new_dj = get_dj(new_dj)
						shout.djid = web.get_djid(new_dj)
						web.send_queue(0, [])
						print shout.djid, new_dj
						web.send_nowplaying(djid=shout.djid)
					else:
						conn.privmsg(channel, 'Topic is borked, repair first')
			else:
				conn.notice(nick, "You don't have the necessary privileges to do this.")
		else:
			conn.privmsg(channel, "Current DJ: {0}{1}".format(color('03'), self.current_dj))
	def irc_favorite(self, conn, nick, channel, text):
		if (web.check_fave(nick, shout.songid)):
			response = u"You already have {c3}'{np}'{c} favorited".format(c3=color('03'), np=shout.nowplaying(), c=color())
		else:
			if (shout.isafk()):
				web.add_fave(nick, shout.songid, shout._accurate_songid) #first esong.id, then tracks.id
			else:
				web.add_fave(nick, shout.songid)
			response = u"Added {c3}'{np}'{c} to your favorites.".format(c3=color("03"), np=shout.nowplaying(), c=color())
		conn.notice(nick, response)
		
	def irc_unfavorite(self, conn, nick, channel, text):
		if (web.check_fave(nick, shout.songid)):
			web.del_fave(nick, shout.songid)
			response = u"{c3}'{np}'{c} is removed from your favorites.".format(c3=color("03"), np=shout.nowplaying(), c=color())
		else:
			response = u"You don't have {c3}'{np}'{c} in your favorites.".format(c3=color("03"), np=shout.nowplaying(), c=color())
		conn.notice(nick, response)
	def irc_set_curthread(self, conn, nick, channel, text):
		tokens = text.split(' ')
		threadurl = " ".join(tokens[1:]).strip()

		if threadurl != "" or len(tokens) > 1:
			if self.irc.hasaccess(conn, channel, nick):
				web.send_curthread(threadurl)

		curthread = web.get_curthread()
		response = u"Thread: %s" % (curthread)
		conn.privmsg(channel, response)
	def irc_topic(self, conn, nick, channel, text):
		tokens = text.split(' ')
		param = u" ".join(tokens[1:]).strip()
		param = shoutmain.fix_encoding(param)
		if param != u"" or len(tokens) > 1: #i have NO IDEA WHATSOEVER why this is like this. just c/p from above
			if self.irc.hasaccess(conn, channel, nick):
				topic = self.irc.topic(conn, channel)
				print(u"Topic: {0}".format(topic))
				regex = re.compile(ur"(.*?r/)(.*)(/dio.*?)(.*)")
				result = regex.match(topic)
				if (result != None):
					result = list(result.groups())
					result[1] = u"{0}{1}".format(param, color('07'))
					self.irc.set_topic(conn, channel, u"".join(result))
				else:
					conn.privmsg(channel, 'Topic is borked, repair first')

		else:
			topic = self.irc.topic(conn, channel)
			conn.privmsg(channel, u"Topic: %s" % topic)
	def irc_kill_afk(self, conn, nick, channel, text):
		if (self.irc.isop(conn, channel, nick)):
			try:
				shout.shut_afk_streamer(True)
				message = u"Forced AFK Streamer down,\
							please connect in 15 seconds or less."
			except:
				message = u"Something went wrong, please punch Wessie."
				print format_exc()
			conn.privmsg(channel, message)
		else:
			conn.notice(channel, u"You don't have high enough access to do this.")
	def irc_shut_afk(self, conn, nick, channel, text):
		if (self.irc.isop(conn, channel, nick)):
			try:
				shout.shut_afk_streamer(False)
				message = u'AFK Streamer will disconnect after current \
					track, use ".kill" to force disconnect.'
			except:
				message = u"Something went wrong, please punch Wessie."
				print format_exc()
			conn.privmsg(channel, message)
		else:
			conn.notice(channel, u"You don't have high enough access to do this.")
	def irc_announce(self, faves):
		for fave in faves:
			if (self.irc.inchannel(self.irc_server, "#r/a/dio", fave)):
				self.irc_server.notice(fave, u"Fave: {0} is playing.".format(shout.current))
		if (len(faves) > 0):
			message = u"Now starting:%s '%s' %s[%s/%s](%s/200), %s faves, played %s time(s), %s" % (color('4'),
							shout.nowplaying(), color(),
							shout.get_duration(), shout.get_length(), shout.listeners,
							shout.get_fave_count(), shout.get_playcount(),
							u'%sLP:%s %s' % (color('03'), color(), shout.get_lastplayed()))
			self.irc_server.privmsg("#r/a/dio", message)
	def irc_request_announce(self, request):
		try:
			path, message = web.get_song(request)
			message = u"Requested:{c3} '{request}'".format(c3=color('03'),request=message)
			self.irc_server.privmsg("#r/a/dio", message)
		except:
			print "I'm broken with all the requests"
	def irc_search(self, search):
		pass
	def irc_request(self, id):
		pass
	def irc_request_help(self, conn, nick, channel, text):
		try:
			message = u"{nick}: http://r-a-dio.com/search {c5}Thank you for listening to r/a/dio!".format(nick=nick, c5=color('05'))
			self.irc_server.privmsg(channel, message)
		except:
			print "Error in request help function"
if __name__ == '__main__':
	if (_profile_app):
		import cProfile
		cProfile.run('main_start()', 'profile_output')
	else:
		main_start()
