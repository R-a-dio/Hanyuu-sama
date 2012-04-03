import pylibshout
from time import sleep
from threading import Thread
import os
import logging

class UnsupportedFormat(Exception):
    pass

import lame
from Queue import Queue, Empty

class Transcoder(object):
    def __init__(self, file_method):
        """Accepts a file_method that is called whenever the previous
        file finished decoding, should return a full filepath"""
        object.__init__(self, file_method)
        
        self.file_method = file_method
        
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
                self.current = self.file_method()
            except (Empty):
                sleep(0.1)
            else:
                self.decoder(self.current, self.decoder_out)
        self.encoder_in.close()
        
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
    def __init__(self, attributes, queue=None, file_method=None):
        Thread.__init__(self)
        self.queue = queue or Queue()
        self.file_method = file_method or (lambda: self.queue.pop())
        self.transcoder = Transcoder(self.transcoder_file)
        self._shout = pylibshout.Shout()
        self.attributes.update(attributes)
        for key, value in self.attributes.iteritems():
            if (key not in ["metadata"]):
                setattr(self._shout, key, value)
        self.metadata = (True, "Currently have no metadata available")
        self.daemon = 1
        self.name = "Streamer Instance"
    
    def connected(self):
        return True if self._shout.connected() == -7 else False
    
    def transcoder_file(self):
        filename, metadata = self.file_method()
        self.metadata = [True, metadata]
        return filename
    
    def run(self):
        """Internal method"""
        try:
            logging.debug("Opening connection to stream server")
            self._shout.open()
        except (pylibshout.ShoutException):
            logging.exception("Could not connect to stream server")
            self.on_disconnect()
            return
        while (True):
            # Handle our metadata
            if (self.metadata[0]):
                self.metadata[0] = False
                metadata = self.metadata[1]
                if (type(metadata) != str):
                    metadata = metadata.encode('utf-8', 'replace')
                try:
                    logging.debug("Sending metadata: {meta}"\
                                .format(meta=metadata))
                    self._shout.metadata = {'song': metadata}
                except (pylibshout.ShoutException):
                    self.on_disconnect()
                    logging.exception("Failed sending stream metadata")
                    break
                self.attributes['metadata'] = metadata
            buff = self.transcoder.read(4096)
            if (len(buff) == 0):
                self.on_disconnect()
                logging.debug("Stream buffer empty, breaking loop")
                break
            try:
                self._shout.send(buff)
                self._shout.sync()
            except (pylibshout.ShoutException):
                self.on_disconnect()
                logging.exception("Failed sending stream data")
                break
    def close(self):
        self.on_disconnect()
        self.join()
    def on_disconnect(self):
        try:
            self._shout.close()
        except (pylibshout.ShoutException):
            pass
        self.transcoder.terminate()