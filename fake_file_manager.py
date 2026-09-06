import logging

from file_manager import FileManager
from fake_directories import FakeDirectories

logger = logging.getLogger(__name__)

class FakeFileManager(FileManager):
  
  def __init__(self, root = 'invalid/'):
    super().__init__(root)

  def __enter__(self):
    self.td = FakeDirectories()
    self.td.__enter__()
    self.__init__(self.td.root)

    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.td.__exit__(exc_type, exc_val, exc_tb)
    self.td = None
