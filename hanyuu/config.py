from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import yaml
import logging
import os.path
import hanyuu


logger = logging.getLogger('hanyuu.config')
# A sentinal object to make sure we don't accidently raise on None
SENTINAL = object()

class AttributeDict(dict):
    def __getattr__(self, key):
        value = super(AttributeDict, self).get(key, SENTINAL)
        if value is SENTINAL:
            raise KeyError("No such key: {:s}".format(key))
        if isinstance(value, dict):
            # We want to make sure we can chain attributes afterall!
            return AttributeDict(value)
        return value


class Settings(AttributeDict):
    """
    A relatively simple and small class that is injected as a module in
    `sys.modules`. This object allows for attribute access on the returned
    yaml dictionary.
    """
    filename = None
    def __init__(self):
        super(Settings, self).__init__()

    def load(self, filename):
        """
        Loads a configuration file and tries parsing it, before exporting it
        as the active configuration.

        If this is called when another file is already loaded the previous
        file will be dumped in preference for the new file.

        raises: Any exceptions possible from :func:`open` and :func:`yaml.safe_load`
        return: None
        """
        filename = os.path.abspath(os.path.expanduser(filename))
        with open(filename, 'rb') as f:
            config = yaml.safe_load(f.read())

        # TODO: Make this thread-safe
        self.clear()
        self.update(config)
        self.filename = filename

    def reload(self):
        """
        A convience function that reloads the currently loaded configuration
        file with the filename used last.

        raises: Any exceptions possible from :func:`open` and :func:`yaml.safe_load`.
        """
        self.load(self.filename)


settings = Settings()
hanyuu.settings = settings

def open_file(filename):
    """
    Open a filename, and apply it to the settings object currently
    active
    """
    settings.load(filename)

