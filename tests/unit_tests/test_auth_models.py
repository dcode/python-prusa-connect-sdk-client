import base64
import json
from datetime import UTC, datetime

from prusa.connect.client.auth import PrusaAccessToken, PrusaIdentityToken, PrusaRefreshToken


def create_dummy_jwt(payload: dict) -> str:
    """Helper to create a dummy JWT string (unsigned for testing)."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.signature"


def test_access_token_parsing():
    """Test that PrusaAccessToken parses raw JWT strings correctly."""
    payload = {
        "jti": "unique-id-123",
        "sub": 12345,
        "exp": 1735689600,  # 2025-01-01 00:00:00 UTC
        "sid": "session-abc",
        "app": "prusa-connect",
        "type": "access",
        "connect_id": "team-xyz",
    }
    raw_token = create_dummy_jwt(payload)

    # Instantiate from raw string
    token = PrusaAccessToken.model_validate(raw_token)

    # Check aliases mapped to correct fields
    assert token.token_id == "unique-id-123"
    assert token.user_id == 12345
    assert token.session_id == "session-abc"
    assert token.app_slug == "prusa-connect"
    assert token.token_type == "access"
    assert token.connect_id == "team-xyz"

    # Check raw token is stored
    assert token.raw_token == raw_token

    # Check datetime conversion
    expected_dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert token.expires_at == expected_dt


def test_refresh_token_parsing():
    """Test that PrusaRefreshToken parses correctly from raw string."""
    payload = {
        "jti": "refresh-id-456",
        "sub": 12345,
        "exp": 1735689600,
        "sid": "session-abc",
        "app": "prusa-connect",
        "type": "refresh",
    }
    raw_token = create_dummy_jwt(payload)

    token = PrusaRefreshToken.model_validate(raw_token)

    assert token.token_id == "refresh-id-456"
    assert token.user_id == 12345
    assert token.token_type == "refresh"
    assert isinstance(token.expires_at, datetime)
    assert token.raw_token == raw_token


def test_identity_token_parsing():
    """Test that PrusaIdentityToken parses correctly from raw string."""
    payload = {
        "jti": "id-789",
        "sub": 67890,
        "exp": 1735689600,
        "aud": "some-audience",
        "user": {"name": "Test User", "email": "test@example.com"},
        "iss": "https://prusa3d.com",
    }
    raw_token = create_dummy_jwt(payload)

    token = PrusaIdentityToken.model_validate(raw_token)

    assert token.token_id == "id-789"
    assert token.user_id == 67890
    assert token.audience == "some-audience"
    assert token.issuer == "https://prusa3d.com"
    assert token.user_info == {"name": "Test User", "email": "test@example.com"}
    assert isinstance(token.expires_at, datetime)
    assert token.raw_token == raw_token
