#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm.util"

from contextlib import contextmanager, nested
from threading import Lock
from lastfm.util import Wormhole
from datetime import datetime
import sys

api = None
lock = Lock()

def set_api(api_):
    global api
    api = api_

@contextmanager
def logfile():
    if api._logfile is None:
        try:
            yield sys.stdout
        finally:
            pass
    else:
        try:
            log = None
            try:
                log = open(api._logfile, 'at')
                yield log
            except IOError:
                sys.stderr.write("could not open log file, logging to stdout\n")
                yield sys.stdout
        finally:
            if log is not None:
                log.close()

@Wormhole.exit('lfm-api-url')
def log_url(url, *args, **kwargs):
    if api._debug >= api.DEBUG_LEVELS['LOW']:
        with nested(logfile(), lock) as (log, l):
            log.write("{0}: URL fetched: {1}\n".format(datetime.now(), url))
        
@Wormhole.exit('lfm-obcache-register')
def log_object_registration((inst, already_registered), *args, **kwargs):
    if api._debug >= api.DEBUG_LEVELS['MEDIUM']:
        with nested(logfile(), lock) as (log, l):
            if already_registered:
                log.write("{0}: already registered: {1}\n".format(datetime.now(), repr(inst)))
            else:
                log.write("{0}: not already registered: {1}\n".format(datetime.now(), inst.__class__))

@Wormhole.exit('lfm-api-raw-data')
def log_raw_data(raw_data, *args, **kwargs):
    if api._debug >= api.DEBUG_LEVELS['HIGH']:
        with nested(logfile(), lock) as (log, l):
            log.write("{0}: RAW DATA\n {1}\n".format(datetime.now(), raw_data))
            
def log_silenced_exceptions(ex):
    if api._debug >= api.DEBUG_LEVELS['LOW']:
        with nested(logfile(), lock) as (log, l):
            log.write("{0}: Silenced Exception: {1}\n".format(datetime.now(), ex))