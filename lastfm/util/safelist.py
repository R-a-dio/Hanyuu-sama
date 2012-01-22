#!/usr/bin/env python

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm.util"

import sys
class SafeList(object):
    def __init__(self, lst, add_func, remove_func):
        self._list = lst
        self._add_func = add_func
        self._remove_func = remove_func

    def add(self, lst):
        if not isinstance(lst, (list, tuple)):
            lst = [lst]
        self._add_func(lst)

    def remove(self, lst):
        if not isinstance(lst, (list, tuple)):
            lst = [lst]
        for l in lst:
            self._remove_func(l)

    def __iter__(self):
        for i in xrange(len(self._list)):
            yield self._list[i]

    def _tuple_from_slice(self, i):
        """
        Get (start, end, step) tuple from slice object.
        """
        (start, end, step) = i.indices(len(self._list))
        # Replace (0, -1, 1) with (0, 0, 1) (misfeature in .indices()).
        if step == 1:
            if end < start:
                end = start
            step = None
        if i.step == None:
            step = None
            return (start, end, step)


    def __getitem__(self, i):
        if isinstance(i, slice):
            (start, end, step) = self._tuple_from_slice(i)
            if step == None:
                indices = xrange(start, end)
            else:
                indices = xrange(start, end, step)
            return [self._list[i] for i in indices]
        else:
            return self._list[i]

    def index(self, x, i=0, j=None):
        if i != 0 or j is not None:
            (i, j, ignore) = self._tuple_from_slice(slice(i, j))
        if j is None:
            j = len(self)
        for k in xrange(i, j):
            if self._list[k] == x:
                return k
        raise ValueError('index(x): x not in list')

    # Define sort() as appropriate for the Python version.
    if sys.version_info[:3] < (2, 4, 0):
        def sort(self, cmpfunc=None):
            ans = list(self._list)
            ans.sort(cmpfunc)
            self._list[:] = ans
    else:
        def sort(self, cmpfunc=None, key=None, reverse=False):
            ans = list(self._list)
            if reverse == True:
                ans.sort(cmpfunc, key, reverse)
            elif key != None:
                ans.sort(cmpfunc, key)
            else:
                ans.sort(cmpfunc)
            self._list[:] = ans

    def __len__(self):
        return len(self._list)

    def __repr__(self):
        return repr(self._list)
