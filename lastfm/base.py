#!/usr/bin/env python
"""Module containting the base class for all the classes in this package"""

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

class LastfmBase(object):
    """Base class for all the classes in this package"""
    
    def init(self, **kwargs):
        for k in kwargs:
            if (k in self.Meta.properties or
                (hasattr(self.Meta, 'fillable_properties') and
                    k in self.Meta.fillable_properties)):
                setattr(self, "_{0}".format(k), kwargs[k])
    
    def __eq__(self, other):
        raise NotImplementedError("The subclass must override this method")
    
    def __lt__(self, other):
        raise NotImplementedError("The subclass must override this method")

    def __gt__(self, other):
        return not (self.__lt__(other) or self.__eq__(other))

    def __ne__(self, other):
        return not self.__eq__(other)

    def __ge__(self, other):
        return not self.__lt__(other)

    def __le__(self, other):
        return not self.__gt__(other)