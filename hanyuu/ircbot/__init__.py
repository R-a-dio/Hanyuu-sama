from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from .. import logger
logger = logger.getChild('ircbot')

# Handler constants
# Channels
ALL_CHANNELS = []
MAIN_CHANNELS = ["#r/a/dio", "#r/a/dio-dev"]
# Nicks
ALL_NICKS = [] # All nicknames can trigger this

ACCESS_MODES = 'qaoh' # Nicks with halfop or higher can trigger this
OP_MODES = 'qao' # Only operators or higher can trigger this
HALFOP_MODES = 'h' # Only half operators can trigger this
VOICE_MODES = 'v' # Only voiced people can trigger this
REGULAR_MODES = 'qaohv' # Only regulars can trigger this