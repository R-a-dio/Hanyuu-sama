from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import logging
import peewee


logger = logging.getLogger('db')
# TODO: Temporary for testing.
radio_database = peewee.SqliteDatabase('test.db')