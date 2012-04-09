import pylibshout
from time import sleep
from threading import Thread, Event
import os
import logging
import main
import select
from subprocess import Popen

class IcecastStream(Thread):
    attributes = {}
    def __init__(self, attributes, file_method):
        super(IcecastStream, self).__init__()
        
        # Setup event
        self.active = Event()
        
        # Setup transcoder
        self.file_method = file_method
        self.decoder = None
        self.transcoder = TranscoderTwo()
        self.stream_stdin = self.transcoder.stream_stdin
        self.stream_poll = select.poll()
        self.stream_poll.register(self.stream_stdin, select.POLLIN)
        # Setup libshout
        self._shout = pylibshout.Shout()
        self.attributes.update(attributes)
        for key, value in self.attributes.iteritems():
            if (key not in ["metadata"]):
                setattr(self._shout, key, value)
                
        self.daemon = True
        self.name = "Icecast Stream"
        
    def connected(self):
        try:
            return True if self._shout.connected() == -7 else False
        except AttributeError:
            return False
    
    def run(self):
        try:
            logging.debug("Opening connection to stream server")
            self._shout.open()
        except (pylibshout.ShoutException):
            logging.exception("Could not connect to stream server")
            self.on_disconnect()
            return
        metadata = (False, "No metadata available")
        while self.connected() and not self.active.is_set():
            # Set our metadata value
            metadata = (False, metadata[1])
            
            # Decoder logic
            if (not self.decoder or self.decoder.poll() is not None):
                # Decoder doesn't exist yet
                filename, metadata = self.file_method()
                if (filename == None or metadata == None):
                    logging.debug("File method returned None, disconnecting")
                    self.on_disconnect()
                    break
                logging.debug("Decoding file: %s, %s", filename, metadata)
                try:
                    self.decoder = self.transcoder.decode(filename)
                except OSError as err:
                    print err.__dict__
                    break
                metadata = (True, metadata)
                
            # Check metadata
            if (metadata[0]):
                metadata = (False, metadata[1])
                meta = metadata[1]
                if (type(meta) != str):
                    meta = meta.encode('utf-8', 'replace')
                try:
                    logging.debug("Sending metadata: {meta}"\
                                .format(meta=meta))
                    self._shout.metadata = {'song': meta}
                except (pylibshout.ShoutException) as err:
                    self.on_disconnect()
                    if err[0] == pylibshout.SHOUTERR_UNCONNECTED:
                        pass
                    else:
                        logging.exception("Failed sending stream metadata")
                    break
                self.attributes['metadata'] = meta
                
            disconnect = False
            # Buffer logic
            for fileno, event in self.stream_poll.poll(10):
                buff = os.read(fileno, 4096)
                if (len(buff) == 0):
                    logging.debug("Stream stdin empty, disconnecting")
                    disconnect = True
                    break
                try:
                    self._shout.send(buff)
                    self._shout.sync()
                except (pylibshout.ShoutException) as err:
                    if err[0] == pylibshout.SHOUTERR_UNCONNECTED:
                        pass
                    else:
                        logging.exception("Failed sending stream data")
                    disconnect = True
                    break
            if (disconnect):
                break

        self.on_disconnect()
        
    def close(self):
        self.on_disconnect()
        try:
            self.join(5)
        except RuntimeError:
            pass
        
    def on_disconnect(self):
        import datetime
        self.active.set()
        logging.debug("On disconnect called at %s", str(datetime.datetime.now()))
        try:
            self._shout.close()
        except (pylibshout.ShoutException) as err:
            if err[0] == pylibshout.SHOUTERR_UNCONNECTED:
                pass
            else:
                logging.exception("Failure in libshout close")
        self.transcoder.close()
        
class TranscoderTwo(object):
    encoder_args = ["lame", "--silent", "--flush",
                    "--cbr", "--resample", "44.1",
                    "-b", "192", "-", "-"]
    decoder_args = ["lame", "--silent", "--flush",
                    "--mp3input", "--decode", "FILE", "-"]
    processes = []
    pipes = []
    def __init__(self):
        super(TranscoderTwo, self).__init__()
        
        self.encode_stdin, self.decode_stdout = self.create_pipe()
        self.stream_stdin, self.encode_stdout = self.create_pipe()
        self.pipes.extend([self.encode_stdin,
                           self.decode_stdout,
                           self.stream_stdin,
                           self.encode_stdout])
        self.encoder = Popen(args=self.encoder_args,
                             stdin=self.encode_stdin,
                             stdout=self.encode_stdout)
        self.processes.append(self.encoder)
    def close(self):
        # Clean the pipes
        self.pipes[:] = [f for f in self.pipes if not f.closed]
        # Clean the processes
        self.processes[:] = [p for p in self.processes if not isinstance(p, int)]
        
        for pipe in self.pipes:
            try:
                pipe.close()
            except:
                logging.exception("Pipe closing error")
       
        
        for i, process in enumerate(self.processes):
            try:
                process.terminate()
            except (OSError, AttributeError):
                logging.exception("Termination failed")
            finally:
                switch = main.Switch(True, timeout=5)
                while switch:
                    result = process.poll()
                    if result:
                        self.processes[i] = result
                    sleep(0.5)
        
    def decode(self, filename, wait=False):
        if (hasattr(self, "decoder")):
            self.processes.remove(self.decoder)
        decoder_args = self.decoder_args[:]
        decoder_args[decoder_args.index("FILE")] = filename
        print decoder_args
        decoder = Popen(args=decoder_args,
                        stdout=self.decode_stdout)
        self.processes.append(decoder)
        self.decoder = decoder
        if wait:
            decoder.wait()
        return decoder
    
    def create_pipe(self):
        r, w = os.pipe()
        return os.fdopen(r, 'rb'), os.fdopen(w, 'wb')