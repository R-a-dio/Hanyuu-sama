from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import hanyuu.db.common as db
import peewee
import os.path


db.radio_database = peewee.SqliteDatabase(os.path.join(os.path.dirname(__file__),
                                                       '../res/test.db'))
