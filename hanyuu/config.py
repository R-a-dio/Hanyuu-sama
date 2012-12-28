from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import ConfigParser
import functools


def reload_configuration():
    """
    Creates a new :class:`ConfigParser.SafeConfigParser` and passes it the
    same filenames as given in the last call to :func:`load_configuration`.
    
    This effectively 'reloads' the configuration files.
    """
    global configuration
    configuration = ConfigParser.SafeConfigParser()
    configuration.read(configuration_files)
    
def load_configuration(filepaths):
    """
    Creates a new :class:`ConfigParser.SafeConfigParser` and tries parsing
    all :obj:`filepaths` given.
    
    :obj:`filepaths` should be a list of filenames.
    
    Returns nothing, instead assigns itself to the global variable 
    `configuration` and abstracts itself by calling :func:`create_abstractions`
    """
    global configuration, configuration_files
    configuration = ConfigParser.SafeConfigParser()
    configuration.read(filepaths)
    configuration_files = filepaths

def get(*args, **kwargs):
    """See :class:`ConfigParser.RawConfigParser`"""
    return configuration.get(*args, **kwargs)
    
def getint(*args, **kwargs):
    """See :class:`ConfigParser.RawConfigParser`"""
    return configuration.getint(*args, **kwargs)

def getfloat(*args, **kwargs):
    """See :class:`ConfigParser.RawConfigParser`"""
    return configuration.getfloat(*args, **kwargs)

def options(*args, **kwargs):
    """See :class:`ConfigParser.RawConfigParser`"""
    return configuration.options(*args, **kwargs)

def has_option(*args, **kwargs):
    """See :class:`ConfigParser.RawConfigParser`"""
    return configuration.options(*args, **kwargs)

def sections(*args, **kwargs):
    """See :class:`ConfigParser.RawConfigParser`"""
    return configuration.sections(*args, **kwargs)

def has_section(*args, **kwargs):
    """See :class:`ConfigParser.RawConfigParser`"""
    return configuration.has_section(*args, **kwargs)

def items(*args, **kwargs):
    """See :class:`ConfigParser.RawConfigParser`"""
    return configuration.items(*args, **kwargs)
