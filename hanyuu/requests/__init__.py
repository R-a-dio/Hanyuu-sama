from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from .. import config
import logging


logger = logging.getLogger('hanyuu.requests')


# TODO: Add this to the Song abstraction layer instead.
def songdelay(val):
    """Gives the time delay in seconds for a specific song
    request count.
    """
    import math
    if val > 20:
        val = 20
    #return int(29145 * math.exp(0.0476 * val) + 0.5)
    #return int(0.1791*val**4 - 17.184*val**3 + 557.07*val**2 - 3238.9*val + 30687 + 0.5)
    #return int(25133*math.exp(0.1625*val)+0.5)
    return int(-123.82*val**3 + 3355.2*val**2 + 10110*val + 51584 + 0.5)


request_response = '''
<html>
    <head>
        <title>R/a/dio</title>
        <meta http-equiv="refresh" content="5;url=/search/">
        <link rel="shortcut icon" href="/favicon.ico" />
    </head>
    <body>
        <center><h2>{message:s}</h2></center><br />
        <center><h3>You will be redirected shortly.</h3></center>
    </body>
</html>
'''
