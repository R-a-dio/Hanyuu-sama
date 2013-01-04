from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import sys
import os


# We add the path above us to the PYTHONPATH to allow non-install testing
sys.path.insert(0, os.path.abspath('..'))
# Test if the PYTHONPATH addition worked

# We don't check if what we import is actually the one above us or one that
# was previously installed. So be cautious of old installs.
import hanyuu


# Mock the configuration file
from hanyuu import config

# Change our configuration to the test configuration file

# The configuration file is in the root instead of in ./res because it's easier
# to find for others this way.
config.load_configuration(
                    os.path.join(os.path.dirname(__file__), 'test_config')
                    )


# More mocking to do
def sphinx_documentation_mock():
    """
    Mocks the environment and configure files to allow auto documentation.
    
    All this really does is remove our PYTHONPATH addition we did earlier
    in this same module because the Sphinx prepare module also does it.
    """
    sys.path.pop(0)
