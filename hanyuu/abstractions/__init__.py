"""
package to abstract the database from the rest of the code.

For users:
    submodules are grouped by their overarcing thema such as DJ profiles and
    users in the same submodule, track information in the same submodule,
    AFK streamer information in the same submodule, etc.
    
For developers:
    submodules should be of the grouping type where closely related data
    structures are placed together in a module.
"""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from .. import logger


logger = logger.getChild('abstractions')