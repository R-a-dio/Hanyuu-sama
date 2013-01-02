from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import


def instance_decorator(cls):
    """
    Decorator for a class that returns an instance of the class.
    
    This is used to create a singleton of a class that lives forever
    in the process.
    """
    return cls()
