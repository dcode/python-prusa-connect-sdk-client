# Helper to create dummy JWT
import base64
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from prusa_connect.auth import PrusaConnectCredentials, PrusaJWTTokenSet, PrusaRefreshToken


def create_dummy_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.signature"


@pytest.fixture
def mock_tokens():
    future = datetime.now(UTC) + timedelta(hours=1)
    access_payload = {
        "jti": "1",
        "sub": 1,
        "exp": future.timestamp(),
        "sid": "s",
        "app": "a",
        "type": "access",
        "connect_id": "c",
    }
    refresh_payload = {"jti": "2", "sub": 1, "exp": future.timestamp(), "sid": "s", "app": "a", "type": "refresh"}

    return {
        "access_token": create_dummy_jwt(access_payload),
        "refresh_token": create_dummy_jwt(refresh_payload),
    }


def test_credentials_load_from_dict(mock_tokens):
    """Test loading credentials from a dictionary."""
    creds = PrusaConnectCredentials(mock_tokens)
    assert isinstance(creds.tokens, PrusaJWTTokenSet)
    assert creds.tokens.access_token.raw_token == mock_tokens["access_token"]
    assert creds.valid is True


def test_credentials_expired(mock_tokens):
    """Test validity check with expired token."""
    # Create expired token
    past = datetime.now(UTC) - timedelta(hours=1)
    mock_tokens["access_token"] = create_dummy_jwt(
        {"jti": "1", "sub": 1, "exp": past.timestamp(), "sid": "s", "app": "a", "type": "access", "connect_id": "c"}
    )

    creds = PrusaConnectCredentials(mock_tokens)
    assert creds.valid is False


def test_refresh_flow(mock_tokens):
    """Test token refresh flow."""
    creds = PrusaConnectCredentials(mock_tokens)

    # Mock requests.Session.post
    with patch("requests.Session.post") as mock_post:
        # Prepare mock response
        new_future = datetime.now(UTC) + timedelta(hours=2)
        new_access_payload = {
            "jti": "3",
            "sub": 1,
            "exp": new_future.timestamp(),
            "sid": "s",
            "app": "a",
            "type": "access",
            "connect_id": "c",
        }
        new_access_token = create_dummy_jwt(new_access_payload)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": new_access_token}
        mock_post.return_value = mock_response

        # Trigger refresh
        creds.refresh()

        # Verify access token updated
        assert creds.tokens.access_token.raw_token == new_access_token
        # Verify verify refresh token preserved
        assert isinstance(creds.tokens.refresh_token, PrusaRefreshToken)
        assert creds.tokens.refresh_token.raw_token == mock_tokens["refresh_token"]


def test_saver_called_on_refresh(mock_tokens):
    """Test that token_saver is called with new data."""
    saver = MagicMock()
    creds = PrusaConnectCredentials(mock_tokens, token_saver=saver)

    with patch("requests.Session.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": mock_tokens["access_token"]}  # just reuse

        creds.refresh()

    saver.assert_called_once()
    # Check that called with dict
    args = saver.call_args[0][0]
    assert isinstance(args, dict)
    assert "access_token" in args
