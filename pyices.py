import audiotools
import shout
from collections import deque
from time import sleep, time
from threading import Thread, RLock
from os import mkfifo, remove, path, urandom
from traceback import format_exc
import logging
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
	
	def play(self, file, metadata):
		"""Checks if the player is idle or not, if idle, start playing
		'file' with 'metadata' as tags, else queue 'file' with 'metadata'
		
		file  		- filename, open file object, file-like object
		
		metadata	- String containing the tags to send to server
		
		Note: file-like object has to support 'object.read(size)'
		"""
		pass
	
	def queue(self):
		"""Returns internal queue in format [(file, metadata), ...]"""
		pass
	
	def bitrate(self):
		"""Returns bitrate of current track, estimate and can be off"""
		pass
	
	def metadata(self):
		pass
	
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

	def del_handle(self, event, handle, priority=0):
		"""Deletes a handler for 'event' linked to method 'handle'
		
		See 'add_handle' for 'event' list
		"""

	def connect(self):
		pass
		
	def disconnect(self, force=False):
		pass
		
	def shutdown(self, force=False):
		"""Stops streaming after finishing the current file, if force=True
		the current file is interrupted"""
		pass
	
	def __play(self, file, metadata):
		"""Internal method"""
		pass
	
	def __queue(self, file, metadata):
		"""Internal method"""
		pass
	
	def __set_attribute(self, attribute, value):
		"""Internal method"""
		pass
	
	def __size(self, file):
		"""Internal method"""
		pass
	def __ready_next(self, object):
		"""Internal method"""
		pass
	def __next(self, object):
		"""Internal method"""
		pass
	def __loadfile(self, f):
		"""Internal method"""
		pass
	def __call(self, target):
		"""Internal method"""
		pass
	def __disconnect(self, object):
		pass
	def run(self):
		"""Internal method"""
		pass
	def __clean(self, method):
		"""Internal method"""
		pass
	def __shoutcheck(self, shouterr):
		pass
	

class AudioFile(object):
	"""
		Class that handles conversion of several input files to
		a single big mp3 file kept in memory.
		
			methods:
				read(bytes):
					Reads maximum bytes from mp3 in memory, this is
					rarely actually the amount of bytes specified.
				add_file(filename):
					Adds the filename to queue for converting, the
					encoder waits if there are no files left to do.
				close():
					Cleans up the Class, afterwards calling read(bytes)
					will return an empty string, progress() will return
					0.0 and add_file(filename)
					and close() do nothing.
				progress():
					returns the process of the current file in the
					transcoder, the value is a float between 0 and 100.
	"""
	def __init__(self, format="mp3"):
		if (not converters.has_key(format)):
			raise UnsupportedFormat("{format} is not a valid format"\
								.format(format=format))
		self._temp_filename = path.join('/dev/shm/', '{temp}.AudioFile'\
							.format(temp=md5.new(urandom(20)).hexdigest()))
		try:
			mkfifo(self._temp_filename)
		except OSError:
			pass
		self._active = True
		self._file_queue = deque()
		self._handlers = {}
		self._PCM = AudioPCMVirtual(self._handlers, self._file_queue)
		self._CON = converters[format](self._temp_filename, self._PCM)
		self._file = open(self._temp_filename)
		
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
		if (self._handlers.get(event)):
			self._handlers[event].append((priority, handle))
		else:
			self._handlers.update({event: [(priority, handle)]})
		self._handlers[event].sort(reverse=True)
	def del_handle(self, event, handle, priority=0):
		"""Deletes a handler for 'event' linked to method 'handle'
		
		See 'add_handle' for 'event' list
		"""
		if (self._handlers.get(event)):
			try:
				self._handlers[event].remove((priority, handle))
			except ValueError:
				pass
	def read(self, bytes):
		"""Read at most `bytes` from the finished file
		most of the time won't return the actual bytes"""
		if (self._active):
			return self._file.read(bytes)
		return ''
	def close(self):
		"""Will clean up the AudioFile object,
		
		does this by feeding a EOF to AudioMP3Converter and
		removing all references to AudioPCMVirtual afterwards"""
		if (self._active):
			self._active = False
			self._PCM.close()
			self._file.read(16384)
			self._file.close()
			remove(self._temp_filename)
	def add_file(self, file):
		"""Add a file to the queue for transcoding"""
		if (self._active):
			self._file_queue.append(file)
	def progress(self):
		"""Returns the progress of encoding the current file
		as a float in percentage"""
		try:
			return 100.0 / self._PCM.total * self._PCM.current
		except (AttributeError):
			return 0.0
		
class AudioPCMVirtual(Thread):
	"""
	
	This class shouldn't be used by anything else than the AudioFile class
	
	Make several files look like a single PCMReader
	
		queue is a queue-like object that supports queue.popleft() that
			raises IndexError if no item is available. AudioFile() uses
			collections.deque
		
		sample_rate:
			The sample rate of this audio stream, in Hz, as a positive integer.
		channels:
			The number of channels in this audio stream as a positive integer.
		channel_mask:
			The channel mask of this audio stream as a non-negative integer.
		bits_per_sample:
			The number of bits-per-sample in this audio stream as a
			positive integer.
	"""
	def __init__(self, handlers, queue, sample_rate=44100, channels=2, channel_mask=None,
				bits_per_sample=16):
		Thread.__init__(self)
		self.daemon = True
		self.sample_rate = sample_rate
		self._handlers = handlers
		self.channels = channels
		if (not channel_mask):
			self.channel_mask = audiotools.ChannelMask\
								.from_fields(front_left=True, front_right=True)
		else:
			self.channel_mask = channel_mask
		self.bits_per_sample = bits_per_sample
		self.current = 0.0
		self.total = 0.0
		self._file_queue = queue
		self._active = True
		self.reader = None
		self.start()
		
	def run(self):
		self.open_file()
		self._call("start")
	def get_new_file(self):
		# First get a new file from the queue
		new_file = None
		new_audiofile = None
		while (self._active):
			try:
				new_file = self._file_queue.popleft()
			except (IndexError):
				sleep(0.1)
			else:
				# Try to open our new file
				try:
					new_audiofile = audiotools.open(new_file)
				except (IOError):
					logging.error("File cannot be opened at all ({file})"\
								.format(file=new_file))
				except (audiotools.UnsupportedFile):
					logging.error("Unsupported file used ({file})"\
								.format(file=new_file))
				else:
					# success we have a new file
					logging.debug("Opened audio file ({file})"\
								.format(file=new_file))
					break
		return new_audiofile
	def open_file(self):
		self._track_finishing = True
		logging.debug("Opening a file in AudioPCMVirtual({ident})"\
					.format(ident=self.ident))
		audiofile = self.get_new_file()
		if (audiofile == None):
			return self.read
		reader = audiotools.PCMConverter(audiofile.to_pcm(), self.sample_rate,
										self.channels, self.channel_mask,
										self.bits_per_sample)
		frames = audiofile.total_frames()
		self.reader = audiotools.PCMReaderProgress(reader, frames,
												 self.progress_method)
		
	def read(self, bytes):
		while ((not self.reader) and (self._active)):
			sleep(0.1)
		if (not self._active):
			return ''
		read = self.reader.read(4096)
		if (len(read) == 0):
			# call finish handler
			self._call("finish")
			self.open_file()
			while (len(read) == 0):
				sleep(0.1)
				read = self.reader.read(4096)
			# call start handler
			self._call("start")
		return read
		
	def close(self):
		self._active = False
		try:
			self.reader.close()
		except (AttributeError):
			pass
	def progress_method(self, current, total):
		"""internal method"""
		self.current = current
		self.total = total
		if ((self._track_finishing) and ((100.0 / total * current) >= 90.0)):
			self._call("finishing")
			self._track_finishing = False
	def _call(self, target):
		"""Internal method"""
		logging.debug("AudioPCMVirtual(%(thread)d) Calling handler: {target}".format(target=target))
		try:
			handles = self._handlers[target]
			for h in handles:
				try:
					if (h[1](self) == 'UNHANDLE'):
						del handles[h]
				except:
					logging.warning(format_exc())
		except (KeyError):
			logging.debug("AudioPCMVirtual(%(thread)d) No handler: {target}".format(target=target))
		except:
			logging.exception("AudioPCMVirtual(%(thread)d)")
			
class AudioConverter(Thread):
	"""Generic wrapper around an audiotools.FORMAT.from_pcm function"""
	format_class = audiotools.MP3Audio
	format_invalid = audiotools.InvalidMP3
	def __init__(self, filename, PCM):
		Thread.__init__(self)
		self.daemon = True
		self.filename = filename
		self.PCM = PCM
		self.start()
	def run(self):
		logging.debug("AudioConverter({ident}) has started"\
					.format(ident=self.ident))
		try:
			self.format_class.from_pcm(self.filename, self.PCM)
		except (self.format_invalid):
			pass
		logging.debug("AudioConverter({ident}) has exited"\
					.format(ident=self.ident))
		
class AudioMP3Converter(AudioConverter):
	"""Wrapper around audiotools.MP3Audio.from_pcm to run in a
	separate thread"""
	format_class = audiotools.MP3Audio
	format_invalid = audiotools.InvalidMP3
		
class AudioVorbisConverter(AudioConverter):
	"""Wrapper around audiotools.VorbisAudio.from_pcm to run in a
	separate thread"""
	format_class = audiotools.VorbisAudio
	format_invalid = audiotools.InvalidVorbis
		
class AudioFlacConverter(Thread):
	"""Wrapper around audiotools.FlacAudio.from_pcm to run in a
	separate thread"""
	format_class = audiotools.FlacAudio
	format_class = audiotools.InvalidFLAC

converters = {'mp3': AudioMP3Converter, 'flac': AudioFlacConverter,
				"vorbis": AudioVorbisConverter}