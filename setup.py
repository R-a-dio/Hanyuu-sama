import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
      name = "Hanyuu-sama",
      version = "1.2.0",
      author = 'Wessie',
      author_email = 'r-a-dio@wessie.info',
      description = ("Developer version of Hanyuu-sama, a complete "
                     "package including an IRC bot, Icecast streamer "
                     "and FastCGI request server."),
      license = 'GPL',
      long_description = read('README'),
      install_requires = [
                  "requests >= 1.0",
                  "mutagen >= 1.19",
                  "flup >= 1.0.2",
                  "pymysql",
                  "xmltodict >= 0.4",
                  "peewee >= 2.0",
                  "pylibmc >= 1.2.3",
                  #"audiotools >= 2.19alpha3",
                          ],
      keywords = "streaming icecast fastcgi irc",
      packages = ['hanyuu'],
      )