from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from .. import logger
logger = logger.getChild('audio')

import threading
import logging
import audiotools
from . import garbage
from . import encoder
from . import files
from . import icecast


class Manager(object):
    """
    A class that manages the audio pipeline. Each component gets a reference
    to the processor before it.
    
    .. note::
        This is a very cruel pipeline and has specifics to our needs and is in
        no way a generic implementation. 
        
        Nor does it have proper definitions of what should go out or into
        a processor.
        
        
    --------------
    All processors
    --------------
    
    The :class:`Manager` expects that all registered processors have at least
    the following characteristics:
    
        :func:`start`: Called when :meth:`Manager.start` is called. This should
                       initialize required components. The :class:`Manager`
                       expects that a call to `close` and `start` is close to
                       equal of recreating the whole instance.
                       
        :func:`close`: Called when :meth:`Manager.close` is called. This should
                       close down the processor cleanly and if potential long
                       running cleanups are to be done should use the
                       :mod:`garbage` sub package shipped with the **audio**
                       package.
                      
        :func:`__init__`: Called when the :class:`Manager` instance is created.
                          This should not start any state dependant parts, these
                          should be done in the `start` method instead.
                          
                          Gets passed one positional argument that is the
                          previous processor in the chain. Or if the first
                          processor read below.
                          
                          Gets passed extra keyword arguments if specified in
                          the class attribute `options`. Read more about this
                          attribute below.
                          
    ---------------
    First processor
    ---------------
    
    The current version expects the first specified processor to take a
    function as `source` argument. That can be called for the filepath of an
    audiofile. This first processor is responsible for opening it.
    
    .. note::
        This means the processor doesn't actually need to decode the file but
        that it is just expected to accept the function as `source`. What it
        does with the function is not important to the :class:`Manager`.
        
    
    --------------
    Last processor
    --------------
    
    The current version expects the last specified processor to have several
    methods available to be used by the :class:`Manager`. These are:
    
        :func:`status`: A method that is called when :meth:`status` is called.
                        This should return something of significants to the
                        user.
                        
        :func:`metadata`: A method that accepts a single `unicode` argument.
                          This is called whenever new metadata is found at the
                          start of the processor chain.
    """
    #: A list of processors that are instanced in order and are passed their
    #: previous friend as first argument.
    processors = [files.FileSource, encoder.Encoder, icecast.Icecast]
    def __init__(self, source, processors=None, **options):
        """
        :params source: A callable object that returns a FileInformation object.
                        See :meth:`Manager.get_source` for the exception.
                        
        :params processors: An iterable of processors. 
                            Defaults to :attr:`Manager.processors`
                            
        :params options: The constructor accepts other arbitrary keyword
                         arguments that are passed to processors that have the
                         keyword inside their `options` attribute.
                         
                     Example: If processor **A** defines `options` as the
                              following: '[("my_extra_argument", None)]' and
                              you pass 'my_extra_argument' as an keyword
                              argument to the :class:`Manager` class it
                              would be passed to processor **A** when
                              creating the class instance. Or if the keyword
                              is not given will pass `None` instead.
        """
        super(Manager, self).__init__()
        
        processors = processors or self.processors
        
        self.instances = []
        
        self.started = threading.Event()
        
        last_proc = None
        for processor in processors:
            for option, default in getattr(processor, 'options', []):
                proc_options[option] = options.get(option, default)
            
            logger.debug("Creating {!r} instance.".format(processor))
            # Create our processor instance with requested options.
            # NOTE: We don't call the `start` method here but in our own `start`
            #       instead. Please don't change this.            
            proc_instance = processor(last_proc, **proc_options)
            
            # Append it to the instances list so we don't lose reference to
            # them. Or garbage collect them by accident.
            self.instances.append(proc_instance)
            
            # Set our `last_proc` so we have an easy reference to pass to the
            # next processor.
            last_proc = proc_instance
        
        self.source = source
        
    def start(self):
        """
        Calls the `start` method on all registered processor instances.
        
        This method does nothing if a previous call to :meth:`start` was
        successfull but :meth:`close` was not called inbetween the two calls.
        
        .. warning::
            Exceptions are propagated.
        """
        if not self.started.is_set():
            for proc in self.instances:
                proc.start()
                
            self.started.set()
            
    def status(self):
        """
        Calls the `status` method on the last processor in the chain.
        
        If no method was found returns :const:`False` instead.
        """
        status = getattr(self.instances[-1], 'status', False)
        # Make sure we don't call the `status` method when not needed.
        return status() if status else status
    
    def get_source(self):
        """
        :returns unicode: A full file path to an audio file.
        
        .. note::
            This can also return :const:`None` if the user gives us a
            :const:`None` as filename. This should be handled properly.
        
        -------------------
        Source return value
        -------------------
        
        The value returned from :meth:`Manager.source` is expected to be an
        :class:`FileInformation` object. But there is one exception to this
        rule.
        
        When :meth:`Manager.source` returns a different type it will be used 
        as the positional arguments to the :class:`FileInformation` constructor
        by using the `FileInformation(*returntype)` syntax.
        """
        info = self.source()
        
        if not isinstance(info, FileInformation):
            info = FileInformation(*info)
            
        if info.filename is None:
            # If the filename is set to None we should close ourself implicitly
            self.close()
            # As well as closing ourself we also return None here to let the
            # callee know we are closing down. The callee should handle this
            # case properly.
            return None
        
        if info.metadata:
            # We don't check for explicit None here since if there is no actual
            # metadata passed it is set to an empty unicode sequence instead.
            self.instances[-1].metadata(info.metadata)
            
        return info.filename
    
    
        try:
            audiofile = files.AudioFile(filename)
        except (files.AudioError) as err:
            logger.exception("Unsupported file.")
            return self.give_source()
        except (IOError) as err:
            logger.exception("Failed opening file.")
            return self.give_source()
        else:
            print meta
            if hasattr(self, 'icecast'):
                self.icecast.set_metadata(meta)
            return audiofile
    
    def close(self):
        """
        Calls the `close` method on all registered processor instances.
        
        .. warning::
            Exceptions are propagated.
        """
        self.started.clear()
        
        for proc in self.instances:
            proc.close()


class FileInformation(object):
    """
    A class that should be returned from the function passed to
    :class:`Manager` for file discovery. 
    
    This is to make switching functions easier since the :class:`Manager` 
    doesn't need to know what format the function returns but only know that
    it returns a :class:`FileInformation` instance instead.
    
    .. note::
        The above has one exception and this can be found in the documents of
        :meth:`Manager.give_source`.
    """
    def __init__(self, filename, metadata=None):
        """
        :param unicode filename: The full path to the audio file.
        :param metadata: A single unicode string that is the metadata to send
                         to the icecast. If not given it will try to read this
                         from the tags in the file.
                         
         .. note::
             If the metadata parameter isn't given it tries to read the file
             with the `mutagen` module and pull out the `artist` and `title`
             tag in the following format "[artist -] title" where the `artist`
             is left out if none is found.
        """
        super(FileInformation, self).__init__()
        
        self.filename = filename
        
        if metadata is None:
            self.metadata = metadata
        else:
            try:
                meta = mutagen.File(filename, easy=True)
            except:
                # TODO: Find the exact exceptions mutagen can raise.
                # WARNING: The instancing of this object should NEVER raise an
                #          exception to the callee that isn't expected.
                meta = ''
            else:
                # Either get the artist or the implicit None
                artist = meta.get('artist')
                # Same as for the artist
                title = meta.get('title')
                
                # Check if we need the artist formatting or not.
                meta = u"{:s} - {:s}" if artist else u"{:s}"
                
                # mutagen returns a list of unicode objects so we join them on
                # a nice comma for the end result.
                if artist:
                    artist = u", ".join(artist)
                if title:
                    title = u", ".join(title)
                meta = meta.format(artist, title)
                
            self.metadata = meta
            

def test_dir(directory=u'/media/F/Music', files=None):
    import os
    import mutagen
    files = set() if files is None else files
    for base, dir, filenames in os.walk(directory):
        for name in filenames:
            files.add(os.path.join(base, name))
    
    def pop_file():
        try:
            filename = files.pop()
        except KeyError:
            return (None, None)
        if (filename.endswith('.flac') or
                filename.endswith('.mp3') or
                filename.endswith('.ogg')):
            try:
                meta = mutagen.File(filename, easy=True)
            except:
                meta = "No metadata available, because I errored."
            else:
                artist = meta.get('artist')
                title = meta.get('title')
                
                meta = u"{:s} - {:s}" if artist else u"{:s}"
                
                if artist:
                    artist = u", ".join(artist)
                if title:
                    title = u", ".join(title)
                meta = meta.format(artist, title)
            return (filename, meta)
        else:
            return pop_file()
    return pop_file

def test_config(password=None):
    return {'host': 'stream.r-a-d.io',
            'port': 1130,
            'password': password,
            'format': 1,
            'protocol': 0,
            'mount': 'test.mp3'}