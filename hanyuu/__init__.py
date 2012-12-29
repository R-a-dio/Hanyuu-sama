from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from . import config
import os
import logging

import sys
print(sys.path[0])

logger = logging.getLogger('hanyuu')

home = os.path.expanduser('~/.hanyuu')
relative = os.path.abspath('./.hanyuu')
config.load_configuration([home, relative])