import unittest

from unittest.mock import MagicMock

from cd_cmd import CD
from file_manager import FileManager

class CDTest(unittest.TestCase):
  
  def test_execute(self):
    fm = MagicMock(spec=FileManager)
    cd = CD(fm)

    cd.execute(['foo/bar'], None)

    fm.cd.assert_called_once_with('foo/bar')
