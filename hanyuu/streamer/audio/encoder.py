from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import

from . import garbage
from . import logger
logger = logger.getChild('encoder')

import subprocess
import threading
import decimal
import time
import select
import logging


#: The path to the LAME binary. This can be just 'lame' on bash environments.
LAME_BIN = 'lame'


class Encoder(object):
    """An Encoder class that handles the encoder subprocess underneath.
    
    This expects various things from the **source** given.
    
    The source should have the following characteristics:
    
        :func:`read`: A function that accepts a single integer argument that is
                      the amount of bytes to return. It should return PCM audio
                      data in a supported format.
                      
        :attr:`sample_rate`: The sample rate of the audio data. This should be
                             the full integer of the sample rate (44100 instead
                             of 44.1)
                             
        :attr:`bits_per_sample`: The bits per sample of the audio data. This
                                 can be 16, 24 and 32 bits.
                                 

    .. note::
        The Encoder class can restart the encoder transparently when an error
        occurs. This means that you should never use the underlying
        :class:`EncoderInstance` class anywhere in your code but always use 
        the actual :class:`Encoder` class instead.
    """
    options = [('lame_settings',
                ['--cbr', '-b', '192', '--resample', '44.1'])]
    def __init__(self, source, lame_settings):
        """
        :params lame_settings:
                This should be a list of lame options to pass to the lame
                binary. This should be used for the encoding options, other
                options are handled by the class already.
                
                The default is to encode to CBR192 @ 44.1kHz and joint stereo.
                
        .. note::
            The 'joint stereo' flag is implicitly set inside the class and
            can't be changed through the :obj:`lame_settings`.
        """
        super(Encoder, self).__init__()
        self.alive = threading.Event()
        
        self.source = source
        
        #: The settings for encoding to pass to lame as a list.
        self.encoding_settings = lame_settings
        
        # This is an implicit 'joint stereo' setting for lame.
        self.mode = 'j'
        
        # We use an option to specify where lame should send the output as well.
        # This way we can change it easier.
        self.out_file = '-'
        
    def start(self):
        """
        This clears our `alive` flag and starts a new :class:`EncoderInstance`
        instance by calling :meth:`start_instance`.
        """
        self.alive.clear()
        self.start_instance()
        
    def close(self):
        """
        This calls the :meth:`EncoderInstance.close` method on the
        :class:`EncoderInstance`.
        """
        self.alive.set() # Set ourself to closed so we don't restart instances
        self.instance.close()
        
    def restart(self):
        """
        This method rather then restart, destroys and then recreates the
        underlying :class:`EncoderInstance` instance.
        """
        # A kinda hackish way of restarting the instance.
        # This is the easiest way of restarting the instance without actually
        # calling `close` which would create a short time without encoder.
        self.report_close()
        
    def report_close(self):
        """
        This method is called by the :class:`EncoderInstance` class when it
        gets closed or an error occurs in the instance. This should handle
        the case gracefully and even restart the instance if the close was
        unintentional by the user.
        
        The method registers the :class:`EncoderInstance` instance for garbage
        collection by the :mod:`garbage` module.
        """
        if not self.alive.is_set():
            GarbageInstance(self.instance)
            self.start_instance()
            
    def start_instance(self):
        """
        This method is responsible for creating and starting the 
        :class:`EncoderInstance` class instances.
        
        
        This creates a new :class:`EncoderInstance` instance and calls the
        :meth:`EncoderInstance.start` method on it.
        
        After the call to 'start' returns the new instance is assigned to
        :attr:`instance`.
        """
        # Don't assign it to the instance directly because that would allow
        # a different thread to accidently touch a non-started instance
        new = EncoderInstance(self)
        new.start()
        self.instance = new
        
    def __getattr__(self, key):
        """
        We are passed along as a source through the audio pipeline. This means
        we are required to have some attributes that are often on the
        :class:`EncoderInstance` instead of on :class:`Encoder`.
        
        This delegates the attribute lookups we don't have to the
        :class:`EncoderInstance` instead.
        """
        # This is to make sure we don't run into an infinite recursion. Since
        # the below call to 'getattr' uses `self.instance`.
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