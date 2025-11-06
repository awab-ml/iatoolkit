# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

from iatoolkit.services.excel_service import ExcelService
from iatoolkit.services.i18n_service import I18nService
from iatoolkit.common.util import Utility
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import pytest
from flask import Flask


class TestExcelService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = Flask(__name__)
        self.app.testing = True

        # Create real temporary directory structure
        self.temp_dir_base = tempfile.mkdtemp()
        self.app.root_path = self.temp_dir_base
        self.temp_dir = os.path.join(self.temp_dir_base, 'static', 'temp')
        os.makedirs(self.temp_dir, exist_ok=True)

        # Mocks of services
        self.util = MagicMock(spec=Utility)
        self.mock_i18n_service = MagicMock(spec=I18nService)
        self.excel_service = ExcelService(util=self.util, i18n_service=self.mock_i18n_service)

        self.mock_i18n_service.t.side_effect = lambda key, **kwargs: f"translated:{key}"

        yield

        # Cleanup after test
        shutil.rmtree(self.temp_dir_base)

    def create_test_file(self, filename, content=b'test content'):
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(content)
        return file_path

    def test_validate_file_access_valid_file(self):
        filename = 'valid_file.xlsx'
        self.create_test_file(filename)

        with self.app.app_context():
            with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is None

    def test_validate_file_access_path_traversal_dotdot(self):
        filename = '../../../etc/passwd'

        with self.app.app_context():
            with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'translated:errors.services.invalid_filename'

    def test_validate_file_access_path_traversal_absolute_unix(self):
        filename = '/etc/passwd'

        with self.app.app_context():
            with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'translated:errors.services.invalid_filename'

    def test_validate_file_access_path_traversal_backslash(self):
        filename = 'folder\\..\\sensitive_file.txt'

        with self.app.app_context():
            with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'translated:errors.services.invalid_filename'

    def test_validate_file_access_file_not_found(self):
        filename = 'non_existent_file.xlsx'

        with self.app.app_context():
            with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'translated:errors.services.file_not_exist'

    def test_validate_file_access_is_directory(self):
        dirname = 'test_directory'
        dir_path = os.path.join(self.temp_dir, dirname)
        os.makedirs(dir_path)

        with self.app.app_context():
            with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(dirname)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'translated:errors.services.path_is_not_a_file'

    def test_validate_file_access_exception_handling(self):
        filename = 'test_file.xlsx'

        with self.app.app_context():
            with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                with patch('iatoolkit.services.excel_service.os.path.exists', side_effect=Exception("Test exception")):
                    result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'translated:errors.services.file_validation_error'

    def test_validate_file_access_logs_exception(self):
        filename = 'test_file.xlsx'

        with patch('iatoolkit.services.excel_service.logging') as mock_logging:
            with patch('iatoolkit.services.excel_service.os.path.exists', side_effect=Exception("Test exception")):
                with self.app.app_context():
                    with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                        mock_current_app.root_path = self.temp_dir_base
                        self.excel_service.validate_file_access(filename)

        mock_logging.error.assert_called_once()
        error_msg = mock_logging.error.call_args[0][0]
        assert 'File validation error test_file.xlsx' in error_msg
        assert 'Test exception' in error_msg

    def test_validate_file_access_various_valid_filenames(self):
        with self.app.app_context():
            with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base

                valid_filenames = [
                    'simple.xlsx',
                    'file_with_underscores.xlsx',
                    'file-with-dashes.xlsx',
                    'file with spaces.xlsx',
                    'file123.xlsx',
                    'UPPERCASE.XLSX',
                    'file.with.dots.xlsx'
                ]

                for filename in valid_filenames:
                    self.create_test_file(filename)
                    result = self.excel_service.validate_file_access(filename)
                    assert result is None, f"Filename '{filename}' should be valid"

    def test_validate_file_access_various_invalid_filenames(self):
        with self.app.app_context():
            with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base

                invalid_filenames = [
                    '../file.xlsx',
                    '../../file.xlsx',
                    '/absolute/path/file.xlsx',
                    'folder\\file.xlsx',
                    '..\\file.xlsx',
                    'file..xlsx/../other.xlsx',
                    '/etc/passwd',
                    'C:\\Windows\\System32\\config'
                ]

                for filename in invalid_filenames:
                    result = self.excel_service.validate_file_access(filename)
                    assert result is not None, f"Filename '{filename}' should be invalid"
                    data = result.get_json()
                    assert data['error'] == 'translated:errors.services.invalid_filename'

    def test_validate_file_access_empty_filename(self):
        filename = ''

        with self.app.app_context():
            with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(filename)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'translated:errors.services.invalid_filename'

    def test_validate_file_access_none_filename(self):
        with self.app.app_context():
            with patch('iatoolkit.services.excel_service.current_app') as mock_current_app:
                mock_current_app.root_path = self.temp_dir_base
                result = self.excel_service.validate_file_access(None)

        assert result is not None
        data = result.get_json()
        assert data['error'] == 'translated:errors.services.invalid_filename'
