import pathlib

from unittest.mock import MagicMock
from tempfile import TemporaryDirectory, NamedTemporaryFile

def make_mock_file(filename, suffix='.txt', is_dir=False):
    mock_file_object = MagicMock(spec=pathlib.Path)
    mock_file_object.__str__.return_value = filename
    mock_file_object.name = filename
    mock_file_object.suffix = '' if is_dir else suffix
    mock_file_object.is_dir.return_value = is_dir
    return mock_file_object

def get_mock_files():
    folder = make_mock_file('testfolder', '', True)
    hidden_folder = make_mock_file('.git', '', True)
    txt_file = make_mock_file('testdict')
    nontxt_file = make_mock_file('testimg', 'jpg')

    mock_path_objects = [folder, hidden_folder, txt_file, nontxt_file] 
    return mock_path_objects
