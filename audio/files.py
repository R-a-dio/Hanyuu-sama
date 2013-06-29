"""Module that handles file access and decoding to PCM.

It uses python-audiotools for the majority of the work done."""
import audiotools
import garbage
import logging
import bootstrap

bootstrap.logging_setup()

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
        import gc
        import subprocess
        try:
            [item.poll() for item in gc.get_referrers(subprocess.Popen)
             if isinstance(item, subprocess.Popen)]
        except:
            logging.warning("Exception occured in hack.")
        # Hack to kill zombies above

        return True


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
        except (audiotools.UnsupportedFile):
            logging.exception("Unsupported File - Check dependencies")
            raise AudioError("Unsupported file")

        self.file = reader
        total_frames = reader.total_frames()

        # Wrap in a PCMReader because we want PCM
        reader = reader.to_pcm()

        # Wrap in a converter
        reader = audiotools.PCMConverter(reader, sample_rate=44100,
                                         channels=2,
                                         channel_mask=audiotools.ChannelMask(
                                         0x1 | 0x2),
                                         bits_per_sample=24)

        # And for file progress!
        reader = audiotools.PCMReaderProgress(reader, total_frames,
                                              self.progress)

        return reader
