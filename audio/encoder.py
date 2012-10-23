import subprocess
import threading
import decimal
import time
import select


LAME_BIN = 'lame'


class EncodingError(Exception):
    pass


class Encoder(object):
    def __init__(self, source):
        super(Encoder, self).__init__()
        self.source = source
        self.compression = ['--cbr', '-b', '192', '--resample', '44.1']
        self.mode = 'j'
        
        self.out_file = '-'
        
        self.running = threading.Event()
        
    def run(self):
        while not self.running.is_set():
            data = self.source.read()
            if data == b'':
                # EOF we just sleep and wait for a new source
                time.sleep(0.3)
            self.write(data)
            
    def start(self):
        arguments = [LAME_BIN, '--quiet',
                     '--flush',
                     '-r',
                     '-s', str(decimal.Decimal(self.source.sample_rate) / 1000),
                     '--bitwidth', str(self.source.bits_per_sample),
                     '--signed', '--little-endian',
                     '-m', self.mode] + self.compression + ['-', self.out_file]
                     
        self.process = subprocess.Popen(args=arguments,
                                        stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE)
        
        self.feed_thread = threading.Thread(target=self.run,
                                            name='Encoder Feeder')
        self.feed_thread.daemon = True
        self.feed_thread.start()
        
    def switch_source(self, new_source):
        self.source = new_source
        
    def write(self, data):
        try:
            self.process.stdin.write(data)
        except (IOError, ValueError) as err:
            self.process.stdin.close()
            self.process.stdout.close()
            self.process.wait()
            raise EncodingError(str(err))
        except (Exception) as err:
            self.process.stdin.close()
            self.process.stdout.close()
            self.process.wait()
            raise err
        
    def read(self, size=4096, timeout=10.0):
        reader, writer, error = select.select([self.process.stdout],
                                              [], [], timeout)
        if not reader:
            return b''
        return reader[0].read(size)
    
    def close(self):
        self.running.set()