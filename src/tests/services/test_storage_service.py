# Copyright (c) 2024 Fernando Libedinsky
# Product: IAToolkit
#
# IAToolkit is open source software.

import unittest
from unittest.mock import MagicMock, patch
import base64
from iatoolkit.services.storage_service import StorageService
from iatoolkit.infra.connectors.s3_connector import S3Connector
from iatoolkit.common.exceptions import IAToolkitException

class TestStorageService(unittest.TestCase):

    def setUp(self):
        # Patch S3Connector class to prevent real connection
        self.connector_patch = patch('iatoolkit.services.storage_service.S3Connector')
        self.mock_s3_class = self.connector_patch.start()

        # The mock instance that will be assigned to self.connector
        self.mock_connector_instance = MagicMock(spec=S3Connector)
        self.mock_s3_class.return_value = self.mock_connector_instance

        self.service = StorageService()

    def tearDown(self):
        self.connector_patch.stop()

    def test_init_connector_configuration(self):
        # Verify that S3Connector was instantiated
        self.mock_s3_class.assert_called_once()

        # Verify call args (bucket, auth, etc.)
        call_kwargs = self.mock_s3_class.call_args.kwargs
        self.assertIn('bucket', call_kwargs)
        self.assertIn('auth', call_kwargs)
        self.assertEqual(call_kwargs['prefix'], "")

    def test_store_generated_image_success(self):
        # Arrange
        company_short_name = "test_co"
        # "hello" in base64 is "aGVsbG8="
        raw_base64 = "aGVsbG8="
        mime_type = "image/png"
        expected_url = "https://fake-s3-url.com/image.png"

        self.mock_connector_instance.generate_presigned_url.return_value = expected_url

        # Act
        result = self.service.store_generated_image(company_short_name, raw_base64, mime_type)

        # Assert
        # 1. Check return structure
        self.assertEqual(result['url'], expected_url)
        self.assertTrue(result['storage_key'].startswith(f"companies/{company_short_name}/generated_images/"))
        self.assertTrue(result['storage_key'].endswith(".png"))

        # 2. Check upload call
        self.mock_connector_instance.upload_file.assert_called_once()
        args = self.mock_connector_instance.upload_file.call_args

        # Verify uploaded content is bytes and decoded correctly
        uploaded_content = args.kwargs['content']
        self.assertEqual(uploaded_content, b"hello")
        self.assertEqual(args.kwargs['content_type'], mime_type)

    def test_store_generated_image_strips_header(self):
        # Arrange: Input with data URI scheme header
        base64_with_header = "data:image/jpeg;base64,aGVsbG8=" # "hello"

        # Act
        self.service.store_generated_image("co", base64_with_header, "image/jpeg")

        # Assert: Verify only the payload was decoded
        args = self.mock_connector_instance.upload_file.call_args
        self.assertEqual(args.kwargs['content'], b"hello")

    def test_store_generated_image_handles_connector_error(self):
        # Arrange
        self.mock_connector_instance.upload_file.side_effect = Exception("Connection lost")

        # Act & Assert
        with self.assertRaises(IAToolkitException) as context:
            self.service.store_generated_image("co", "AAAA", "image/png")

        self.assertEqual(context.exception.error_type, IAToolkitException.ErrorType.FILE_IO_ERROR)
        self.assertIn("Connection lost", str(context.exception))

    def test_get_public_url(self):
        # Arrange
        key = "some/path/file.jpg"
        self.mock_connector_instance.generate_presigned_url.return_value = "http://signed-url"

        # Act
        url = self.service.get_public_url(key)

        # Assert
        self.assertEqual(url, "http://signed-url")
        self.mock_connector_instance.generate_presigned_url.assert_called_once_with(key)