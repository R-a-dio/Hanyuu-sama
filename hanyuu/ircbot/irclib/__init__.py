from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from .. import logger
logger = logger.getChild('irclib')

#from . import session

# Handler constants
# Channels
ALL_CHANNELS = 0
MAIN_CHANNELS = ["#r/a/dio", "#r/a/dio-dev"]
PRIVATE_MESSAGE = 1
# Nicks
ALL_NICKS = 0 # All nicknames can trigger this
ACCESS_NICKS = 1 # Nicks with halfop or higher can trigger this
OP_NICKS = 2 # Only operators or higher can trigger this
HALFOP_NICKS = 3 # Only half operators can trigger this
VOICE_NICKS = 4 # Only voiced people can trigger this
REGULAR_NICKS = 5 # Only regulars can trigger this
DEV_NICKS = 6 # Only the nicknames defined in config.irc_devs can trigger this