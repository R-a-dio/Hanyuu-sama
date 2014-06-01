from __future__ import absolute_import
import functools
import logging

from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer as JSONServer
import jsonrpclib

import config

jsonrpclib.config.use_jsonclass = False


def eat_exceptions(func):
    @functools.wraps(func)
    def wrap(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            logging.exception("API exception, none cares")
            return None

    return wrap
    

def clientify(method):
    name = method.__name__
    print "clientifying:", name

    @eat_exceptions
    @functools.wraps(method)
    def wrap(*args):
        server = jsonrpclib.Server(config.irc_url)

        print "calling:", name, args
        return getattr(server, name)(*args)

    wrap.server_side = method
    return wrap

@clientify
def request_announce(session, song):
    session.request_announce(song)

@clientify
def announce(session):
    session.announce()

def run_rpc_server(config, session):
    funcs = [request_announce, announce]

    server = JSONServer((config.host, config.port),
                        encoding="utf8", logRequests=False)

    for f in funcs:
        wrapped = functools.wraps(f.server_side)
        wrapped = wrapped(functools.partial(f.server_side, session))
        server.register_function(wrapped)

    server.serve_forever()
