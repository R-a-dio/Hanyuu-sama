from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import

import unittest

def TestFile():
    # Returns a AudioFile instance for testing.
    import hanyuu.streamer.audio.files as audiofile
    return audiofile.AudioFile("/media/F/test.flac")


from .audio import *

if __name__ == '__main__':
    unittest.main()