"""Authentication utilities for Prusa Connect.

This module mimics the pattern found in `google-auth`.
It provides a Credentials object that can automatically refresh tokens
and attach headers to requests.
"""

import base64
import hashlib
import json
import os
import re
import urllib.parse
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
import structlog
from pydantic import BaseModel, Field, model_validator

from prusa_connect import __version__
from prusa_connect.exceptions import PrusaAuthError

logger = structlog.get_logger()

# Constants
AUTH_URL = "https://account.prusa3d.com/o/authorize/"
TOKEN_URL = "https://account.prusa3d.com/o/token/"
CLIENT_ID = "MRHTlZhZqkNrrQ6FUPtjyusAz8nc59ErHXP8XkS4"
REDIRECT_URI = "https://connect.prusa3d.com/login/auth-callback"



def _decode_jwt(token: str) -> dict[str, Any]:
    """Decodes a JWT token.

    Args:
        token: The JWT token to decode.
    
    Returns:
        A dictionary containing the decoded token.
    """
    # Split the token into header, payload, and signature
    _, payload, _ = token.split(".")

    # Decode the payload, adding padding if necessary
    token_payload_decoded = str(base64.b64decode(payload + "=="), "utf-8")

    # Load the JSON string into a dictionary
    return json.loads(token_payload_decoded)


class PrusaJwtModel(BaseModel):
    """Base model for JWT-based tokens that can parse raw strings."""

    raw_token: str | None = Field(default=None, exclude=True)


    @model_validator(mode="before")
    @classmethod
    def parse_jwt_string(cls, data: Any) -> Any:
        """Parses a raw JWT string into a dictionary of claims."""
        if isinstance(data, str):
            try:
                claims = _decode_jwt(data)
                # Ensure we don't overwrite existing raw_token if somehow present
                if isinstance(claims, dict):
                    claims["raw_token"] = data
                return claims
            except Exception as e:
                raise ValueError(f"Invalid JWT format: {e}") from e
        return data

    def __init__(self, token: str | None = None, /, **data: Any):
        """Allows initializing with a raw JWT string."""
        if token is not None:
            # Re-use the decoding logic or similar.
            # Since validation normally handles decoding for model_validate(str),
            # for __init__ we need to manually prep the dict if we want to support positional args.
            try:
                claims = _decode_jwt(token)
                data.update(claims)
                data["raw_token"] = token
            except Exception:
                # If it fails, we assume it might be intentional or let validation fail later.
                # But typically we want to support the raw string flow.
                pass
        super().__init__(**data)

class PrusaAccessToken(PrusaJwtModel):
    token_id: str = Field(alias="jti")
    user_id: int = Field(alias="sub")
    expires_at: datetime = Field(alias="exp")
    session_id: str = Field(alias="sid")
    app_slug: str = Field(alias="app")
    token_type: str = Field(alias="type")
    connect_id: str

class PrusaRefreshToken(PrusaJwtModel):
    token_id: str = Field(alias="jti")
    user_id: int = Field(alias="sub")
    expires_at: datetime = Field(alias="exp")
    session_id: str = Field(alias="sid")
    app_slug: str = Field(alias="app")
    token_type: str = Field(alias="type")

class PrusaIdentityToken(PrusaJwtModel):
    token_id: str = Field(alias="jti")
    user_id: int = Field(alias="sub")
    expires_at: datetime = Field(alias="exp")
    audience: str = Field(alias="aud")
    user_info: dict[str, Any] = Field(alias="user")
    issuer: str = Field(alias="iss")



class PrusaJWTTokenSet(BaseModel):
    """JWT token data structure."""

    access_token: PrusaAccessToken
    refresh_token: PrusaRefreshToken | None = None
    identity_token: PrusaIdentityToken | None = None

    def dump_tokens(self) -> dict[str, str]:
        """Returns the raw tokens as a dictionary, suitable for saving to disk."""
        data = {}
        if self.access_token and self.access_token.raw_token:
            data["access_token"] = self.access_token.raw_token
        if self.refresh_token and self.refresh_token.raw_token:
            data["refresh_token"] = self.refresh_token.raw_token
        if self.identity_token and self.identity_token.raw_token:
            data["id_token"] = self.identity_token.raw_token
        return data

def _is_token_valid(token: PrusaAccessToken | PrusaRefreshToken | PrusaIdentityToken) -> bool:
    """Checks if the token is valid (will not expire within 30 seconds)."""
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        now = datetime.now()
    else:
        now = datetime.now(UTC)
    logger.debug(
        "Checking token validity",
        token_type=type(token),
        expires_at=expires_at,
        now=now,
        valid=(expires_at - now) > timedelta(seconds=30),
    )
    return (expires_at - now) > timedelta(seconds=30)

class PrusaConnectCredentials:
    """Authentication credentials that allow making authorized API calls.

    This class manages the lifecycle of the access token, including
    automatic refreshing when expired.
    """

    def __init__(self, token_info: dict[str, Any] | PrusaJWTTokenSet, token_saver: Callable[[dict], None] | None = None):
        """Args:
        token_info: Dictionary or PrusaJWTTokenSet containing access_token, etc.
        token_saver: Optional callback executed when tokens are refreshed (to save to disk).
        """
        self._load_tokens(token_info)
        self.token_saver = token_saver
        self._session = requests.Session()  # Session for refresh calls

    def _load_tokens(self, data: dict[str, Any] | PrusaJWTTokenSet) -> None:
        """Parses data into internal state."""
        if isinstance(data, dict):
            # Parse dict into PrusaJWTTokenSet
            self.tokens = PrusaJWTTokenSet(**data)
        else:
            self.tokens = data

    @property
    def valid(self) -> bool:
        """Checks if the current access token is valid (not expired)."""
        if not self.tokens.access_token:
            return False

        return _is_token_valid(self.tokens.access_token)

    def refresh(self) -> None:
        """Forces a token refresh using the refresh token."""
        if not self.tokens.refresh_token or not self.tokens.refresh_token.raw_token:
            raise PrusaAuthError("Cannot refresh token: No refresh token present.")

        if not _is_token_valid(self.tokens.refresh_token):
            raise PrusaAuthError("Cannot refresh token: Refresh token is expired.")

        logger.debug("Refreshing access token...")
        payload = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": self.tokens.refresh_token.raw_token,
        }

        resp = self._session.post(TOKEN_URL, data=payload)

        if resp.status_code == 200:
            new_data = resp.json()
            # We need to update our PrusaJWTTokenSet.
            # The refresh response typically contains a new access_token and optionally a new refresh_token.

            # Use dump_tokens() to get current state as dict of raw strings
            current_raw = self.tokens.dump_tokens()
            # Update with new raw strings from response
            current_raw.update(new_data)

            # Reload from the updated raw dict
            self._load_tokens(current_raw)
            logger.info("Token refreshed successfully.")

            if self.token_saver:
                # pass raw dict back to saver
                self.token_saver(self.tokens.dump_tokens())
        else:
            logger.error("Token refresh failed", status=resp.status_code, body=resp.text)
            raise PrusaAuthError("Failed to refresh token. Re-authentication required.")

    def before_request(self, headers: dict[str, str]) -> None:
        """Injects the Authorization header into the request headers.

        Refreshes the token automatically if needed.
        """
        if not self.valid:
            self.refresh()

        headers["Authorization"] = f"Bearer {self.tokens.access_token.raw_token}"

    @classmethod
    def from_file(cls, path: Path) -> "PrusaConnectCredentials | None":
        """Factory: Load credentials from a JSON file."""
        try:
            logger.debug(f"Loading credentials from {path}")
            with path.open() as f:
                data = json.load(f)

            # Define a saver that updates this specific file
            def save_to_disk(new_data):
                logger.debug(f"Saving credentials to {path}")
                with path.open("w") as f:
                    json.dump(new_data, f, indent=2)

            return cls(data, token_saver=save_to_disk)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info(f"No credentials found at {path.absolute()}")
            return None


# --- PKCE & Login Flow Helpers ---


def _generate_pkce() -> tuple[str, str]:
    """Generates (code_verifier, code_challenge)."""
    verifier = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")
    m = hashlib.sha256()
    m.update(verifier.encode("ascii"))
    challenge = base64.urlsafe_b64encode(m.digest()).decode("utf-8").rstrip("=")
    return verifier, challenge


def interactive_login(email: str, password: str, otp_callback: Callable[[], str]) -> PrusaJWTTokenSet:
    """Performs the full PKCE login flow, including screen scraping and TOTP.

    Args:
        email: Prusa account email.
        password: Prusa account password.
        otp_callback: A function that returns the 6-digit 2FA code if requested.

    Returns:
        A dict containing the token response (access_token, refresh_token, etc).

    Raises:
        PrusaAuthError: If login fails.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": f"PrusaConnectClient/{__version__}"})

    # 1. Setup PKCE
    verifier, challenge = _generate_pkce()

    # 2. Get Login Page
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    }

    logger.info("Initiating login flow...")
    resp = session.get(AUTH_URL, params=params)
    if resp.status_code != 200:
        raise PrusaAuthError(f"Could not load login page (Status: {resp.status_code})")

    csrf = _extract_csrf(resp.text)
    if not csrf:
        raise PrusaAuthError("Could not find CSRF token on login page.")

    # 3. Submit Credentials
    payload = {
        "csrfmiddlewaretoken": csrf,
        "next": _extract_next(resp.text),
        "email": email,
        "password": password,
    }

    headers = {"Referer": resp.url, "Origin": "https://account.prusa3d.com"}
    resp = session.post(resp.url, data=payload, headers=headers)

    # 4. Check for errors or TOTP
    if 'class="invalid-feedback"' in resp.text:
        raise PrusaAuthError("Invalid email or password.")

    if "/login/totp/" in resp.url:
        logger.info("2FA Challenge detected.")
        resp = _handle_totp(session, resp, otp_callback)

    # 5. Handle Callback
    parsed = urllib.parse.urlparse(resp.url)
    if not parsed.path.endswith("/auth-callback"):
        raise PrusaAuthError("Login failed: Did not redirect to auth-callback.")

    query = urllib.parse.parse_qs(parsed.query)
    if "code" not in query:
        raise PrusaAuthError("Login failed: No authorization code in callback.")

    auth_code = query["code"][0]

    # 6. Exchange Code
    token_resp = session.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": auth_code,
            "code_verifier": verifier,
            "redirect_uri": REDIRECT_URI,
        },
    )

    if token_resp.status_code != 200:
        raise PrusaAuthError(f"Token exchange failed: {token_resp.text}")

    return PrusaJWTTokenSet(**token_resp.json())


def _handle_totp(session: requests.Session, resp: requests.Response, otp_callback: Callable) -> requests.Response:
    """Internal helper to handle the TOTP form submission."""
    csrf = _extract_csrf(resp.text)
    otp_code = otp_callback()

    # Find the input name (usually 'otp_token' or generated)
    match = re.search(r'name="([^"]+)"[^>]*autocomplete="one-time-code"', resp.text)
    field_name = match.group(1) if match else "otp_token"

    payload = {
        "csrfmiddlewaretoken": csrf,
        "next": _extract_next(resp.text),
        field_name: otp_code,
    }

    return session.post(resp.url, data=payload, headers={"Referer": resp.url})


def _extract_csrf(html: str) -> str | None:
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    return match.group(1) if match else None


def _extract_next(html: str) -> str:
    match = re.search(r'name="next" value="([^"]+)"', html)
    return urllib.parse.unquote(match.group(1)) if match else ""
