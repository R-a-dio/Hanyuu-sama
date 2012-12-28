from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import logging
import peewee
import __init__ as db


logger = db.logger.getChild('models')


class Base(peewee.Model):
    """Simple base class to inherit from so all the other models
    inherit the database connection used."""
    class Meta:
        database = radio_database
        
        
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
        