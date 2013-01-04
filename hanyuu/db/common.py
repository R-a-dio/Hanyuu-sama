from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from .. import config
import logging
import peewee


logger = logging.getLogger('hanyuu.db.common')
# TODO: Temporary for testing.

adapters = {'mysql': peewee.MySQLDatabase,
            'postgresql': peewee.PostgresqlDatabase,
            'sqlite': peewee.SqliteDatabase}

try:
    db_type = config.get('database', 'type')
    adaptor = adapters[db_type]
except KeyError:
    raise ValueError("Unknown database type '{:s}' given.".format(db_type))
except NoSectionError:
    if config.sphinx:
        pass
    else:
        raise
