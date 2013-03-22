import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
      name="Hanyuu-sama",
      version="1.2.0a",
      author='Wessie',
      author_email='r-a-dio@wessie.info',
      description=("Developer version of Hanyuu-sama, a complete "
                     "package including an IRC bot, Icecast streamer "
                     "and FastCGI request server."),
      license='GPL',
      install_requires=[
                  "requests >= 1.0",
                  "mutagen >= 1.19",
                  "flup >= 1.0.2",
                  "pymysql",
                  "PyYAML>=3.05",
                  "xmltodict >= 0.4",
                  "peewee >= 2.0",
                  "bjsonrpc",
                  # "pylibmc >= 1.2.3",
                  "audiotools >= 2.19",
                  "pylibshout >= 1.0",
                  #"python-audio-tools >= 2.19",
      ],
      dependency_links = [
          "http://r-a-d.io/etc/python-pkg/"
      ],
      entry_points={
          "console_scripts": [
              "hanyuu = hanyuu.runner:main",
          ],
      },
      keywords="streaming icecast fastcgi irc",
      packages=['hanyuu', 'hanyuu.db', 'hanyuu.abstractions',
                'hanyuu.ircbot', 'hanyuu.status', 'hanyuu.streamer',
                'hanyuu.streamer.audio', 'hanyuu.streamer.audio.garbage',
                'hanyuu.ircbot.irclib'],
      )
