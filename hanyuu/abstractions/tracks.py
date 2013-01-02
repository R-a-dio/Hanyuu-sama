from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from . import logger


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
