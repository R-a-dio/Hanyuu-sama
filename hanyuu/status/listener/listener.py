from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import

from .. import logger
from .. import config
logger = logger.getChild(__name__)

import requests
import re


def shoutcast_protocol_iterator(fileobj, metaint, handle_meta=None):
    """
    Reads chunks from a file object and yields the audio data.
    
    Calls the :obj:`handle_meta` function when metadata is found in the stream.
    """
    DATA, METALEN, META = 0, 1, 2
    
    status = DATA
    metadata_length = 0
    while True:
        if status == DATA:
            status = METALEN
            
            data = fileobj.read(metaint)
            yield data
        elif status == METALEN:
            status = META
            
            data = fileobj.read(1)
            metadata_length = ord(data) * 16
        elif status == META:
            status = DATA
            
            data = fileobj.read(metadata_length)
            
            if not data:
                continue
            
            if not handle_meta:
                continue

            meta = parse_shoutcast_metadata(data)
            try:
                handle_meta(meta)
            except:
                logger.warning("Exception in listener meta data handler.",
                               exc_info=True)
        if not data:
            break
    
def open(url, handler=None):
    response = requests.get(url, stream=True, headers={'Icy-MetaData': 1})

    metaint = int(response.headers['icy-metaint'])
    return shoutcast_protocol_iterator(response.raw, metaint, handler)

shoutcast_metadata_regex = re.compile(r"(?P<tag>[^;' ]+)='(?P<value>.*?)';")
shoutcast_metadata_key_map = {
                              "streamtitle": "metadata",
                              "streamurl": "url",
                              }
def parse_shoutcast_metadata(string):
    """
    A parser to handle the metadata block send by icecast/shoutcast servers.
    
    Since the server does not escape any characters, we can get malformed
    metadata blocks. We handle this carefully.
    
    :param bytes string: The raw metadata block send by the server.
    :returns dict: A mapping of tag:value items.
    
    .. note::
        We use a simple key mapper to make the metadata a bit more generalized.
        This will return the original key if we don't map it, and otherwise will
        return whatever is in the :obj:`shoutcast_metadata_key_map`.
    """
    items = shoutcast_metadata_regex.findall(string)

    # We lower the key because there is no standard to what the server
    # is required to return.
    return {shoutcast_metadata_key_map.get(key.lower(), key.lower()): value for
            key, value in items}
    
    # Ugly one liner above, it's equal to the following code for reference:
    result = {}
    for key, value in items:
        # Lower the key for mapping and user (no need to remember case)
        key = key.lower()
        # Map the key to either a friendlier one or return the original key.
        key = shoutcast_metadata_key_map.get(key, key)
        # Add it to our result.
        result[key] = value