from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import

import peewee
import time

from .. import config
from ..db import models
from .. import abstractions
import logging


logger = logging.getLogger('hanyuu.queue')

REGULAR = 0
REQUEST = 1
POPPED = 2

class QueueError(Exception):
    pass

class Queue(object):
    def __init__(self, dj=None):
        if dj != None:
            self.dj = models.DJ.get(models.DJ.id == dj)
        else:
            self.dj = None
    
    def __len__(self):
        return self.length
    
    @property
    def length(self):
        return self._create_select_query().count()
    
    def get_time_placement(self, type=REGULAR):
        result = None
        if type == REGULAR:
            # if we want to add a regular, it goes at the end
            # of the queue
            query = self._create_select_query()\
                        .order_by(models.Queue.time.desc())
        elif type == REQUEST:
            # requests need to be added after the last request
            query = self._create_select_query()\
                        .where(models.Queue.type == REQUEST |
                               models.Queue.type == POPPED)\
                        .order_by(models.Queue.time.desc())
        if query.count() > 0:
            # take the time of the last song and then add the length
            # to that
            result = time.mktime(query[0].time.timetuple())
            result += query[0].song.length
        return result or time.time()
    
    def append(self, song, type=REGULAR):
        if not self.dj:
            raise QueueError('cannot append to a Queue without a dj')
        
    
    def _create_select_query(self):
        query = models.Queue.select()
        if self.dj:
            query = query.where(models.Queue.dj == self.dj)
        return query
    