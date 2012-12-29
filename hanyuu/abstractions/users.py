"""
A module used for the abstractions of the users part of the database.
"""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from ..db import models
from .. import utils, config
import logging


logger = logging.getLogger('hanyuu.abstractions.user')


@utils.instance_decorator
class DJ(object):
    """
    Encapsulates the concept of a DJ in our system.
    
    This abstracts the database from the rest of the code. But does return a
    database related object since it's a simple one.
    """
    def __init__(self, id=None, name=None):
        """
        Returns a read-only DJ object.
        
        Raises DoesNotExist if no match was found or ValueError if no arguments
        where supplied.
        """
        if id is None and name is None:
            raise ValueError("Neither `name` nor `id` is supplied.")
        elif id is None:
            self.model = models.DJ.get(models.DJ.name == name)
        elif name is None:
            self.model = models.DJ.get(models.DJ.id == id)
        else:
            self.model = models.DJ.get(models.DJ.id == id, models.DJ.name == name)
        
    def __getattr__(self, key):
        """
        This method is chosen to add abstraction, if we change the database
        layout or other things we can easily adopt it into the older structure
        by adding properties.
        """
        return getattr(self.model, key)
    
    @classmethod
    def resolve_name(cls, name):
        """
        Resolves a DJ username to a DJ identifier.
        
        Returns an integer that is the DJ identifier or 0 if the DJ username
        does not exist.
        """
        return cls(name=name)
        
    @classmethod
    def resolve_id(cls, id):
        """
        Resolves a DJ identifier to a DJ username.
        
        Returns a class instance or raises DoesNotExist
        """
        return cls(id=id)
    