
import pathlib

from unittest.mock import MagicMock


def make_mock_file(filename, suffix='.txt', is_dir=False):
    mock_file_object = MagicMock(spec=pathlib.Path)
    mock_file_object.__str__.return_value = filename
    mock_file_object.name = filename
    mock_file_object.suffix = '' if is_dir else suffix
    mock_file_object.is_dir.return_value = is_dir
    return mock_file_object

