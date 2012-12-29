from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import peewee
import datetime
from . import models

class Status(models.Base):
    """
    Models the legacy `streamstatus` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True,
                                default=0)
    
    dj = peewee.ForeignKeyField(models.DJ, related_name='status',
                                    default=0,
                                    db_column='djid')
    
    # this could do with a length increase
    now_playing = peewee.CharField(max_length=200,
                                   default='',
                                   db_column='np')
    
    listeners = peewee.IntegerField(default=0)
    
    # this isn't used
    bitrate = peewee.IntegerField(default=192)
    
    is_afk_stream = peewee.IntegerField(default=0,
                                        db_column='isafkstream')
    
    # lol
    is_streamdesk = peewee.IntegerField(default=0,
                                        db_column='isstreamdesk')
    
    start_time = peewee.IntegerField(default=0)
    
    end_time = peewee.IntegerField(default=0)
    
    last_set = peewee.DateTimeField(default=datetime.datetime.now(),
                                    db_table='lastset')
    
    track = peewee.ForeignKeyField(models.Track, related_name='status',
                                   null=True,
                                   default=None)
    
    class Meta:
        db_name='streamstatus'


class Radvar(models.Base):
    """
    Models the legacy `radvars` table.
    """
    id = peewee.PrimaryKeyField(primary_key=True)
    
    name = peewee.CharField(max_length=60)
    
    value = peewee.TextField()
    
    class Meta:
        db_table = 'radvars'
