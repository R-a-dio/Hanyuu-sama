from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_imports
from .. import db


class DJ(object):
    """
    Encapsulates the concept of a DJ in our system.
    
    This abstracts the database from the rest of the code.
    """
    def __init__(self, id=None, name=None):
        super(DJ, self).__init__()
        if id is None and name is None:
            raise ValueError("Neither `name` nor `id` is supplied.")
        elif id is None:
            self.name = name
            self.id = self.resolve_name_to_id(name)
        elif name is None:
            self.id = id
            self.name = self.resolve_id_to_name(id)
            
    @classmethod
    def resolve_name_to_id(cls, name):
        """
        Resolves a DJ username to a DJ identifier.
        
        Returns an integer that is the DJ identifier or 0 if the DJ username
        does not exist.
        """
        with db.create_cursor() as cursor:
            cursor.execute(
               "SELECT `djid` FROM `users` WHERE `user`=%s LIMIT 1;",
               (name,)
               )
            for djid, in cursor:
                return djid
            return 0
        
    @classmethod
    def resolve_id_to_name(cls, id):
        """
        Resolves a DJ identifier to a DJ username.
        
        Returns an unicode string containing the DJ username or 'Unknown' if
        no DJ exists with this identifier.
        """
        with db.create_cursor() as cursor:
            cursor.execute(
               "SELECT `user` FROM `users` WHERE `djid`=%s LIMIT 1;",
               (id,)
               )
            for user, in cursor:
                return user
            return 'Unknown'
        
    @classmethod
    def resolve_wildcard_to_name(cls, wildcard):
        """
        Resolves a string to a DJ username.
        
        This is the best method to get a valid DJ name when you get 
        user input.
        
        >>> DJ.resolve_wildcard_to_name('Eggmun-twat')
        'eggmun'
        
        Returns a :class:DJ instance or None.
        """
        for dj, wildcards in config.items('dj_wildcards'):
            if re.search(regex, dj):
                return cls(name=dj)
        return None