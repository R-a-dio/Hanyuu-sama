import irclib
import re
from threading import Thread

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
		self.servers[s] = Server(s)
		self.servers[s].__attr = {"nickpwd": nickpwd, "channels": ",".join(channels)}
		self.start()
		return self.counter
	def isop(self, conn, channel, nick):
		return self.servers[conn].has_mode(channel, nick, 'o') or self.servers[conn].has_mode(channel, nick, 'a') or self.servers[conn].has_mode(channel, nick, 'q')
	def ishop(self, conn, channel, nick):
		return self.servers[conn].has_mode(channel, nick, 'h')
	def isvoice(self, conn, channel, nick):
		return self.servers[conn].has_mode(channel, nick, 'v')
	def isnormal(self, conn, channel, nick):
		return not self.hasaccess(conn, channel, nick) and not self.isvoice(conn, channel, nick)
	def hasaccess(self, conn, channel, nick):
		if (self.isop(conn, channel, nick)) or (self.ishop(conn, channel, nick)):
			return True
		return False
	def inchannel(self, conn, channel, nick):
		return self.servers[conn].inchannel(channel, nick)
	def topic(self, conn, channel):
		print("Server: {0}".format(self.servers[conn]))
		return self.servers[conn].get_topic(channel)
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
			data.join(chan, event.source())
			#print(data.get_nicks(chan))
		elif (e == 'part'):
			data.part(chan, event.source())
			#print(data.get_nicks(chan))
		elif (e == 'quit'):
			data.part(None, event.source())
			#print(data.get_nicks(chan))
		elif (e == 'kick'):
			kickee = event.arguments()[0]
			data.part(chan, kickee + "!~" + kickee + "@broken.as.fuck")
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
						data.add_nick_mode(chan, nick, mode)
					else:
						data.rem_nick_mode(chan, nick, mode)
				if mode in self.argmodes:
					titer += 1
				miter += 1
			
			#print('Channel: {0}'.format(chan))
			#print('Args: {0}'.format(event.arguments()[1:]))
		elif (e == 'notopic'):
			info = " ".join(event.arguments()[1:])
			data.topic(chan, None)
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
				data.join(chan, nick + "!~" + nick + "@broken.as.fuck") #yeah... this is dumb. names doesn't have hosts.
				for mode in modes:
					pos = self.nickchars.index(mode)
					data.add_nick_mode(chan, nick, self.nickmodes[pos])
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
class Server:
	def __init__(self, conn):
		self.connection = conn
		self._nicknames = Nicknames()
		self._channels = Channels()
	
	def join(self, chan, src):
		nick = irclib.nm_to_n(src)
		host = irclib.nm_to_uh(src)
		chan = irclib.irc_lower(chan)
		
		if not self._nicknames.knows_of_nick(nick):
			self._nicknames.add_nick(nick, host)
		
		if not self._channels.knows_of_chan(chan):
			self._channels.add_chan(chan)
		
		id = self._nicknames._nicks[nick]['id']
		if self._channels.nick_join(chan, id, []):
			self._nicknames.chan_join(nick)
	def part(self, chan, src):
		nick = irclib.nm_to_n(src)
		host = irclib.nm_to_uh(src)
		id = self._nicknames._nicks[nick]['id']
		if chan is not None:
			chan = irclib.irc_lower(chan)
			
			self._channels.nick_part(chan, id)
			self._nicknames.chan_part(nick)
		else: # remove him from all channels, was a quit
			for c_k in self._channels._chans:
				if self._channels.nick_part(c_k, id):
					self._nicknames.chan_part(nick)
	
	def topic(self, chan, topic):
		chan = irclib.irc_lower(chan)
		self._channels.set_topic(chan, topic)
	def get_topic(self, chan):
		chan = irclib.irc_lower(chan)
		if self._channels.knows_of_chan(chan):
			return self._channels._chans[chan]['topic']
		return None
	def nick(self, old, new):
		self._nicknames.change_nick(old, new)
	def add_nick_mode(self, chan, nick, mode):
		chan = irclib.irc_lower(chan)
		id = self._nicknames._nicks[nick]['id']
		self._channels.nick_mode_add(chan, id, mode)
	def rem_nick_mode(self, chan, nick, mode):
		chan = irclib.irc_lower(chan)
		id = self._nicknames._nicks[nick]['id']
		self._channels.nick_mode_del(chan, id, mode)
	def has_mode(self, chan, nick, mode):
		chan = irclib.irc_lower(chan)
		if self._channels.knows_of_chan(chan):
			if self._nicknames.knows_of_nick(nick):
				id = self._nicknames._nicks[nick]['id']
				#print "Mode for " + nick + " in " + chan + ":"
				#print self._channels._chans[chan]['nickmodes'][id]
				return mode in self._channels._chans[chan]['nickmodes'][id]
		return False
	def inchannel(self, chan, nick):
		chan = irclib.irc_lower(chan)
		if self._channels.knows_of_chan(chan):
			if self._nicknames.knows_of_nick(nick):
				id = self._nicknames._nicks[nick]['id']
				return id in self._channels._chans[chan]['nickmodes']

class Channels:
	def __init__(self):
		self._chans = {}
	
	def add_chan(self, chan):
		if chan not in self._chans:
			data = {}
			data['topic'] = ''
			data['nickmodes'] = {}
			self._chans[chan] = data
	
	def knows_of_chan(self, chan):
		return chan in self._chans
	
	def set_topic(self, chan, topic):
		if chan in self._chans:
			self._chans[chan]['topic'] = topic
		else:
			self._chans[chan] = {'topic': topic}
		#print("{chan}: New Topic: {topic}".format(chan=chan, topic=topic))
	def nick_join(self, chan, id, modes):
		if chan in self._chans:
			if id not in self._chans[chan]['nickmodes']:
				self._chans[chan]['nickmodes'][id] = modes
				return True #was added; need to increment chancount externally
		return False
	
	def nick_part(self, chan, id):
		if chan in self._chans:
			if id in self._chans[chan]['nickmodes']:
				del self._chans[chan]['nickmodes'][id]
				return True
		return False
	
	def nick_mode_add(self, chan, id, mode):
		if chan in self._chans:
			if id in self._chans[chan]['nickmodes']:
				if mode not in self._chans[chan]['nickmodes'][id]:
					self._chans[chan]['nickmodes'][id].append(mode)
	
	def nick_mode_del(self, chan, id, mode):
		if chan in self._chans:
			if id in self._chans[chan]['nickmodes']:
				if mode in self._chans[chan]['nickmodes'][id]:
					self._chans[chan]['nickmodes'][id].remove(mode)
	
	
	
	

class Nicknames:
	def __init__(self):
		self._nicks = {} #dict - nick: data
		self.__freed_ids = []
		self.__id_incr = 0
		#data = dict:
		# 'id': nick id
		# 'host': nick host
		# 'chancount': number of channels
	
	def add_nick(self, nick, host):
		if not self.knows_of_nick(nick):
			data = {}
			if len(self.__freed_ids) == 0:
				data['id'] = self.__id_incr
				self.__id_incr += 1
			else: #reuse expended ids
				data['id'] = self.__freed_ids[0]
				del self.__freed_ids[0]
			data['host'] = host
			data['chancount'] = 0
			self._nicks[nick] = data
		else:
			self._nicks[nick]['host'] = host
	
	def change_nick(self, old, new):
		if self.knows_of_nick(old):
			data = self._nicks[old]
			del self._nicks[old]
			self._nicks[new] = data
	
	#this should only be called if all references to the nick are lost, i. e. if it's parted all channels that we know of
	def del_nick(self, nick):
		if self.knows_of_nick(nick):
			self.__freed_ids.append(self._nicks[nick]['id'])
			del self._nicks[nick]
	
	def knows_of_nick(self, nick):
		return nick in self._nicks
	
	def chan_join(self, nick):
		if self.knows_of_nick(nick):
			self._nicks[nick]['chancount'] += 1
	
	def chan_part(self, nick):
		if self.knows_of_nick(nick):
			self._nicks[nick]['chancount'] -= 1
		if self._nicks[nick]['chancount'] == 0:
			self.del_nick(nick)
