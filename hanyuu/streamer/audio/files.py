"""Module that handles file access and decoding to PCM.

It uses python-audiotools for the majority of the work done."""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import

from . import garbage
import audiotools


class AudioError(Exception):
    """Exception raised when an error occurs in this module."""
    pass


class GarbageAudioFile(garbage.Garbage):
    """Garbage class of the AudioFile class"""
    def collect(self):
        """Tries to close the AudioFile resources when called."""
        try:
            self.item._reader.close()
        except (audiotools.DecodingError):
            pass
        # Hack to kill zombies below
        import gc, subprocess
        try:
            [item.poll() for item in gc.get_referrers(subprocess.Popen)
             if isinstance(item, subprocess.Popen)]
        except:
            logger.warning("Exception occured in hack.")
        # Hack to kill zombies above
        
        return True
    
    
# TODO: Add handler hooks.
class FileSource(object):
    """
    ======
    Source
    ======
    
    The :class:`FileSource` class expects a function as source.
    
    This function should return an absolute path to a supported audio file as
    an :const:`unicode` or :const:`bytes` object.
    
    =======
    Options
    =======
    
    No options are supported for this class.
    
    ========
    Handlers
    ========
    
    No handlers are supported for this class.
    """
    def __init__(self, source, options, handlers):
        super(FileSource, self).__init__()
        self.source = None

        self.source_function = source
        
        self.options = options
        
        self.handler = handlers
        
        self.eof = False
        
    def start(self):
        """Starts the source"""
        self.eof = False
        self.source = self.change_source()

    def initialize(self):
        """Sets the initial source from the source function."""
        self.start()
        
    def change_source(self):
        """Calls the source function and returns the result if not None."""
        if not (self.source is None):
            self.source.close()
        filename = self.source_function()

        if filename is None:
            return
        
        try:
            audiofile = AudioFile(filename)
        except (files.AudioError) as err:
            logger.exception("Unsupported file.")
            return self.change_source()
        except (IOError) as err:
            logger.exception("Failed opening file.")
            return self.change_source()
        else:
            return audiofile
    
    def read(self, size=4096, timeout=10.0):
        if self.eof:
            return b''
        try:
            data = self.source.read(size, timeout)
        except (ValueError) as err:
            if err.message == 'MD5 mismatch at end of stream':
                data = b''
        if data == b'':
            self.source = self.change_source()
            if self.source == None:
                self.eof = True
                return b''
        return data
    
    def skip(self):
        self.source = self.change_source()
        
    def close(self):
        self.eof = True
        
    def __getattr__(self, key):
        return getattr(self.source, key)
    
    
class AudioFile(object):
    """A Simple wrapper around the audiotools library.
    
    This opens the filename given wraps the file in a PCMConverter that
    turns it into PCM of format 44.1kHz, Stereo, 24-bit depth."""
    def __init__(self, filename):
        super(AudioFile, self).__init__()
        self._reader = self._open_file(filename)
        
    def read(self, size=4096, timeout=0.0):
        """Returns at most a string of size `size`.
        
        The `timeout` argument is unused. But kept in for compatibility with
        other read methods in the `audio` module."""
        return self._reader.read(size).to_bytes(False, True)
    
    def close(self):
        """Registers self for garbage collection. This method does not
        close anything and only registers itself for colleciton."""
        GarbageAudioFile(self)
        
    def __getattr__(self, key):
        try:
            return getattr(self._reader, key)
        except (AttributeError):
            return getattr(self.file, key)
        
    def progress(self, current, total):
        """Dummy progress function"""
        pass

    def _open_file(self, filename):
        """Open a file for reading and wrap it in several helpers."""
        try:
            reader = audiotools.open(filename)
        except (audiotools.UnsupportedFile) as err:
            raise AudioError("Unsupported file")
        
        self.file = reader
        total_frames = reader.total_frames()
        
        # Wrap in a PCMReader because we want PCM
        reader = reader.to_pcm()
        
        
        # Wrap in a converter
        reader = audiotools.PCMConverter(reader, sample_rate=44100,
                                    channels=2,
                                    channel_mask=audiotools.ChannelMask(0x1 | 0x2),
                                    bits_per_sample=24)
        
        # And for file progress!
        reader = audiotools.PCMReaderProgress(reader, total_frames,
                                              self.progress)
        
        return reader

