# tests/services/test_language_service.py
import pytest
from flask import Flask, g
from unittest.mock import MagicMock, patch, call
from iatoolkit.services.language_service import LanguageService
from iatoolkit.repositories.profile_repo import ProfileRepo
from iatoolkit.repositories.models import Company, User


class TestLanguageService:
    """
    Unit tests for the LanguageService.
    """

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """
        Pytest fixture that runs before each test.
        - Mocks the ProfileRepo dependency.
        - Creates a fresh instance of LanguageService.
        - Creates a Flask app to provide a request context for tests.
        """
        self.mock_profile_repo = MagicMock(spec=ProfileRepo)
        self.language_service = LanguageService(profile_repo=self.mock_profile_repo)

        # A Flask app is necessary to create a request context
        self.app = Flask(__name__)

        # Mock company objects for predictable test data
        self.company_en = Company(id=1, short_name='acme-en', default_language='en')
        self.company_fr = Company(id=2, short_name='acme-fr', default_language='fr')
        self.company_no_lang = Company(id=3, short_name='acme-no-lang', default_language=None)

        # Mock user objects
        self.user_with_lang_de = User(id=1, email='user-de@acme.com', preferred_language='de')
        self.user_without_lang = User(id=2, email='user-no-lang@acme.com', preferred_language=None)

        # Register a dummy route that matches the URL structure used in tests.
        # This allows Flask's test context to correctly parse `company_short_name`.
        @self.app.route('/<company_short_name>/login')
        def dummy_route_for_test(company_short_name):
            return "ok"

    # --- Priority 1 Tests: User Preference ---

    @patch('iatoolkit.services.language_service.SessionManager')
    def test_returns_user_language_when_user_has_preference(self, mock_session_manager):
        """
        GIVEN a logged-in user with a preferred language ('de')
        WHEN the current language is requested
        THEN the user's preferred language is returned, ignoring other contexts.
        """
        # Arrange
        mock_session_manager.get.return_value = 'user-de@acme.com'
        self.mock_profile_repo.get_user_by_email.return_value = self.user_with_lang_de

        with self.app.test_request_context():
            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'de'  # The user's preference ('de') should win.
            self.mock_profile_repo.get_user_by_email.assert_called_once_with('user-de@acme.com')
            # Verify that it returned immediately without checking for the company
            self.mock_profile_repo.get_company_by_short_name.assert_not_called()

    # --- Priority 2 Tests: Company Default ---

    @patch('iatoolkit.services.language_service.SessionManager')
    def test_returns_company_language_when_user_has_no_preference(self, mock_session_manager):
        """
        GIVEN a logged-in user with NO preferred language and a company with 'en'
        WHEN the current language is requested
        THEN the company's default language ('en') is returned.
        """
        # Arrange
        def session_get_side_effect(key):
            if key == 'user_identifier':
                return 'user-no-lang@acme.com'
            if key == 'company_short_name':
                return 'acme-en'
            return None
        mock_session_manager.get.side_effect = session_get_side_effect
        self.mock_profile_repo.get_user_by_email.return_value = self.user_without_lang
        self.mock_profile_repo.get_company_by_short_name.return_value = self.company_en

        with self.app.test_request_context():
            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'en'  # The company's language should be used as fallback.
            self.mock_profile_repo.get_user_by_email.assert_called_once_with('user-no-lang@acme.com')
            self.mock_profile_repo.get_company_by_short_name.assert_called_once_with('acme-en')

    @patch('iatoolkit.services.language_service.SessionManager')
    def test_returns_company_language_from_url_when_no_session(self, mock_session_manager):
        """
        GIVEN no user is logged in
        WHEN a request is made to a URL containing a company short name ('acme-fr')
        THEN the company's default language ('fr') is returned.
        """
        # Arrange
        mock_session_manager.get.return_value = None  # No active session
        self.mock_profile_repo.get_company_by_short_name.return_value = self.company_fr

        # Simulate a request to a URL like /acme-fr/login
        with self.app.test_request_context('/acme-fr/login'):
            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'fr'
            self.mock_profile_repo.get_company_by_short_name.assert_called_once_with('acme-fr')
            # Verify that session was checked for both user and company
            mock_session_manager.get.assert_has_calls([call('user_identifier'), call('company_short_name')], any_order=True)

    # --- Priority 3 Tests: System Fallback ---

    @patch('iatoolkit.services.language_service.SessionManager')
    def test_returns_fallback_when_company_has_no_language(self, mock_session_manager):
        """
        GIVEN a company context exists but the company has no default language
        WHEN the current language is requested
        THEN the system-wide fallback language ('es') is returned.
        """
        # Arrange
        mock_session_manager.get.return_value = None  # No user
        self.mock_profile_repo.get_company_by_short_name.return_value = self.company_no_lang

        with self.app.test_request_context('/acme-no-lang/login'):
            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'es'

    @patch('iatoolkit.services.language_service.SessionManager')
    def test_returns_fallback_when_no_context_found(self, mock_session_manager):
        """
        GIVEN no user is logged in and the URL has no company context
        WHEN the current language is requested
        THEN the system-wide fallback language ('es') is returned.
        """
        # Arrange
        mock_session_manager.get.return_value = None  # No session

        with self.app.test_request_context('/health'): # URL without company
            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'es'
            self.mock_profile_repo.get_company_by_short_name.assert_not_called()

    @patch('iatoolkit.services.language_service.SessionManager')
    def test_returns_fallback_on_repository_exception(self, mock_session_manager):
        """
        GIVEN a repository call will fail with an exception
        WHEN the current language is requested
        THEN the service fails gracefully and returns the fallback language ('es').
        """
        # Arrange
        mock_session_manager.get.return_value = 'user@acme.com' # Trigger user lookup
        self.mock_profile_repo.get_user_by_email.side_effect = Exception("Database is down")

        with self.app.test_request_context():
            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'es'

    # --- Caching Test ---

    @patch('iatoolkit.services.language_service.SessionManager')
    def test_returns_cached_language_from_g_without_external_calls(self, mock_session_manager):
        """
        GIVEN the language has already been determined and cached in g.lang
        WHEN the current language is requested again in the same request
        THEN the cached language is returned without any external calls.
        """
        with self.app.test_request_context():
            # Arrange
            g.lang = 'xx-cached'

            # Act
            lang = self.language_service.get_current_language()

            # Assert
            assert lang == 'xx-cached'
            # CRUCIAL: Verify that no external calls were made because the value was cached.
            mock_session_manager.get.assert_not_called()
            self.mock_profile_repo.get_user_by_email.assert_not_called()
            self.mock_profile_repo.get_company_by_short_name.assert_not_called()