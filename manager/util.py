from __future__ import absolute_import
import time
import functools
import threading

import MySQLdb
import MySQLdb.cursors
import elasticsearch

import config


elasticsearch_instance = elasticsearch.Elasticsearch(config.elasticsearch_server)


def search(query, limit=5):
    query = {
       "query": {
           "match": {
                "_all": {
                    "query": query,
                    "operator": "and",
                }
            },
        },
        "from": 0, "size": limit,
    }

    res = elasticsearch_instance.search(config.elasticsearch_index, body=query)

    return (item['_source'] for item in res['hits']['hits'])


class MySQLCursor(object):
    """Return a connected MySQLdb cursor object"""
    counter = 0
    cache = {}

    def __init__(self, cursortype=MySQLdb.cursors.DictCursor, lock=None):
        threadid = threading.current_thread().ident
        if (threadid in self.cache):
            self.conn = self.cache[threadid]
            self.conn.ping(True)
        else:
            self.conn = MySQLdb.connect(host=config.dbhost,
                                        user=config.dbuser,
                                        passwd=config.dbpassword,
                                        db=config.dbtable,
                                        charset='utf8',
                                        use_unicode=True)
            self.cache[threadid] = self.conn
        self.curtype = cursortype
        self.lock = lock

    def __enter__(self):
        if (self.lock is not None):
            self.lock.acquire()
        self.cur = self.conn.cursor(self.curtype)
        return self.cur

    def __exit__(self, type, value, traceback):
        self.cur.close()
        self.conn.commit()
        if (self.lock is not None):
            self.lock.release()
        return

MySQLNormalCursor = functools.partial(MySQLCursor, cursortype=MySQLdb.cursors.Cursor)


def get_hms(seconds):
    negative = False
    if seconds < 0:
        negative = True
        seconds = abs(seconds)
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    if negative:
        return u"-%02d:%02d:%02d" % (h, m, s)
    else:
        return u"%02d:%02d:%02d" % (h, m, s)


def get_ms(seconds):
        m, s = divmod(seconds, 60)
        return u"%02d:%02d" % (m, s)


def unix_to_text(seconds):
    if (seconds > 0):
        difference = int(time.time()) - seconds
        year, month = divmod(difference, 31557600)
        month, week = divmod(month, 2629800)
        week, day = divmod(week, 604800)
        day, hour = divmod(day, 86400)
        hour, minute = divmod(hour, 3600)
        minute, second = divmod(minute, 60)
        result = []

        def plurify(num, unit):
            if num != 1:
                unit += 's'
            return u'%d %s' % (num, unit)

        if (year):
            result.append(plurify(year, u'year'))
        if (month):
            result.append(plurify(month, u'month'))
        if (week):
            result.append(plurify(week, u'week'))
        if (day):
            result.append(plurify(day, u'day'))
        if (hour):
            result.append(plurify(hour, u'hour'))
        if (minute):
            result.append(plurify(minute, u'minute'))
        if (second):
            result.append(plurify(second, u'second'))
        return " ".join(result)
    else:
        return u'Never before'
