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

class TestTrackGetters(unittest.TestCase):
    def setUp(self):
        self.song = test_track_with_all()

    def test_length(self):
        self.assertEqual(self.song.length, 252)

    def test_length_format(self):
        self.assertEqual(self.song.length.format(), '04:12')

    def test_filename(self):
        self.assertEqual(self.song.filename, '3gi8bnvaonc.mp3')

    def test_filepath(self):
        # TODO: We just check for None here because the path can't be accurately
        #         transmitted to this code.
        self.assertIsNot(self.song.filepath, None)

    def test_plays(self):
        self.assertIsNot(self.song.plays, None)

    def test_requests(self):
        self.assertIsNot(self.song.requests, None)

    def test_metadata(self):
        self.assertEqual(self.song.metadata, 'Izaya Orihara - Renai Circulation')
