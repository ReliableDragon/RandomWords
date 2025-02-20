from command import Command

class FileCommand(Command):

  def __init__(self, file_manager):
    super().__init__()
    self.fm = file_manager
