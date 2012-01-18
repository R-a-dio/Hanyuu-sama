import audiotools
import shout
from collections import deque
from time import sleep, time
from threading import Thread, RLock
from multiprocessing import Process, Queue
from os import mkfifo, remove, path, urandom
from traceback import format_exc
import md5

class instance(Thread):
	"""Wrapper around shout.Shout

	Requires at least host, port, password and mount to be specified
	in the 'attributes' which should be a dictionary which can contain:

       host - name or address of destination server
       port - port of destination server
       user - source user name (optional)
   password - source password
      mount - mount point on server (relative URL, eg "/stream.ogg")
   protocol - server protocol: "http" (the default) for icecast 2,
              "xaudiocast" for icecast 1, or "icy" for shoutcast
nonblocking - use nonblocking send
     format - audio format: "ogg" (the default) or "mp3"
       name - stream name
        url - stream web page
      genre - stream genre
description - longer stream description
 audio_info - dictionary of stream audio parameters, for YP information.
              Useful keys include "bitrate" (in kbps), "samplerate"
              (in Hz), "channels" and "quality" (Ogg encoding
              quality). All dictionary values should be strings. The known
              keys are defined as the SHOUT_AI_* constants, but any other
              will be passed along to the server as well.
   dumpfile - file name to record stream to on server (not supported on
              all servers)
      agent - for customizing the HTTP user-agent header"""
	def __init__(self, attributes):
		Thread.__init__(self)
		self.__shout = shout.Shout()
		self.__handlers = {}
		self.__start = True
		self.__active = True
		self.__ready = True
		self.__lock = RLock()
		self.__forceshut = False
		self.__wait = True
		self._virtual_file = AudioFile()
		self.daemon = 1
		self.stats = {'position':None, 'st_time': 0, 'ed_time': 0,
						'bitrate': 0}
		self.__queue_f = deque()
		self.__submit = False
		for key, item in attributes.iteritems():
			self.__set_attribute(key, item)
		
		# internal handlers
		self.add_handle('finishing', self.__ready_next, -10)
		self.add_handle('finish', self.__next, -10)
		self.add_handle('disconnect', self.__disconnect, -10)
	
	def play(self, file, metadata):
		"""Checks if the player is idle or not, if idle, start playing
		'file' with 'metadata' as tags, else queue 'file' with 'metadata'
		
		file  		- filename, open file object, file-like object
		
		metadata	- String containing the tags to send to server
		
		Note: file-like object has to support 'object.read(size)'
		"""
		if (self.__ready):
			self.__play(file, metadata)
		else:
			self.__queue(file, metadata)

	def queue(self):
		"""Returns internal queue in format [(file, metadata), ...]"""
		return list(self.__queue_f)

	def bitrate(self):
		"""Returns bitrate of current track, estimate and can be off"""
		br = self.stats['position']*0.008/(time()-self.stats['st_time'])
		self.stats['bitrate'] = br
		return br

	def metadata(self):
		return self.__metadata
		
	def add_handle(self, event, handle, priority=0):
		"""Adds a handler for 'event' to a method 'handle'
		
		Event can be:
			'start'		- Start of a song
			
			'finishing'	- Song is finishing, 90% of song is played
			
			'finish'	- Song finished
		
		Handle can be:
			Any method that accepts one parameter, the
			streamer.instance object.
		"""
		if (self.__handlers.get(event)):
			self.__handlers[event].append((priority, handle))
		else:
			self.__handlers.update({event: [(priority, handle)]})
		self.__handlers[event].sort(reverse=True)
	def del_handle(self, event, handle, priority=0):
		"""Deletes a handler for 'event' linked to method 'handle'
		
		See 'add_handle' for 'event' list
		"""
		if (self.__handlers.get(event)):
			try:
				self.__handlers[event].remove((priority, handle))
			except ValueError:
				pass
	def connect(self):
		pass
		
	def disconnect(self, force=False):
		pass
		
	def shutdown(self, force=False):
		"""Stops streaming after finishing the current file, if force=True
		the current file is interrupted"""
		self.__active = False
		self.__forceshut = force

	def __play(self, file, metadata):
		"""Internal method"""
		self.__file, self.__filenormal = self.__loadfile(file)
		self.__filesize = self.__size(self.__file)
		self.__metadata = metadata
		self.__submit = True
		if (self.__start):
			self.__start = False
			self.__playing = True
			self.__ready = False
			self.__wait = False
			self.start()
	def __queue(self, file, metadata):
		"""Internal method"""
		self.__queue_f.append((file, metadata))
	
	def __set_attribute(self, attribute, value):
		"""Internal method"""
		setattr(self.__shout, attribute, value)
		self.stats[attribute] = value
		
	def __size(self, file):
		"""Internal method"""
		try:
			pos = file.tell()
			file.seek(0,2)
			size = file.tell()
			file.seek(pos)
			return size
		except:
			return -1

	def __ready_next(self, object):
		"""Internal method"""
		try:
			file, metadata = self.__queue_f.pop()
			self.__wait = False
		except IndexError:
			self.__wait = True
		else:
			self.__next_metadata = metadata
			self.__next_file, self.__next_filenormal = self.__loadfile(file)
			self.__next_filesize = self.__size(self.__next_file)
			self.__next_ready = True
		
	def __next(self, object):
		"""Internal method"""
		if (self.__next_ready):
			self.__lock.acquire()
			self.__file = self.__next_file
			self._virtual_file._next_file = self.__file
			self.__filenormal = self.__next_filenormal
			self.__filesize = self.__next_filesize
			self.__metadata = self.__next_metadata
			self.__submit = True
			self.__lock.release()
			del self.__next_file
			del self.__next_filenormal
			del self.__next_metadata
			del self.__next_filesize
		else:
			try:
				file, metadata = self.__queue_f.pop()
				self.__wait = False
			except IndexError:
				self.__wait = True
			else:
				self.__metadata = metadata
				del metadata
				self.__file, self.__filenormal = self.__loadfile(file)
				self.__filesize = self.__size(file)
				del file
				
	def __loadfile(self, f):
		"""Internal method"""
		t = type(f)
		if (t == str) or (t == unicode):
			f = open(f, 'rb')
			normal = True
		elif (t == file):
			normal = True
		else:
			normal = False
		return (f, normal)

	def __call(self, target):
		"""Internal method"""
		try:
			handles = self.__handlers[target]
			for h in handles:
				try:
					h[1](self)
				except:
					print format_exc()
		except:
			print format_exc()
	
	def __disconnect(self, object):
		object._instance__active = False
		
	def run(self):
		"""Internal method"""
		_shout = self.__shout
		try:
			self.__shout.open()
		except (shout.ShoutException):
			self.__call('disconnect')
		while self.__active:
			if (self.__wait):
				sleep(0.1)
			else:
				self.__lock.acquire()
				if (self.__submit):
					if (type(self.__metadata) != str):
						self.__metadata = self.__metadata.encode('utf-8', 'replace')
					try:
						_shout.set_metadata({'song': self.__metadata})
					except (shout.ShoutException):
						self.__call('disconnect')
					self.stats['metadata'] = self.__metadata
					self.__submit = False
				if (self.__filenormal):
					self.stats['position'] = 0
				setoff = False
				if (self.__filesize != -1):
					alarm = self.__filesize * 0.90
					alarm = int(alarm)
					setoff = True
				self.stats['st_time'] = time()
				self.stats['bitrate'] = 0
				source = self.__file
				self.stats['file'] = self.__file
				nbuffer = source.read(4096)
				self.__call('start')
				while 1:
					if (self.__forceshut):
						break
					buffer = nbuffer
					nbuffer = source.read(4096)
					lbuffer = len(buffer)
					self.stats['position'] += lbuffer
					if (lbuffer == 0):
						break
					if (setoff):
						if (self.stats['position'] > alarm):
							self.__call('finishing')
							setoff = False
					try:
						_shout.send(buffer)
						_shout.sync()
					except (shout.ShoutException):
						self.__call('disconnect')
				if (self.__ready):
					self.__clean(0)
				elif (self.__active):
					self.__clean(0)
				else:
					self.__clean(1)
				self.__lock.release()
				if (self.__active):
					self.__call('finish')
		self.__call('disconnect')
	def __clean(self, method):
		"""Internal method"""
		if (method == 0):
			# Cleanup for next file
			if (self.__filenormal):
				self.__file.close()
		elif (method == 1):
			# Cleanup for the whole instance
			self.__call('disconnect')
			try:
				self.__file.close
			except:
				del self.__file
			shouterr = self.__shout.close()
	
	def __shoutcheck(self, shouterr):
		if shouterr in (shout.SHOUTERR_NOCONNECT,
						shout.SHOUTERR_NOLOGIN,
						shout.SHOUTERR_MALLOC,
						shout.SHOUTERR_UNCONNECTED,
						shout.SHOUTERR_SOCKET):
			self.__shout.close()
			self.__call('disconnect')

class AudioPCMVirtual(Thread):
	"""Make several files look like a single PCMReader
	
		filefunction is a function that returns a filename to open next.
		
		sample_rate:
			The sample rate of this audio stream, in Hz, as a positive integer.
		channels:
			The number of channels in this audio stream as a positive integer.
		channel_mask:
			The channel mask of this audio stream as a non-negative integer.
		bits_per_sample:
			The number of bits-per-sample in this audio stream as a positive integer.
	"""
	def __init__(self, filefunction, sample_rate=44100, channels=2, channel_mask=None,
				bits_per_sample=16):
		Thread.__init__(self)
		self.daemon = True
		self.sample_rate = sample_rate
		self.channels = channels
		if (not channel_mask):
			self.channel_mask = audiotools.ChannelMask.from_fields(front_left=True, front_right=True)
		else:
			self.channel_mask = channel_mask
		self.bits_per_sample = bits_per_sample
		self._available = False
		
		self.next_file = filefunction
		
		self.start()
	def run(self):
		self._open_file()
	def _open_file(self):
		audiofile = audiotools.open(self.next_file())
		reader = audiotools.PCMConverter(audiofile.to_pcm(), self.sample_rate, self.channels, self.channel_mask, self.bits_per_sample)
		frames = audiofile.total_frames()
		self.reader = audiotools.PCMReaderProgress(reader, frames, self.progress_method)
		self._available = True
		
	def read(self, bytes):
		while (not self._available):
			sleep(0.1)
		read = self.reader.read(bytes)
		while (len(read) == 0):
			sleep(0.1)
		print read, len(read)
		return read
		
	def close(self):
		pass
		
	def progress_method(self, current, total):
		self.current = current
		self.total = total
		if (current >= total):
			self._available = False
			self._open_file()
class AudioMP3Converter(Process):
	def __init__(self, filename, PCM):
		Process.__init__(self)
		self.daemon = True
		self.filename = filename
		self.PCM = PCM
		self.start()
	def run(self):
		audiotools.MP3Audio.from_pcm(self.filename, self.PCM)
class AudioFile(Thread):
	def __init__(self):
		Thread.__init__(self)
		self.daemon = True
		self._temp_filename = path.join('/dev/shm/', '{temp}.mp3'.format(temp=md5.new(urandom(20)).hexdigest()))
		try:
			mkfifo(self._temp_filename)
		except OSError:
			pass
		self._next_file, self._current_file = (None, None)
		self.start()

	def run(self):
		print "starting AudioPCMVirtual"
		self.PCM = AudioPCMVirtual(self.next_file)
		print "done AudioPCMVirtual, starting CON"
		self.CON = AudioMP3Converter(self._temp_filename, self.PCM)
		print "done CON, starting file"
		self.file = open(self._temp_filename)
		print "done file"
	def read(self, bytes):
		self.file.read(bytes)
	def close(self):
		self.file.close()
		remove(self._temp_filename)
		self.PCM.close()
		self.CON.terminate()
	def next_file(self):
		while (not self._next_file):
			sleep(0.1)
		self._current_file = self._next_file
		return self._current_file
	def progress(self):
		return 100.0 / self.PCM.total * self.PCM.current