from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from . import config
import os

home = os.path.expanduser('~/.hanyuu')
config.load_configuration([home])