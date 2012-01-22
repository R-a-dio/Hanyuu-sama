#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm.mixin"

def sharable(cls):
    def share(self, recipient, message = None):
        from lastfm.user import User
        params = self._default_params({'method': '%s.share' % self.__class__.__name__.lower()})
        if message is not None:
            params['message'] = message
        
        if not isinstance(recipient, list):
            recipient = [recipient]
            
        for i in xrange(len(recipient)):
            if isinstance(recipient[i], User):
                recipient[i] = recipient[i].name
        params['recipient'] = ",".join(recipient)
        self._api._post_data(params)
        
    def _default_params(self, extra_params = None):
        if extra_params is not None:
            return extra_params
        else:
            return {}
        
    cls.share = share
    if not hasattr(cls, '_default_params'):
        cls._default_params = _default_params
    
    if not hasattr(cls, '_mixins'):
            cls._mixins = []
    cls._mixins.append('share')
    
    return cls