from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from . import logger
from ..db import models
from .. import config
import os
import functools


logger = logger.getChild('tracks')


class Track(object):
    """
    An instance of a known track in our database. This can also be used for
    adding new tracks.
    
    A 'known' track is one we have seen before. This means there is no
    difference between tracks we have an audio file of and ones we only know
    metadata of. The object easily allows you to check if it has a corresponding
    audio file available or not.
    
    """
    # This is a dictionary of {'keyword': 'type'} items in it.
    # 'type' is the type 'keyword' should have when passed,
    # set 'type' to None to not do any checking at all.
    # the value of 'type' is passed to :func:`isinstance` without change and
    # can thus be a sequence of types.
    _accepted_keywords = {
                          'length': (int, long, float),
                          'last_played': datetime.datetime,
                          'last_requested': datetime.datetime,
                          'filename': unicode,
                          'change': bool,
                          }
    def __init__(self, meta, **kwargs):
        """
        The constructor accepts only a metadata string and extra values to set
        on the new Track object. 
        
        The extra keyword arguments won't be used if the track already exists 
        unless 'change=:const:`True`' is given as one of the keyword arguments.
        
        .. note::
            For constructing from a database primary key see the :meth:`from_id`
            class method below.
        
        Required parameters:
            :param meta: An unicode string of metadata.
        
        Extra keyword arguments are:
            :param integer length: Defines the length of the track.
            :param last_played: :class:`datetime.datetime` object of when this was last played.
            :param last_requested: Same as `last_played` but then for last requested.
            :param unicode filename: A filename that points to an audio file for this Track.
            :param bool change: Flag if you want to force update the storage with your extra arguments.
        """
        super(Track, self).__init__()

        # Try loading from the database first.
        if self._load_from_database(meta):
            # If we have a force change flag we shouldn't return right away.
            # Since we need to handle all the extra values done below.
            if not kwargs.get('change'):
                return

        # Handle our extra values.
        for key, value in kwargs.iteritems():
            keytype = self._accepted_keywords.get(key)
            if keytype and isinstance(value, keytype):
                setattr(key, value)
            else:
                # Argument is of the wrong type.
                if keytype:
                    raise TypeError(("Argument '{key:s}' is not of the correct "
                                    "type. Expected '{expected!s}' got "
                                    "'{type!s}' instead.").format(
                                                              key=key,
                                                              expected=keytype,
                                                              type=type(value)
                                                              )
                                     )
                # Argument doesn't exist
                # this should NOT be raised if it's a deprecated argument.
                else:
                    raise AttributeError(("Unknown argument '{key:s}' passed "
                                         "to Track.").format(key=key))

    def _load_from_database(self, metadata):
        """
        Internal method to load a track from the database.
        
        This checks if there is a matching record in the database.
        
        :param unicode metadata: A string of metadata.
        :returns: Boolean indicating if there was a matching record or not.
        :rtype: bool
        """
        try:
            self._song = models.Song.from_meta(metadata,
                                               plays=True, faves=True)
        except models.Song.DoesNotExist:
            return False

        try:
            self._track = models.Track.from_meta(metadata)
        except models.Track.DoesNotExist:
            self._track = None

        return True

    @property
    def length(self):
        """
        :returns: :class:`Length` object that is the length of the song.
        
        .. note::
            The song length is only 100% accurate if the song has an audio
            file available. Otherwise it's an approximation from when it was
            last played.
        """
        return Length(self._song.length)

    @length.setter
    def length(self, value):
        """
        Sets the length of the song.
        
        :params integer value: The new length to set.
        
        .. note::
            :class:`Length` is a subclass of :const:`int` and can also be
            used as value.
        """
        self._song.length = value

    @property
    def last_played(self):
        return self._song.last_played

    @property
    @requires_track
    def last_requested(self):
        """
        :returns: The time of when this Song was last requested.
        :rtype: :class:`datetime.datetime`
        :raises: :class:`NoTrackEntry` if the song has no audio file.
        """
        return self._track.last_requested

    @last_requested.setter
    @requires_track
    def last_requested(self, value):
        """
        Sets the new last requested time.
        
        :type value: :class:`datetime.datetime`
        :raises: :class:`NoTrackEntry` if the song has no audio file.
        :raises: :class:`TypeError` if the argument is not a :class:`datetime.datetime` object.
        """
        if not isinstance(value, datetime.datetime):
            raise TypeError("Expected `datetime.datetime` object, got "
                            "'{0!r}' object.".format(type(value)))
        self._track.last_requested = value

    @property
    @requires_track
    def filename(self):
        """
        :returns unicode: The filename of the audio file.
        :raises: :class:`NoTrackEntry` if the song has no audio file.
        
        .. note::
            This is relative to the configured media.directory configuration.
        """
        return self._track.path

    @filename.setter
    @requires_track
    def filename(self, value):
        """
        :params unicode value: A new filename to set.
        :raises: :class:`NoTrackEntry` if the song has no audio file.
        """
        self._track.path = value

    @requires_track
    def open(self, mode='rb'):
        """
        Opens the associated file and returns a file object.
        
        This handles the path finding for you.
        
        :params unicode mode: The mode to be passed to the :func:`open` call.
        :returns: An open file object.
        :raises: :class:`NoTrackEntry` if the song has no audio file.
        """
        return open(os.path.join(config.get('media', 'path'), self.filename),
                    mode)


def requires_track(func):
    """
    Decorator that raises :class:`NoTrackEntry` if the song instance has no
    associated audio file in the database.
    
    Currently this only checks if `self._track` is falsy.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self._track:
            raise NoTrackEntry()
        return func(self, *args, **kwargs)
    return wrapper


class NoTrackEntry(Exception):
    """
    Raised when a :class:`Song` instance accesses Track only attributes
    without having an audio file attached to it.
    """
    pass


class Length(int):
    """
    A simple subclass of :const:`int` to support formatting on it without
    having to know the exact format or value in the rest of the code.
    """
    def format(self):
        """
        :returns unicode: A formatted hh:mm:nn string of the integer.
        """
        if self <= 3600:
            # the divmod is equal to 'minutes, seconds = divmod(self, 60)'
            return '{0:02d}:{0:02d}'.format(*divmod(self, 60))
        else:
            hours, minutes = divmod(self, 3600)
            minutes, seconds = divmod(minutes, 60)
            return '{0:02d}:{0:02d}:{0:02d}'.format(hours, minutes, seconds)
