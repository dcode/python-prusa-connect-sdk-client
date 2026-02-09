import base64
import json
import os
from pathlib import Path
from unittest.mock import patch

from prusa.connect.client.auth import PrusaConnectCredentials, get_default_token_path


def create_dummy_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.signature"


def test_get_default_token_path():
    with patch("platformdirs.user_config_dir") as mock_dir:
        mock_dir.return_value = "/tmp/mock/config"
        path = get_default_token_path()
        assert path == Path("/tmp/mock/config/prusa_tokens.json")


def test_secure_file_permissions(tmp_path):
    """Verify that saving tokens sets strict permissions (0o600)."""
    token_file = tmp_path / "tokens.json"
    # Initialize from file with valid data
    valid_payload = {
        "jti": "1",
        "sub": 1,
        "exp": 1234567890,
        "sid": "s",
        "app": "a",
        "type": "access",
        "connect_id": "c",
    }
    valid_token = create_dummy_jwt(valid_payload)
    token_file.write_text(json.dumps({"access_token": valid_token}))

    creds = PrusaConnectCredentials.from_file(token_file)
    assert creds is not None
    assert creds.token_saver is not None

    creds.token_saver({"access_token": valid_token, "new_field": "test"})

    # Check permissions (POSIX only)
    if os.name == "posix":
        mode = token_file.stat().st_mode
        # Check that group/other have no permissions (last 6 bits are 0)
        assert mode & 0o077 == 0
        # Check user read/write (0o600)
        assert mode & 0o600 == 0o600


def test_load_default_priority(tmp_path):
    """Test that environment variables take precedence over file."""
    valid_payload = {
        "jti": "1",
        "sub": 1,
        "exp": 1234567890,
        "sid": "s",
        "app": "a",
        "type": "access",
        "connect_id": "c",
    }
    valid_token = create_dummy_jwt(valid_payload)

    # 1. Mock get_default_token_path to return a non-existent path first
    with patch("prusa.connect.client.auth.get_default_token_path") as mock_path:
        mock_path.return_value = tmp_path / "nonexistent.json"

        # Should be None
        assert PrusaConnectCredentials.load_default() is None

        # 2. Create file
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({"access_token": valid_token}))
        mock_path.return_value = token_file

        # Should load from file
        creds = PrusaConnectCredentials.load_default()
        assert creds is not None
        assert creds.tokens.access_token.raw_token == valid_token

        # 3. Set ENV var
        env_token = create_dummy_jwt({**valid_payload, "jti": "2"})
        with patch.dict(os.environ, {"PRUSA_TOKEN": env_token}):
            creds = PrusaConnectCredentials.load_default()
            assert creds is not None
            assert creds.tokens.access_token.raw_token == env_token
