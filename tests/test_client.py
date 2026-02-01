import pytest
import responses

from prusa_connect.client import PrusaConnectClient
from prusa_connect.exceptions import PrusaAuthError


class MockCredentials:
    """A dummy authentication strategy for testing."""

    def before_request(self, headers: dict[str, str]) -> None:
        # Simply inject a static token to satisfy the protocol
        headers["Authorization"] = "Bearer mock_token"


@pytest.fixture
def client():
    # We now pass the strategy object, not a string
    return PrusaConnectClient(credentials=MockCredentials())


@responses.activate
def test_get_printers_success(client):
    # 1. Mock the API endpoint
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers",
        json={"printers": [{"uuid": "abc-123", "name": "MK4", "state": "IDLE"}]},
        status=200,
    )

    # 2. Call the method
    printers = client.get_printers()

    # 3. Assertions
    assert len(printers) == 1
    assert printers[0].name == "MK4"
    assert printers[0].uuid == "abc-123"
    # Verify our model parsed the state correctly using the alias
    assert printers[0].printer_state == "IDLE"


@responses.activate
def test_auth_failure_raises_exception(client):
    responses.add(responses.GET, "https://connect.prusa3d.com/app/printers", status=401)

    with pytest.raises(PrusaAuthError):
        client.get_printers()
