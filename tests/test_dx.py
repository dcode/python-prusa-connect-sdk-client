import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from prusa_connect.auth import PrusaConnectCredentials
from prusa_connect.client import PrusaConnectClient
from prusa_connect.exceptions import PrusaAuthError


# Helper to encode base64url without padding
def b64url(data):
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


def make_dummy_jwt(payload):
    return f"{b64url({})}.{b64url(payload)}.sig"


def test_credentials_load_default_env_json(monkeypatch):
    """Test loading credentials from PRUSA_TOKENS_JSON."""
    payload = {
        "jti": "1",
        "sub": 1,
        "exp": 9999999999,
        "sid": "s",
        "app": "a",
        "type": "access",
        "connect_id": "c",
    }
    jwt_token = make_dummy_jwt(payload)

    data = {
        "access_token": jwt_token,
        "jti": "1",
        "sub": 123,
        "exp": 9999999999,
        "sid": "session",
        "app": "app",
        "type": "access",
        "connect_id": "cid",
    }
    monkeypatch.setenv("PRUSA_TOKENS_JSON", json.dumps(data))

    # Ensure we don't pick up the file
    with patch("pathlib.Path.exists", return_value=False):
        creds = PrusaConnectCredentials.load_default()
        assert creds is not None
        assert creds.tokens.access_token.raw_token == jwt_token


def test_credentials_load_default_env_token(monkeypatch):
    """Test loading credentials from PRUSA_TOKEN (raw JWT)."""
    # Create a dummy payload that matches PrusaAccessToken fields
    payload = {
        "jti": "1",
        "sub": 1,
        "exp": 9999999999,
        "sid": "s",
        "app": "a",
        "type": "access",
        "connect_id": "c",
    }

    dummy_jwt = make_dummy_jwt(payload)

    monkeypatch.setenv("PRUSA_TOKEN", dummy_jwt)

    with patch("pathlib.Path.exists", return_value=False):
        creds = PrusaConnectCredentials.load_default()
        assert creds is not None
        assert creds.tokens.access_token.raw_token == dummy_jwt


def test_credentials_load_default_file():
    """Test loading credentials from prusa_tokens.json."""
    payload = {
        "jti": "1",
        "sub": 1,
        "exp": 9999999999,
        "sid": "s",
        "app": "a",
        "type": "access",
        "connect_id": "c",
    }
    jwt_token = make_dummy_jwt(payload)

    data = {
        "access_token": jwt_token,
        "jti": "1",
        "sub": 123,
        "exp": 9999999999,
        "sid": "session",
        "app": "app",
        "type": "access",
        "connect_id": "cid",
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.open", new_callable=MagicMock),
        patch("json.load", return_value=data),
    ):
        creds = PrusaConnectCredentials.load_default()
        assert creds is not None
        assert creds.tokens.access_token.raw_token == jwt_token


def test_client_init_no_creds_raises():
    """Test that Client raises PrusaAuthError if no creds found."""
    with patch("prusa_connect.auth.PrusaConnectCredentials.load_default", return_value=None):
        with pytest.raises(PrusaAuthError) as exc:
            PrusaConnectClient()
        assert "No credentials provided" in str(exc.value)


def test_client_init_auto_load():
    """Test that Client automatically loads default credentials."""
    mock_creds = MagicMock()
    with patch(
        "prusa_connect.auth.PrusaConnectCredentials.load_default", return_value=mock_creds
    ):
        client = PrusaConnectClient()
        assert client._credentials == mock_creds
