from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from . import common
import logging
import peewee
import datetime


logger = common.logger.getChild('models')


class Base(peewee.Model):
    """Simple base class to inherit from so all the other models
    inherit the database connection used."""
    class Meta:
        database = common.radio_database
        
class DJ(Base):
    """
    Models the legacy `djs` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True)
    
    name = peewee.CharField(max_length=60,
                            unique=True, db_column='djname')
    
    description = peewee.TextField(db_column='djtext')
    
    image = peewee.TextField(db_column='djimage')
    
    visible = peewee.IntegerField()
    
    priority = peewee.IntegerField()
    
    css = peewee.CharField(max_length=60)
    
    class Meta:
        db_table = 'djs'
        
        
class User(Base):
    """
    Models the legacy `users` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True)
    
    name = peewee.CharField(max_length=50, db_column='user')
    
    password = peewee.CharField(max_length=120, db_column='pass')
    
    dj = peewee.ForeignKeyField(DJ, related_name='user', db_column='djid')
    
    privileges = peewee.IntegerField(db_column='privileges')
    
    class Meta:
        db_table = 'users'


class Radvar(Base):
    """
    Models the legacy `radvars` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True)
    
    name = peewee.CharField(max_length=60)
    
    value = peewee.TextField()
    
    class Meta:
        db_table = 'radvars'


class Nickrequest(Base):
    """
    Models the legacy `nickrequesttime` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True)
    
    host = peewee.TextField()
    
    # docs claim that DateTimeField will become mysql datetime columns
    # we have timestamp; is this going to be a problem?
    time = peewee.DateTimeField()
    
    class Meta:
        db_table='nickrequesttime'

class LastFm(Base):
    """
    Models the legacy `lastfm` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True)
    
    nick = peewee.CharField(max_length=150)
    
    username = peewee.CharField(max_length=150, 
                                db_column='user')
    
    class Meta:
        db_table = 'lastfm'


class Nickname(Base):
    """
    Models the legacy `enick` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True)
    
    nickname = peewee.CharField(max_length=30, 
                                unique=True, 
                                db_column='nick')
    
    first_seen = peewee.DateTimeField(db_column='dta', 
                                      default=datetime.datetime.now())
    
    # this is not used for anything
    dtb = peewee.DateTimeField()
    
    authcode = peewee.CharField(max_length=8, null=True)
    
    class Meta:
        db_table = 'enick'


class Song(Base):
    """
    Models the legacy `esong` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True)
    
    hash = peewee.CharField(max_length=40, 
                            unique=True)
    
    length = peewee.IntegerField(db_column='len')
    
    meta = peewee.TextField()
    
    # this was added by me but it was never used
    # it could be a ForeignKey but meh
    hash_link = peewee.CharField(max_length=40)
    
    class Meta:
        db_table='esong'


class Play(Base):
    """
    Models the legacy `eplay` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True)
    
    song = peewee.ForeignKeyField(Song, related_name='plays', 
                                        db_column='isong')
    
    time = peewee.DateTimeField(db_column='dt', 
                                default=datetime.datetime.now())
    
    class Meta:
        db_table='eplay'


class Fave(Base):
    """
    Models the legacy `efave` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True)
    
    nickname = peewee.ForeignKeyField(Nickname, related_name='faves', 
                                                db_column='inick')
    
    song = peewee.ForeignKeyField(Song, related_name='faves', 
                                        db_column='isong')
    
    class Meta:
        db_table='efave'


class Track(Base):
    """
    Models the legacy `tracks` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True)
    
    # does setting varchar to greater size than 255 actually work?
    # also i love how the columns in db are NOT NULL DEFAULT NULL
    artist = peewee.CharField(max_length=500)
    
    title = peewee.CharField(max_length=200, db_column='track')
    
    album = peewee.CharField(max_length=200)
    
    path = peewee.TextField()
    
    search_tags = peewee.TextField(db_column='tags')
    
    last_played = peewee.DateTimeField(db_column='lastplayed')
    
    last_requested = peewee.DateTimeField(db_column='lastrequested')
    
    usable = peewee.IntegerField()
    
    acceptor = peewee.CharField(max_length=200, db_column='accepter')
    
    last_editor = peewee.CharField(max_length=200, db_column='lasteditor')
    
    hash = peewee.ForeignKeyField(Song, related_name='track')
    
    request_count = peewee.IntegerField(db_column='requestcount')
    
    # hanyuu needs to obey this when picking songs/giving search results!
    needs_reupload = peewee.IntegerField(db_column='need_reupload')
    
    class Meta:
        db_table = 'tracks'