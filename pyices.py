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
		print "Opening a file"
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
class AudioMP3Converter(Thread):
	def __init__(self, filename, PCM):
		Thread.__init__(self)
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
		self._file_queue = deque()
		self._next_file, self._current_file = (None, None)
		self.start()

	def run(self):
		print "starting AudioPCMVirtual"
		self.PCM = AudioPCMVirtual(self._next_file)
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
	def file(self, file):
		self._file_queue.append(file)
	def _next_file(self):
		while (len(self._file_queue) == 0):
			sleep(0.1)
		self._current_file = self._file_queue.popleft()
		return self._current_file
	def progress(self):
		try:
			return 100.0 / self.PCM.total * self.PCM.current
		except (AttributeError):
			return 0.0
		