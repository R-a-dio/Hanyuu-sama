import encoder
import files
import icecast
import logging


logger = logging.getLogger('audio')


class Manager(object):
    def __init__(self, icecast_config={}, next_file=lambda self: None):
        super(Manager, self).__init__()
        
        self.next_file = next_file
        
        self.source = UnendingSource(self.give_source)
        
        self.encoder = encoder.Encoder(self.source)
        self.encoder.start()
        
        self.icecast = icecast.Icecast(self.encoder, icecast_config)
        self.icecast.connect()
        
    def give_source(self):
        try:
            return files.AudioFile(self.next_file())
        except (files.AudioError) as err:
            logger.exception("Unsupported file.")
            return self.give_source()
    
class UnendingSource(object):
    def __init__(self, source_function):
        super(UnendingSource, self).__init__()
        self.source_function = source_function
        self.source = source_function()
        
        self.eof = False
        
    def read(self, size=4096, timeout=10.0):
        if self.eof:
            return b''
        try:
            data = self.source.read(size, timeout)
        except (ValueError) as err:
            if err.message == 'MD5 mismatch at end of stream':
                pass
        if data == b'':
            self.source = self.source_function()
            if self.source == None:
                self.eof = True
                return b''
        return data
    
    def close(self):
        self.eof = True
        
    def __getattr__(self, key):
        return getattr(self.source, key)
    
import os
def test_dir(directory='/media/F/Music'):
    files = set()
    for base, dir, filenames in os.walk(directory):
        for name in filenames:
            files.add(os.path.join(base, name))
    
    def pop_file():
        filename = files.pop()
        if (filename.endswith('.flac') or
            filename.endswith('.mp3') or
            filename.endswith('.ogg')):
            return filename
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