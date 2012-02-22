import irclib
import re
from threading import Thread
import sqlitewrapper

DEBUG = True
#debug = open("debug.log", 'wb')
class IRC(Thread):
	"""Object that resembles a copy of irclib wrapper"""
	def __init__(self):
		Thread.__init__(self)
		self.irc = irclib.IRC()
		self.daemon = 1
		self.counter = 0
		
		self.serverlist = {}
		self.servers = {}
		self.version = 'Python IRC library'
		self.nickmodes = ''
		self.nickchars = ''
		self.argmodes = 'bkle' #lol i'm lazy. just assuming that bkl are all argument modes
		for event in irclib.all_events:
			self.irc.add_global_handler(event, self.dispatcher, -5)
	def connect(self, server, port, nick, nickpwd=None, channels=None):
		"""Connect to a server
			
			server   = address
			port     = port
			nick     = irc nick
			nickpwd  = password to identify 'nick' with 'nickserv'
			channels = list of channels to join on connect
			
			Returns a server ID unique to this connection which can be used to disconnect
		"""
		s = self.irc.server()
		s.connect(server, port, nick)
		self.counter += 1
		self.serverlist[self.counter] = s
		self.servers[s] = sqlitewrapper.SqliteConnection()
		self.servers[s].__attr = {"nickpwd": nickpwd, "channels": ",".join(channels)}
		self.start()
		return self.counter
	def isop(self, conn, channel, nick):
		return self.servers[conn].has_modes(channel, nick, 'o') or self.servers[conn].has_modes(channel, nick, 'a') or self.servers[conn].has_modes(channel, nick, 'q')
	def ishop(self, conn, channel, nick):
		return self.servers[conn].has_modes(channel, nick, 'h')
	def isvoice(self, conn, channel, nick):
		return self.servers[conn].has_modes(channel, nick, 'v')
	def isnormal(self, conn, channel, nick):
		return not self.hasaccess(conn, channel, nick) and not self.isvoice(conn, channel, nick)
	def hasaccess(self, conn, channel, nick):
		if (self.isop(conn, channel, nick)) or (self.ishop(conn, channel, nick)):
			return True
		return False
	def inchannel(self, conn, channel, nick):
		return self.servers[conn].in_chan(channel, nick)
	def topic(self, conn, channel):
		print("Server: {0}".format(self.servers[conn]))
		return self.servers[conn].topic(channel)
	def set_topic(self, conn, channel, topic):
		conn.topic(channel, topic)
	def run(self):
		self.irc.process_forever()
		
	def dispatcher(self, conn, event):
		#print "{event}: {source}: {target}: {arguments}\n".format(event=event.eventtype(),
		#				source=event.source(),
		#				target=event.target(),
		#				arguments=" ".join(event.arguments()))
		self.__internal_handle(conn, event)
		
	def __internal_handle(self, conn, event):
		data = self.servers[conn]
		e = event.eventtype()
		if (DEBUG):
			#debug.write(
			print("{event}: {source}: {target}: {arguments}\n".format(event=event.eventtype(),
						source=event.source(),
						target=event.target(),
						arguments=" ".join(event.arguments())))
		try:
			if ('!' in event.source()):
				nick = irclib.nm_to_n(event.source())
				host = irclib.nm_to_uh(event.source())
		except (TypeError):
			#Source is None
			pass
		chan = event.target()
		if (e == 'ctcp'):
			request = event.arguments()[0]
			if (request == 'VERSION'):
				conn.ctcp_reply(nick, 'VERSION {version}'.format(version=self.version))
			#print("CTCP: {0}".format(request))
		elif (e == "featurelist"):
			flist = " ".join(event.arguments())
			match = re.search(r"\sPREFIX=\((.*?)\)(.*?)\s", flist)
			if match:
				self.nickchars = match.groups()[1]
				self.nickmodes = match.groups()[0]
				self.argmodes += self.nickmodes
		elif (e == 'join'):
			data.join(chan, irclib.nm_to_n(event.source()))
			#print(data.get_nicks(chan))
		elif (e == 'part'):
			data.part(chan, irclib.nm_to_n(event.source()))
			#print(data.get_nicks(chan))
		elif (e == 'quit'):
			data.quit(irclib.nm_to_n(event.source()))
			#print(data.get_nicks(chan))
		elif (e == 'kick'):
			kickee = event.arguments()[0]
			data.part(chan, kickee)
			#print(data.get_nicks(chan))
		elif (e == 'nick'):
			old = nick
			new = chan  # bad terminology, source is the old nick, target is the new one
			data.nick(old, new)
			#print("Nick: {0} {1}".format(old, new))
		elif (e == 'topic'):
			topic = event.arguments()[0]
			data.topic(chan, topic)
			#print("Topic: {0}".format(topic))
		elif (e == 'currenttopic'):
			chan = event.arguments()[0]
			topic = " ".join(event.arguments()[1:])
			data.topic(chan, topic)
			#print("Topic: {0}".format(topic))
		elif (e == 'mode'):
			modeaction = event.arguments()[0][0] # + or -
			modes = list(event.arguments()[0]) # example: [+, o, o, -, h]
			modetargets = event.arguments()[1:]
			
			miter = 0
			titer = 0
			
			while miter < len(modes):
				mode = modes[miter]
				
				if mode in ['+', '-']: #FUCK IRC
					modeaction = mode
				if mode in self.nickmodes:
					nick = modetargets[titer]
					if modeaction == '+':
						data.add_mode(chan, nick, mode)
					else:
						data.rem_mode(chan, nick, mode)
				if mode in self.argmodes:
					titer += 1
				miter += 1
			
			#print('Channel: {0}'.format(chan))
			#print('Args: {0}'.format(event.arguments()[1:]))
		elif (e == 'notopic'):
			info = " ".join(event.arguments()[1:])
			data.topic(chan, '')
			#print("Topic: {0}".format(topic))
		# elif (e == 'topicinfo'):
			# chan = event.arguments()[0]
			# info = " ".join(event.arguments()[1:])
			# data.add_topicinfo(chan, info)
		elif (e == 'namreply'):
			kind = event.arguments()[0]
			chan = event.arguments()[1]
			names = event.arguments()[2].strip().split(' ')
			
			for name in names:
				split = 0
				for c in name:
					if c not in self.nickchars:
						break
					split += 1
				modes = list(name[:split])
				nick = name[split:]
				data.join(chan, nick)
				for mode in modes:
					pos = self.nickchars.index(mode)
					data.add_mode(chan, nick, self.nickmodes[pos])
		elif (e == 'invite'):
			target = event.arguments()[0]
			conn.join(target)
		elif (e == 'disconnect'):
			conn.connect(conn.server, conn.port, conn.nickname, conn.password,
					conn.username, conn.ircname, conn.localaddress,
					conn.localport, conn._ssl, conn._ipv6)
		elif (e == "endofmotd"):
			attr = data.__attr
			if (attr["nickpwd"]):
				conn.privmsg('nickserv', 'identify {pwd}'.format(pwd=attr["nickpwd"]))
			if (attr["channels"]):
				conn.join(attr["channels"])
