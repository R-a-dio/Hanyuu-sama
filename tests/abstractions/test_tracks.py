from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from .. import db
import unittest
import hanyuu.abstractions.tracks as tracks

def test_track_with_all():
    """
    Returns a :class:`tracks.Track` instance with all possible data set.
    """
    return tracks.Track('Izaya Orihara - Renai Circulation')


class TestTrackCreation(unittest.TestCase):
    def test_simple_meta(self):
        song = test_track_with_all()
        self.assertIsNot(song._song, None)
        self.assertIsNot(song._track, None)

    def test_unexisting_meta(self):
        song = tracks.Track('I don\'t exist in here.')
        self.assertIs(song._song.hash, None)
        self.assertIs(song._track, None)


class TestLength(unittest.TestCase):
    def test_small_length(self):
        length = tracks.Length(200)
        self.assertEqual(length, 200,
                         "Equality check to initialization value failed.")
        self.assertTrue(isinstance(length, int),
                        "Not a proper subclass of `int`.")
        self.assertEqual(length.format(), '03:20',
                         "Formatting string is invalid.")

    def test_big_length(self):
        length = tracks.Length(6000)
        self.assertEqual(length, 6000,
                         "Equality check to initialization value failed.")
        self.assertTrue(isinstance(length, int),
                        "Not a proper subclass of `int`.")
        self.assertEqual(length.format(), '01:40:00',
                         "Formatting string is invalid.")

class TestTrackGettersGood(unittest.TestCase):
    def setUp(self):
        self.song = test_track_with_all()

    def test_length(self):
        self.assertEqual(self.song.length, 252)

        self.assertIsInstance(self.song.length, int)

    def test_length_format(self):
        self.assertEqual(self.song.length.format(), '04:12')

        self.assertIsInstance(self.song.length.format(), unicode)

    def test_filename(self):
        self.assertEqual(self.song.filename, '3gi8bnvaonc.mp3')

        self.assertIsInstance(self.song.filename, unicode)

    def test_filepath(self):
        # TODO: We just check for None here because the path can't be accurately
        #         transmitted to this code.
        self.assertIsNot(self.song.filepath, None)

        self.assertIsInstance(self.song.filepath, unicode)

    def test_plays(self):
        self.assertIsNot(self.song.plays, None)

    def test_requests(self):
        self.assertIsNot(self.song.requests, None)

    def test_metadata(self):
        self.assertEqual(self.song.metadata, 'Izaya Orihara - Renai Circulation')

        self.assertIsInstance(self.song.metadata, unicode)

    def test_artist(self):
        self.assertEqual(self.song.artist, 'Izaya Orihara')

        self.assertIsInstance(self.song.artist, unicode)

    def test_title(self):
        self.assertEqual(self.song.title, 'Renai Circulation')

        self.assertIsInstance(self.song.title, unicode)


class TestTrackRequests(unittest.TestCase):
    def setUp(self):
        self.song = test_track_with_all()
        self.requests = self.song.requests

    def test_sequence(self):
        self.assertListEqual(list(self.requests), self.requests)

    def test_last(self):
        import datetime
        self.assertEqual(self.requests.last,
                         datetime.datetime(2012, 12, 27, 7, 12, 3))

        self.assertIsInstance(self.requests.last, datetime.datetime)

class TestTrackPlayed(unittest.TestCase):
    def setUp(self):
        self.song = test_track_with_all()
        self.plays = self.song.plays

    def test_sequence(self):
        self.assertListEqual(list(self.plays), self.plays)

    def test_last(self):
        import datetime
        self.assertEqual(self.plays.last,
                         datetime.datetime(2012, 12, 27, 11, 1, 2))

        self.assertIsInstance(self.plays.last, datetime.datetime)
