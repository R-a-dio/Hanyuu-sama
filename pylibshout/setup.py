"""Python libshout2 interface

Based on the c-libary libshout 2 and built with Cython
"""

classifiers = """\
Development Status :: 3 - Alpha
Intended Audience :: Developers
Programming Language :: Python
Topic :: Software Development :: Libraries :: Python Modules
Topic :: Multimedia :: Sound/Audio
Operating System :: OS Independent
"""

from distutils.core import setup
from distutils.extension import Extension

doclines = __doc__.split("\n")

ext_modules = [Extension(
    "pylibshout", ["pylibshout.c"],
    libraries = ['shout'] #.h files
)]

setup(
    name = 'pylibshout',
    version = '0.0.1',
    author = 'Leon Bogaert',
    author_email = 'leon@vanutsteen.nl',
    url = 'http://github.com/LeonB/pylibshout',
    platforms = ["any"],
    description = doclines[0],
    classifiers = filter(None, classifiers.split("\n")),
    long_description = "\n".join(doclines[2:]),
    #py_modules = ['pylibshout'],
    ext_modules = ext_modules,
    requires = ['Cython']
)
