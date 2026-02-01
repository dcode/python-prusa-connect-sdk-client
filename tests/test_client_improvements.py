from unittest.mock import patch

import pytest
import responses
from requests.exceptions import ReadTimeout

from prusa_connect.client import DEFAULT_TIMEOUT, PrusaConnectClient
from prusa_connect.exceptions import PrusaApiError, PrusaNetworkError


class MockCredentials:
    def before_request(self, headers: dict[str, str]) -> None:
        headers["Authorization"] = "Bearer mock_token"


@pytest.fixture
def client():
    return PrusaConnectClient(credentials=MockCredentials())


def test_timeout_arg_passed_to_session():
    """Verify session.request receives timeout."""
    creds = MockCredentials()
    client = PrusaConnectClient(creds)

    with patch.object(client._session, "request") as mock_request:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {"printers": []}
        mock_request.return_value.headers = {}
        mock_request.return_value.content = b"{}"

        client.get_printers()

        mock_request.assert_called_with(
            "GET",
            "https://connect.prusa3d.com/app/printers",
            timeout=DEFAULT_TIMEOUT
        )


@responses.activate
def test_json_error_parsing(client):
    """Verify that JSON error messages are parsed into PrusaApiError."""
    error_message = "Printer is busy doing something else."
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers",
        json={"error": error_message},
        status=400,
    )

    with pytest.raises(PrusaApiError) as exc_info:
        client.get_printers()

    assert error_message in str(exc_info.value)
    assert exc_info.value.status_code == 400


@responses.activate
def test_json_error_parsing_nested_message(client):
    """Verify that JSON error messages with 'message' key are parsed."""
    error_message = "Something went wrong."
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers",
        json={"message": error_message},
        status=500,
    )

    with pytest.raises(PrusaApiError) as exc_info:
        client.get_printers()

    assert error_message in str(exc_info.value)


@responses.activate
def test_network_timeout_wraps_exception(client):
    """Verify that requests.Timeout is wrapped in PrusaNetworkError."""
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers",
        body=ReadTimeout("Connection timed out"),
    )

    with pytest.raises(PrusaNetworkError):
        client.get_printers()
