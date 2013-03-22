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
    
    Example usage:
        >>> import time
        >>> a = Switch(5)
        >>> bool(a)
        False
        >>> time.sleep(5)
        >>> bool(a)
        True
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
        
def fix_encoding(metadata):
    """
    This function tries to guess the correct encoding of :obj:`metadata`
    
    Currently this checks for the following encodings in order:
        UTF-8, strict mode
        SJIS, replace mode
        UTF-8, replace mode
        
    .. note::
        This function also calls an unconditional `metadata.strip()` before
        returning the new string.
        
    :param bytes metadata: A sequence in an unknown encoding.
    :returns unicode: An unicode string.
    """
    # If we get an unicode string we assume it's all nice and clean and just
    # return it. The method below for fixing encoding does NOT work when it gets
    # an unicode object.
    if isinstance(metadata, unicode):
        return metadata

    try:
        return metadata.decode('utf-8', 'strict').strip()
    except (UnicodeDecodeError):
        return metadata.decode('shiftjis', 'replace').strip()