from unittest import mock

import pytest
import prusa_connect
from prusa_connect import PrusaConnectClient
from prusa_connect.client import AuthStrategy


class MockCredentials(AuthStrategy):
    def before_request(self, headers: dict[str, str]) -> None:
        headers["Authorization"] = "Bearer mock_token"


@pytest.fixture
def client():
    return PrusaConnectClient(credentials=MockCredentials())


def test_default_timeout(client):
    """Test that requests use the default timeout."""
    with mock.patch.object(client._session, "request") as mock_request:
        # Mock response to avoid errors
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.content = b"{}"
        mock_request.return_value = mock_response

        client.get_printers()

        mock_request.assert_called()
        # Check that timeout=30.0 was passed
        args, kwargs = mock_request.call_args
        assert kwargs["timeout"] == 30.0


def test_custom_timeout():
    """Test that a custom timeout in __init__ is respected."""
    client = PrusaConnectClient(credentials=MockCredentials(), timeout=10.0)
    with mock.patch.object(client._session, "request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.content = b"{}"
        mock_request.return_value = mock_response

        client.get_printers()

        args, kwargs = mock_request.call_args
        assert kwargs["timeout"] == 10.0


def test_override_timeout(client):
    """Test that per-request timeout overrides the default."""
    with mock.patch.object(client._session, "request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.content = b"{}"
        mock_request.return_value = mock_response

        client.api_request("GET", "/test", timeout=5.0)

        args, kwargs = mock_request.call_args
        assert kwargs["timeout"] == 5.0


def test_top_level_imports():
    """Test that important classes are exposed at the top level."""
    assert hasattr(prusa_connect, "PrusaConnectClient")
    assert hasattr(prusa_connect, "Printer")
    assert hasattr(prusa_connect, "Job")
    assert hasattr(prusa_connect, "PrinterState")
    assert hasattr(prusa_connect, "PrusaApiError")
