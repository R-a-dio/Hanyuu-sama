import logging
import threading
import audio
import util
import manager
import bootstrap


logger = logging.getLogger('afkstreamer')


class Streamer(object):

    """
    Top wrapper of the AFK Streamer. This gives out filenames and metadata
    to the underlying :mod:`audio` module.
    """

    def __init__(self, attributes):
        super(Streamer, self).__init__()
        self.instance = None
        self.icecast_config = attributes

        self.instance = audio.Manager(self.icecast_config, self.supply_song)
        self.close_at_end = threading.Event()

    @property
    def connected(self):
        """
        Returns True if the audio modules :mod:`audio.icecast` is
        currently connected. Else returns False.
        """
        try:
            return self.instance.connected()
        except (AttributeError):
            return False

    def start(self):
        """Starts the audio pipeline and connects to icecast."""
        self.queue = manager.Queue()
        self.close_at_end.clear()
        self.instance.start()

    def close(self, force=False):
        """Stop the audio pipeline and disconnects from icecast."""
        if force:
            self.instance.close()
            logger.info("Closed audio manager.")
        else:
            self.close_at_end.set()
            logger.info("Set close at end of song flag.")

    def supply_song(self):
        """Returns a tuple of (filename, metadata) to be played next."""
        # check if we got asked to shut down at end of track.
        if (self.close_at_end.is_set()):
            self.shutdown(force=True)
        else:
            try:
                song = self.queue.pop()
            except manager.QueueError:
                self.queue.clear_pops()
                return self.supply_song()
            else:
                if (song.id == 0):
                    self.queue.clear()
                    song = self.queue.pop()
                self.queue.clear_pops()
                # update now playing
                manager.NP.change(song)

                return (song.filename, song.metadata)
        return (None, None)

    def connect(self, *args, **kwargs):
        """
        .. deprecated:: 1.2
           use :meth:`start`: instead.
        """
        self.start(*args, **kwargs)

    def shutdown(self, *args, **kwargs):
        """
        .. deprecated:: 1.2
           use :meth:`close`: instead.
        """
        self.close(*args, **kwargs)


class StreamManager(util.BaseManager):
    socket = '/tmp/hanyuu_stream'

StreamManager.register("Streamer", Streamer)
