from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import time


def instance_decorator(cls):
    """
    Decorator for a class that returns an instance of the class.
    
    This is used to create a singleton of a class that lives forever
    in the process.
    """
    return cls()

class Switch(object):
    """
    A timed switch. Evaluates truthy if the time has expired, else falsy.
    """
    def __init__(self, initial, timeout=15):
        object.__init__(self)
        self.state = initial
        self.timeout = time.time() + timeout
    def __nonzero__(self):
        return False if self.timeout <= time.time() else self.state
    def __bool__(self):
        return False if self.timeout <= time.time() else self.state
    def reset(self, timeout=15):
        self.timeout = time.time() + timeout