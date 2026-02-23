"""Tests for App Config loading and validation."""

import typing
from unittest import mock

import pytest
import requests

from prusa.connect.client import PrusaConnectClient, consts, exceptions


@pytest.fixture
def mock_config_response() -> dict[str, typing.Any]:
    return {
        "auth": {
            "backends": ["PRUSA_AUTH"],
            "server_url": "https://account.prusa3d.com",
            "client_id": "client-id",
            "redirect_url": "https://callback",
            "avatar_server_url": "https://avatars",
            "max_upload_size": 1000,
            "max_snapshot_size": 1000,
            "max_preview_size": 1000,
            "afs_enabled": False,
            "afs_group_id": 0,
        }
    }


@pytest.fixture
def mock_get_app_config():
    """Override global fixture to enable real get_app_config logic."""
    yield


def test_init_fetches_config(mock_config_response):
    """Test that initialization fetches and parses config."""
    with (
        mock.patch("requests.Session.get") as mock_get,
        mock.patch(
            "prusa.connect.client.auth.PrusaConnectCredentials.load_default",
            return_value=mock.Mock(),
        ),
    ):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_config_response

        client = PrusaConnectClient(base_url="https://test.connect")

        assert client.config.auth.backends == ["PRUSA_AUTH"]
        assert client.config.auth.max_upload_size == 1000

        # Verify URL
        mock_get.assert_called_with("https://test.connect/app/config", timeout=consts.DEFAULT_TIMEOUT)


def test_init_config_network_error():
    """Test that network error during config fetch raises PrusaNetworkError."""
    with (
        mock.patch("requests.Session.get", side_effect=requests.ConnectionError("Boom")),
        mock.patch(
            "prusa.connect.client.auth.PrusaConnectCredentials.load_default",
            return_value=mock.Mock(),
        ),
        pytest.raises(exceptions.PrusaNetworkError, match="Failed to fetch app config"),
    ):
        PrusaConnectClient()


def test_init_config_warning_on_missing_auth(mock_config_response):
    """Test that a warning is logged if PRUSA_AUTH is missing."""
    from structlog.testing import capture_logs

    mock_config_response["auth"]["backends"] = ["OTHER_AUTH"]

    with (
        mock.patch("requests.Session.get") as mock_get,
        mock.patch(
            "prusa.connect.client.auth.PrusaConnectCredentials.load_default",
            return_value=mock.Mock(),
        ),
        capture_logs() as cap_logs,
    ):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_config_response

        client = PrusaConnectClient()

        found_warning = False
        for log in cap_logs:
            if log.get("event") == "PRUSA_AUTH not found in supported backends":
                found_warning = True
                assert log.get("backends") == ["OTHER_AUTH"]
                break

        assert found_warning, "Expected warning not found in logs"

    assert client.config.auth.backends == ["OTHER_AUTH"]


def test_lazy_access_error():
    """Test accessing config fails if not initialized (though init forces it now)."""
    # Create client but bypass init via __new__ to simulate uninitialized state
    client = PrusaConnectClient.__new__(PrusaConnectClient)
    client._app_config = None

    with pytest.raises(exceptions.PrusaConnectError, match="App config not initialized"):
        _ = client.config
