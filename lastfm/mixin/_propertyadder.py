#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm.mixin"

def property_adder(cls):
    for p in cls.Meta.properties:
        if not hasattr(cls, p):
            def wrapper():
                q = p
                @property
                def get(self):
                    try:
                        return getattr(self, "_{0}".format(q))
                    except AttributeError:
                        return None
                return get
            setattr(cls, p, wrapper())
            
    if hasattr(cls.Meta, 'fillable_properties'):
        for p in cls.Meta.fillable_properties:
            if not hasattr(cls, p):
                def wrapper():
                    q = p
                    @property
                    def get(self):
                        fill = False
                        try:
                            attrval = getattr(self, "_{0}".format(q))
                            if attrval is None:
                                fill = True
                            else:
                                return attrval
                        except AttributeError:
                            fill = True
                        if fill:
                            self._fill_info()
                            return getattr(self, "_{0}".format(q))
                    return get
                setattr(cls, p, wrapper())
    return cls