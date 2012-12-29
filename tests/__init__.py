from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import sys
import os


# Search path monkey patch for our source code.
sys.path.insert(0, os.path.abspath('..'))
import hanyuu

# Mock the configuration file
from hanyuu import config

# Change our configuration to the test configuration file
config.load_configuration(
                    os.path.join(os.path.dirname(__file__), 'test_config')
                    )


# More mocking to do
def sphinx_documentation_mock():
    """
    Mocks the environment and configure files to allow auto documentation.
    """
    sys.path.pop(0)
    