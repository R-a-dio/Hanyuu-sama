import sys
from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

argv = []
argv.append(sys.argv[0])
argv.append('build_ext')
argv.append('--inplace')
sys.argv = argv

ext_modules = [Extension(
    "pylibshout", ["pylibshout.pyx"],
    libraries = ['shout'] #.h files
)]

setup(
    cmdclass = {'build_ext': build_ext},
    ext_modules = ext_modules,
)

#build it: python setup.py build_ext --inplace
#create distribution: python setup.py sdist
