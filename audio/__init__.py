import encoder
import files
import icecast
import logging
import garbage
import audiotools


# Remove this 
logging.basicConfig(level=logging.DEBUG)
# Remove that ^


logger = logging.getLogger('audio')


class Manager(object):
    def __init__(self, icecast_config={}, next_file=lambda self: None):
        super(Manager, self).__init__()
        
        self.started = False
        
        self.next_file = next_file
        
        logger.debug("Creating source instance.")
        self.source = UnendingSource(self.give_source)
        
        logger.debug("Creating encoder instance.")
        self.encoder = encoder.Encoder(self.source)
        
        logger.debug("Creating icecast instance.")
        self.icecast = icecast.Icecast(self.encoder, icecast_config)
        
    def start(self):
        if not self.started:
            self.source.initialize()
            self.encoder.start()
            self.icecast.connect()
            self.started = True
            
    def connected(self):
        """Returns if icecast is connected or not"""
        return self.icecast.connected()
    
    def give_source(self):
        filename, meta = self.next_file()
        if filename is None:
            self.close()
        try:
            audiofile = files.AudioFile(filename)
        except (files.AudioError) as err:
            logger.exception("Unsupported file.")
            return self.give_source()
        except (IOError) as err:
            logger.exception("Failed opening file.")
            return self.give_source()
        else:
            print meta
            if hasattr(self, 'icecast'):
                self.icecast.set_metadata(meta)
            return audiofile
    
    def close(self):
        self.source.close()
        
        self.encoder.close()
        
        self.icecast.close()
        
        self.started = False

class UnendingSource(object):
    def __init__(self, source_function):
        super(UnendingSource, self).__init__()
        self.source_function = source_function
        
        self.eof = False
        
    def initialize(self):
        self.source = self.source_function()
        
    def change_source(self):
        self.source.close()
        return self.source_function()
    
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
    
    
import os
import mutagen
def test_dir(directory=u'/media/F/Music', files=None):
    files = set() if files is None else files
    for base, dir, filenames in os.walk(directory):
        for name in filenames:
            files.add(os.path.join(base, name))
    
    def pop_file():
        try:
            filename = files.pop()
        except KeyError:
            return (None, None)
        if (filename.endswith('.flac') or
                filename.endswith('.mp3') or
                filename.endswith('.ogg')):
            try:
                meta = mutagen.File(filename, easy=True)
            except:
                meta = "No metadata available, because I errored."
            else:
                artist = meta.get('artist')
                title = meta.get('title')
                
                meta = u"{:s} - {:s}" if artist else u"{:s}"
                
                if artist:
                    artist = u", ".join(artist)
                if title:
                    title = u", ".join(title)
                meta = meta.format(artist, title)
            return (filename, meta)
        else:
            return pop_file()
    return pop_file

def test_config(password=None):
    return {'host': 'stream.r-a-d.io',
            'port': 1130,
            'password': password,
            'format': 1,
            'protocol': 0,
            'mount': 'test.mp3'}