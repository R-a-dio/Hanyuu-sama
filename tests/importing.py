import unittest

class TestImports(unittest.TestCase):
    def test_abstraction(self):
        import hanyuu.abstractions
        import hanyuu.abstractions.tracks
        import hanyuu.abstractions.users
        
    def test_db(self):
        import hanyuu.db
        import hanyuu.db.common
        import hanyuu.db.legacy
        import hanyuu.db.models
        
    def test_ircbot(self):
        import hanyuu.ircbot
        import hanyuu.ircbot.irclib
        import hanyuu.ircbot.commands
        
    def test_listener(self):
        import hanyuu.listener
        
    def test_requests(self):
        import hanyuu.requests
        import hanyuu.requests.servers
        
    def test_status(self):
        import hanyuu.status
        
    def test_streamer(self):
        import hanyuu.streamer
        import hanyuu.streamer.audio
        import hanyuu.streamer.audio.garbage
        