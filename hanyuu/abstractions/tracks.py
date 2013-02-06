from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from . import logger
from ..db import models
from .. import config
import os
import functools
import datetime


logger = logger.getChild('tracks')


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
            :param last_requested: Same as `last_played` but then for last requested.
            :param unicode filename: A filename that points to an audio file for this Track.
            :param bool change: Flag if you want to force update the storage with your extra arguments.
        """
        super(Track, self).__init__()

        self._plays = None
        self._requests = None


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

    @classmethod
    def from_track_id(cls, id):
        """
        Returns an instance based on the `tracks` table ID.
        
        .. warning::
            Don't use this method in production code.
        """
        result = models.Track.get(models.Track.id == id)

        return cls(create_metadata_string(result))

    @classmethod
    def from_esong_id(cls, id):
        """
        Returns an instance based on the `esong` table ID.
        
        .. warning::
            Don't use this method in production code.
        """
        result = models.Song.get(models.Song.id == id)

        return cls(result.meta)

    def _load_from_database(self, metadata):
        """
        Internal method to load a track from the database.
        
        This checks if there is a matching record in the database.
        
        :param unicode metadata: A string of metadata.
        :returns: Boolean indicating if there was a matching record or not.
        :rtype: bool
        """
        import peewee
        song_query = models.Song.query_from_meta(metadata)
        song_query.join(models.Play, peewee.JOIN_LEFT_OUTER).annotate(
                            models.Song,
                            peewee.fn.Max(models.Play.time).alias('last_played')
                            )
        try:
            self._song = song_query.get()
        except models.Song.DoesNotExist:
            self._song = models.Song()
            result = False
        else:
            result = True

        try:
            self._track = models.Track.from_meta(metadata)
        except models.Track.DoesNotExist:
            self._track = None

        return result
    
    @property
    def song_id(self):
        """
        :returns: The id field of the underlying :class:`hanyuu.models.Song`
                  instance
        :rtype:   int
        """
        return self._song.id
    
    @property
    def track_id(self):
        """
        :returns: The id field of the underlying :class:`hanyuu.models.Track`
                  instance, or None if there is no underlying Track instance
        :rtype:   int
        """
        if self._track:
            return self._track.id
    
    @property
    def metadata(self):
        """
        :returns: A metadata string of '[artist -] title' where artist is optional
        :rtype: unicode
        
        .. note::
            This uses the `tracks` table if available before trying the other
            table.
        """
        if self._track:
            artist = self._track.artist
            title = self._track.title
            if artist:
                metadata = "{0:s} - {1:s}".format(artist, title)
            else:
                metadata = title
            return metadata
        return self._song.meta or ''

    @metadata.setter
    def metadata(self, value):
        """
        Sets the metadata of the song.
        
        :params unicode value: A metadata string in form '[artist -] title'
        
        .. note::
            The setter only changes the value on the `esong` table. If you
            want to change both values you should set to :attr:`artist` and
            :attr:`title` instead.
        """
        self._song.meta = value

    @property
    @requires_track
    def artist(self):
        """
        :returns: The artist of this song.
        :rtype: unicode
        """
        return self._track.artist

    @artist.setter
    @requires_track
    def artist(self, value):
        """
        Sets the new artist of this song
        
        :params unicode value: The artist
        """
        # TODO: This doesn't change the `esong` table.
        self._track.artist = value

    @property
    @requires_track
    def title(self):
        """
        :returns: The title of this song.
        :rtype: unicode
        """
        return self._track.title

    @title.setter
    @requires_track
    def title(self, value):
        """
        Sets the new title of this song.
        
        :params unicode value: The new title.
        """
        # TODO: This doesn't change the `esong` table.
        self._track.title = value

    @property
    def length(self):
        """
        :returns: Length of the song or 0 if none available.
        :rtype: :class:`Length`
        
        .. note::
            The song length is only 100% accurate if the song has an audio
            file available. Otherwise it's an approximation from when it was
            last played.
        """
        length = self._song.length
        if length:
            return Length(length)
        return Length(0)

    @length.setter
    def length(self, value):
        """
        Sets the length of the song.
        
        :params integer value: The new length to set.
        
        .. note::
            :class:`Length` is a subclass of :const:`int` and can also be
            used as value.
        """
        self._song.length = int(value)

    @property
    def plays(self):
        """
        :returns: A mutable object with all the playing data in it.
        :rtype: :class:`Plays`
        """
        if self._plays is None:
            self._plays = Plays(self, (play.time for play in self._song.plays))
        return self._plays

    @property
    @requires_track
    def requests(self):
        """
        :returns: A mutable objects with all request data in it.
        :rtype: :class:`Requests`
        :raises: :class:`NoTrackEntry` if the song has no audio file.
        """
        if self._requests is None:
            self._requests = Requests([self._track.last_requested])
        return self._requests

    @property
    @requires_track
    def filename(self):
        """
        :returns unicode: The filename of the audio file.
        :raises: :class:`NoTrackEntry` if the song has no audio file.
        
        .. note::
            This is relative to the configured `media.directory` configuration.
        """
        return self._track.filename

    @filename.setter
    @requires_track
    def filename(self, value):
        """
        :params unicode value: A new filename to set.
        :raises: :class:`NoTrackEntry` if the song has no audio file.
        """
        self._track.filename = value

    @property
    @requires_track
    def filepath(self):
        """
        :returns unicode: The full path to the audio file.
        :raises: :class:`NoTrackEntry` if the song has no audio file.
        """
        return os.path.join(config.get('media', 'directory'), self.filename)

    @requires_track
    def open(self, mode='rb'):
        """
        Opens the associated file and returns a file object.
        
        This handles the path finding for you.
        
        :params unicode mode: The mode to be passed to the :func:`open` call.
        :returns: An open file object.
        :raises: :class:`NoTrackEntry` if the song has no audio file.
        """
        return open(self.filepath, mode)

    def save(self):
        """
        Saves all the changes done so far on this object into the database.
        
        .. note::
            This method can do multiple queries to the database depending on
            the changes done on the object.
        """
        if self._track:
            self._track.save()
        if self._song:
            self._song.save()


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
        :returns unicode: A formatted [hh:]mm:nn string of the integer.
        """
        if self <= 3600:
            # the divmod is equal to 'minutes, seconds = divmod(self, 60)'
            return '{0:02d}:{1:02d}'.format(*divmod(self, 60))
        else:
            hours, minutes = divmod(self, 3600)
            minutes, seconds = divmod(minutes, 60)
            return '{0:02d}:{1:02d}:{2:02d}'.format(hours, minutes, seconds)


class Plays(list):
    """
    A simple subclass of :const:`list` to support some extra attributes.
    
    This class is returned when you access :attr:`Track.plays` and is a
    collection of play times of the :class:`Track` in question.
    
    The collection contains :class:`datetime.datetime` objects or objects that
    act the same as such with extra methods (for future additions).
    """
    def __init__(self, song, sequence):
        super(Plays, self).__init__(sequence)

        self.new_values = list()
        self.deleted_values = list()

        self.song = song

    @property
    def last(self):
        """
        :returns: The time that last occured.
        :rtype: :class:`datetime.datetime` object.
        """
        return max(self)

    def add(self, time, dj=None):
        """
        Adds a played entry to the :class:`Track` object.
        
        The exact time it was played at.
        :params time: A :class:`datetime.datetime` instance.
        
        The DJ that played this track at the time.
        :params dj: A :class:`hanyuu.abstractions.users.DJ` instance.
        
        :returns None:
        
        .. note::
            It's good practice to add the DJ argument to all the code already.
            
            The current database however ignores this argument.
        """
        self.new_values.append(time)
        self.append(time)

    def remove(self, time, dj=None):
        """
        Removes a played entry from the :class:`Track` object.
        
        The time this was played at.
        :params time: A :class:`datetime.datetime` instance.
        
        The DJ that played this track at the time.
        If this is :const:`None` it will be ignored otherwise it will be used
        for exact matching.
        :params dj: A :class:`hanyuu.abstractions.users.DJ` instance.
        
        :returns None:
        
        .. note::
            Currently the `dj` argument is completely ignored.
        """
        self.deleted_values.append(time)
        self.remove(time)

    def save(self):
        """
        Saves changes to the database.
        """

class Requests(list):
    """
    A simple subclass of :const:`list` to support some extra attributes.
    """
    @property
    def last(self):
        """
        :returns: The time that last occured.
        :rtype: :class:`datetime.datetime` object.
        """
        return max(self)


def create_metadata_string(track):
    """
    Creates a '[artist -] title' string of the :class:`hanyuu.db.models.Track`
    instance.
    """
    artist = track.artist
    title = track.title
    if artist:
        metadata = "{0:s} - {1:s}".format(artist, title)
    else:
        metadata = title
    return metadata
