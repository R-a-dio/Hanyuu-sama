from __future__ import absolute_import
import argparse
import json

from . import irc, api


def jsonfile(filename):
    with open(filename, 'r') as f:
        return json.load(f)


parser = argparse.ArgumentParser(description="Start the R/a/dio IRC bot.")
parser.add_argument('--config', '-c', default={}, help="location of configuration file", type=jsonfile)

def main():
    # TODO: replace with normal config
    import urlparse, collections, config
    url = urlparse.urlparse(config.irc_url)

    conf = collections.namedtuple("Config", ("host", "port"))
    conf.host = url.hostname
    conf.port = url.port

    # END TODO
    args = parser.parse_args()

    session = irc.run_irc_client(args.config)
    api.run_rpc_server(conf, session)


if __name__ == "__main__":
    main()
