from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import sys
import os


# Search path monkey patch for our source code.
sys.path.insert(0, '..')
import hanyuu

# Mock the configuration file
from hanyuu import config

# Change our configuration to the test configuration file
config.load_configuration(
                    os.path.join(os.path.dirname(__file__), 'test_config')
                    )


# More mocking to do
