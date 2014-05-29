from __future__ import absolute_import

from .song import Song
from .util import get_hms

import time
import datetime

import config
import hanyuu.queue.legacy_client as legacy_queue

REGULAR = 0
REQUEST = 1
POPPED = 2

class QueueError(Exception):
    pass

class QSong(Song):
    def __init__(self, id=None, meta=None, length=None, type=0, time=None):
        super(QSong, self).__init__(id=id, meta=meta, length=length)
        self.type = type
        self.time = time

    @property
    def until(self):
        return get_hms((self.time - datetime.datetime.now()).total_seconds())

legacy_queue.Song = Song
legacy_queue.QSong = QSong
legacy_queue.QueueError = QueueError
Queue = lambda: legacy_queue.Queue(config.queue_url)
