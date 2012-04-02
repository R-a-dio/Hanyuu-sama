import pylibshout
from time import sleep
from threading import Thread
import os
from traceback import format_exc
import logging

class UnsupportedFormat(Exception):
    pass

import lame
from Queue import Queue, Empty

class Chain(object):
    def __init__(self):
        object.__init__(self)
        
        self.queue = Queue(1)
        
        self.decoder = self.create_decoder()
        self.encoder = self.create_encoder()
        self.encoder_in, self.decoder_out = self.create_pipe()
        self.data_in, self.encoder_out = self.create_pipe()
        
        self.thread = Thread(name="Chain Processor",
                             target=self.processor)
        self.thread.daemon = 1
        self.thread.start()
    def terminate(self):
        self.decoder.terminate()
        self.encoder.terminate()
    def read(self, size=2048):
        return self.data_in.read(size)
    def processor(self):
        self.encoder(self.encoder_in, self.encoder_out)
        while True:
            self.decoder.wait()
            try:
                self.current = self.queue.get_nowait()
            except (Empty):
                sleep(0.1)
            else:
                self.decoder(self.current[0], self.decoder_out)
        self.encoder_in.close()
    def add_file(self, filename, metadata):
        self.queue.put((filename, metadata))

    def create_pipe(self):
        r, w = os.pipe()
        return os.fdopen(r, 'rb'), os.fdopen(w, 'wb')
    def create_decoder(self):
        decoder = lame.Lame()
        decoder.config.input = lame.input.MP3
        decoder.config.mode = lame.modes.Decode
        return decoder
    def create_encoder(self):
        encoder = lame.Lame()
        encoder.config.mode = lame.modes.CBR
        return encoder



class instance(Thread):
    """Wrapper around shout.Shout

    Requires at least host, port, password and mount to be specified
    in the 'attributes' which should be a dictionary which can contain:

       host - name or address of destination server
       port - port of destination server
       user - source user name (optional)
   password - source password
      mount - mount point on server (relative URL, eg "/stream.ogg")
   protocol - server protocol: "http" (the default) for icecast 2,
              "xaudiocast" for icecast 1, or "icy" for shoutcast
nonblocking - use nonblocking send
     format - audio format: "ogg" (the default) or "mp3"
       name - stream name
        url - stream web page
      genre - stream genre
description - longer stream description
 audio_info - dictionary of stream audio parameters, for YP information.
              Useful keys include "bitrate" (in kbps), "samplerate"
              (in Hz), "channels" and "quality" (Ogg encoding
              quality). All dictionary values should be strings. The known
              keys are defined as the SHOUT_AI_* constants, but any other
              will be passed along to the server as well.
   dumpfile - file name to record stream to on server (not supported on
              all servers)
      agent - for customizing the HTTP user-agent header"""
    attributes = {"protocol": "http", "format": "ogg"}
    def __init__(self, attributes):
        Thread.__init__(self)
        self.queue = Queue()
        self._start_handler = False
        self._closing = False
        self._handlers = {}
        self._shout = pylibshout.Shout()
        self.daemon = 1
        self.name = "Streamer Instance"
        self.attributes.update(attributes)
        for key, value in self.attributes.iteritems():
            if (key not in ["metadata"]):
                setattr(self._shout, key, value)
        self.transcoder = Chain()
        self.add_handle("disconnect", self.on_disconnect, -20)
    def add_file(self, filename, metadata=None):
        self.queue.put((filename, metadata))

    def run(self):
        """Internal method"""
        try:
            logging.debug("Opening connection to stream server")
            self._shout.open()
        except (pylibshout.ShoutException):
            logging.exception("Could not connect to stream server")
            self._call("disconnect")
            return
        while (True):
            # Handle our metadata
            if (self.transcoder.queue.empty()):
                try:
                    filename, metadata = self.queue.get_nowait()
                except (Empty):
                    sleep(0.1)
                else:
                    self.transcoder.queue.put((filename, metadata))
                    if (type(metadata) != str):
                        metadata = metadata.encode('utf-8', 'replace')
                    try:
                        logging.debug("Sending metadata: {meta}"\
                                    .format(meta=metadata))
                        self._shout.metadata = {'song': metadata}
                    except (pylibshout.ShoutException):
                        self._call('disconnect')
                        logging.exception("Failed sending stream metadata")
                        break
                    self.attributes['metadata'] = metadata
            buffer = self.transcoder.read(4096)
            if (len(buffer) == 0):
                self._call("disconnect")
                logging.debug("Stream buffer empty, breaking loop")
                break
            try:
                self._shout.send(buffer)
                self._shout.sync()
            except (pylibshout.ShoutException):
                self._call("disconnect")
                logging.exception("Failed sending stream data")
                break
    def close(self):
        self._closing = True
        self.on_disconnect(self)
        self.join()
    def on_disconnect(self, instance):
        self.transcoder.terminate()
        try:
            self._shout.close()
        except (pylibshout.ShoutException):
            pass
    def add_handle(self, event, handle, priority=0):
        """Adds a handler for 'event' to a method 'handle'
        
        Event can be:
        
            'disconnect'- Server or Client disconnected
        Handle can be:
            Any method that accepts one parameter, the
            streamer.instance object.
        """
        if (self._handlers.get(event)):
            self._handlers[event].append((priority, handle))
        else:
            self._handlers.update({event: [(priority, handle)]})
        self._handlers[event].sort(reverse=True)
    def del_handle(self, event, handle, priority=0):
        """Deletes a handler for 'event' linked to method 'handle'
        
        See 'add_handle' for 'event' list
        """
        if (self._handlers.get(event)):
            try:
                self._handlers[event].remove((priority, handle))
            except ValueError:
                pass
    def _call(self, target):
        """Internal method"""
        logging.debug("instance Calling handler: {target}".format(target=target))
        logging.debug(self._handlers)
        try:
            handles = self._handlers[target]
            for h in handles:
                try:
                    if (h[1](self) == 'UNHANDLE'):
                        del handles[h]
                except:
                    logging.warning(format_exc())
        except (KeyError):
            logging.debug("instance No handler: {target}".format(target=target))
        except:
            logging.exception("instance")