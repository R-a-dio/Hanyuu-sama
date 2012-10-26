import audiotools
import garbage


class AudioError(Exception):
    pass


class GarbageAudioFile(garbage.Garbage):
    def collect(self):
        try:
            self.item.close()
        except (audiotools.DecodingError):
            pass
        return True
    
    
class AudioFile(object):
    def __init__(self, filename):
        super(AudioFile, self).__init__()
        self._reader = self._open_file(filename)
        
    def read(self, size=4096, timeout=0.0):
        return self._reader.read(size).to_bytes(False, True)
    
    def close(self):
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

