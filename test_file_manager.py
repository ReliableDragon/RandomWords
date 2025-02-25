import logging

from file_manager import FileManager
from test_directories import TestDirectories

logger = logging.getLogger(__name__)

class TestFileManager(FileManager):
  
  def __init__(self, root = 'invalid/'):
    super().__init__(root)

  def __enter__(self):
    self.td = TestDirectories()
    self.td.__enter__()
    self.__init__(self.td.root)

    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.td.__exit__(exc_type, exc_val, exc_tb)
    self.td = None
