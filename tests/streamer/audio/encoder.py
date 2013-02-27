import unittest
import hanyuu.streamer.audio.encoder as encoder
import hanyuu.streamer.audio as audio
from tests.streamer import TestFile

default_options = {}
for option, default in encoder.Encoder.options:
    default_options[option] = default
    
class EncoderOpenTest(unittest.TestCase):
    """
    Test cases that don't need a working :class:`Encoder` instance.
    """
    def setUp(self):
        self.encoder = encoder.Encoder(TestFile(),
                                       default_options,
                                       audio.Handlers())
        
    def test_init(self):
        enc = encoder.Encoder(None, default_options, audio.Handlers())
        
    def test_init_options(self):
        options = {
           'lame_settings': ['--cbr', '-b', '320',
                             '--resample', '44.1']
           }
        enc = encoder.Encoder(None, options, audio.Handlers())
        self.assertEqual(enc.settings, options)
        
    def test_start_defaults(self):
        self.encoder.start()
        
    def test_start_options(self):
        options = {
           'lame_settings': ['--cbr', '-b', '320',
                             '--resample', '44.1']
           }
        enc = encoder.Encoder(TestFile(), options, audio.Handlers())
        enc.start()
        
    def tearDown(self):
        self.encoder.close()
        
class EncoderExtendedTest(unittest.TestCase):
    """
    Test cases that require a started :class:`Encoder` instance.
    """
    def setUp(self):
        self.encoder = encoder.Encoder(TestFile(),
                                       default_options,
                                       audio.Handlers())
        self.encoder.start()
        
    def tearDown(self):
        self.encoder.close()