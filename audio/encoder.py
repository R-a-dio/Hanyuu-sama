import subprocess
import threading
import decimal
import time
import select
import logging
import garbage

import datetime

LAME_BIN = 'lame'
logger = logging.getLogger('audio.encoder')


class EncodingError(Exception):
    pass
        

class Encoder(object):
    """An Encoder that handles the encoder process underneath.
    
    It is possible that the actual process to encode with is different
    over time due to crashes or restarts
    """
    def __init__(self, source):
        super(Encoder, self).__init__()
        self.alive = threading.Event()
        
        self.source = source
        self.compression = ['--cbr', '-b', '192', '--resample', '44.1']
        self.mode = 'j'
        
        self.out_file = '-'
        
    def start(self):
        self.alive.clear()
        self.start_instance()
        
    def close(self):
        """Closes the encoder."""
        self.alive.set() # Set ourself to closed so we don't restart instances
        self.instance.close()
        
    def restart(self):
        """Restarts the encoder process underneath."""
        self.report_close() # Hackish way of restarting
        
    def report_close(self):
        """Called when EncoderInstance is closed
        
        This registers the current instance for garbage collection and
        then starts a new instance for use.
        """
        if not self.alive.is_set():
            GarbageInstance(self.instance)
            self.start_instance()
            
    def start_instance(self):
        """Called to create a new EncoderInstance"""
        new = EncoderInstance(self)
        new.start()
        self.instance = new
        
    def __getattr__(self, key):
        """Since we are used as the source to other parts we require
        to have direct access to EncoderInstance methods from ourself."""
        if key == 'instance':
            raise AttributeError("No attribute named 'instance'")
        return getattr(self.instance, key)
    
    
class EncoderInstance(object):
    """Class that represents a subprocessed encoder."""
    def __init__(self, encoder_manager):
        super(EncoderInstance, self).__init__()
        self.encoder_manager = encoder_manager
        
        for key in ['source', 'compression', 'mode', 'out_file']:
            setattr(self, key, getattr(self.encoder_manager, key))
        
        self.running = threading.Event()
        
    def run(self):
        while not self.running.is_set():
            data = self.source.read()
            if data == b'':
                # EOF we just sleep and wait for a new source
                time.sleep(0.3)
            self.write(data)
        try:
            self.process.stdin.close()
            self.process.stdout.close()
            self.process.wait()
        except:
            logger.exception("Failed to cleanly shutdown encoder.")
            
    def start(self):
        self.running.clear()
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
        
        self.thread = threading.Thread(target=self.run,
                                            name='Encoder Feeder')
        self.thread.daemon = True
        self.thread.start()
        
    def switch_source(self, new_source):
        self.source = new_source
        
    def write(self, data):
        try:
            self.process.stdin.write(data)
        except (IOError, ValueError) as err:
            logger.exception("Write failed, restarting encoder.")
            self.close()
            #raise EncodingError(str(err))
        except (Exception) as err:
            logger.exception("Write failed, unknown exception.")
            self.close()
            raise err
        
    def read(self, size=4096, timeout=10.0):
        reader, writer, error = select.select([self.process.stdout],
                                              [], [], timeout)
        if not reader:
            return b''
        return reader[0].read(size)
    
    def close(self):
        self.running.set()
        self.encoder_manager.report_close()
        
        
class GarbageInstance(garbage.Garbage):
    def collect(self):
        # Check if our encoder process is down yet
        returncode = self.item.process.poll()
        
        self.item.thread.join(0.0) # Check if thread can be joined.
        
        if self.item.thread.isAlive() or returncode is None:
            return False
        return True
