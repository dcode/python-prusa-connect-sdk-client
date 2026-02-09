"""Authentication utilities for Prusa Connect.

This module mimics the pattern found in `google-auth`.
It provides a Credentials object that can automatically refresh tokens
and attach headers to requests.

How to use the most important parts:
- `PrusaConnectCredentials`: The main credentials object for interacting with the SDK. Pass this to
  `PrusaConnectClient(credentials=...)`.
- `interactive_login`: A helper function to kick off an interactive OAuth2 flow, returning a JSON serializable dict
  with access and refresh tokens.
- `get_default_token_path`: Helper to determine the standard configuration path to persist tokens locally.
"""

from __future__ import annotations

import base64
import collections.abc  # noqa: TC003
import contextlib
import datetime
import hashlib
import json
import os
import re
import typing
import urllib.parse
from pathlib import Path

import platformdirs
import pydantic
import requests
import structlog

from prusa.connect.client import __version__, consts, exceptions

logger = structlog.get_logger()


def _decode_jwt(token: str) -> dict[str, typing.Any]:
    """Simple decode of a JWT token.

    This is explicitly NOT intended to validate the token,
    but rather to parse the claims into a dictionary.

    Args:
        token: The JWT token to decode.

    Returns:
        A dictionary containing the decoded token.
    """
    # Split the token into header, payload, and signature
    header, payload, signature = token.split(".")

    logger.debug(f"Token header: {base64.b64decode(header + '==').decode('utf-8')}")
    logger.debug(f"Token payload: {base64.b64decode(payload + '==').decode('utf-8')}")
    logger.debug(f"Token signature: {signature}")

    # Decode the payload, adding padding if necessary
    token_payload_decoded = str(base64.b64decode(payload + "=="), "utf-8")

    # Load the JSON string into a dictionary
    return json.loads(token_payload_decoded)


class PrusaJwtModel(pydantic.BaseModel):
    """Base model for JWT-based tokens that can parse raw strings."""

    raw_token: str | None = pydantic.Field(default=None, exclude=True)

    @pydantic.model_validator(mode="before")
    @classmethod
    def parse_jwt_string(cls, data: typing.Any) -> typing.Any:
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

    def __init__(self, token: str | None = None, /, **data: typing.Any):
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
    """Structure of the Access Token."""

    token_id: str = pydantic.Field(alias="jti")
    user_id: int = pydantic.Field(alias="sub")
    expires_at: datetime.datetime = pydantic.Field(alias="exp")
    session_id: str = pydantic.Field(alias="sid")
    app_slug: str = pydantic.Field(alias="app")
    token_type: str = pydantic.Field(alias="type")
    connect_id: str


class PrusaRefreshToken(PrusaJwtModel):
    """Structure of the Refresh Token."""

    token_id: str = pydantic.Field(alias="jti")
    user_id: int = pydantic.Field(alias="sub")
    expires_at: datetime.datetime = pydantic.Field(alias="exp")
    session_id: str = pydantic.Field(alias="sid")
    app_slug: str = pydantic.Field(alias="app")
    token_type: str = pydantic.Field(alias="type")


class PrusaIdentityToken(PrusaJwtModel):
    """Structure of the Identity Token."""

    token_id: str = pydantic.Field(alias="jti")
    user_id: int = pydantic.Field(alias="sub")
    expires_at: datetime.datetime = pydantic.Field(alias="exp")
    audience: str = pydantic.Field(alias="aud")
    user_info: dict[str, typing.Any] = pydantic.Field(alias="user")
    issuer: str = pydantic.Field(alias="iss")


class PrusaJWTTokenSet(pydantic.BaseModel):
    """JWT token data structure."""

    access_token: PrusaAccessToken
    refresh_token: PrusaRefreshToken | None = None
    identity_token: typing.Annotated[PrusaIdentityToken | None, pydantic.Field(alias="id_token")] = None
    expires_in: int | None = None
    token_type: str | None = None
    scope: typing.Annotated[
        list[str],
        pydantic.Field(default_factory=list),
        pydantic.BeforeValidator(lambda v: v.split() if isinstance(v, str) else v),
    ]
    shared_session_key: str | None = None

    def dump_tokens(self) -> dict[str, typing.Any]:
        """Returns the raw tokens as a dictionary, suitable for saving to disk."""
        data: dict[str, typing.Any] = {}
        if self.access_token and self.access_token.raw_token:
            data["access_token"] = self.access_token.raw_token
        if self.refresh_token and self.refresh_token.raw_token:
            data["refresh_token"] = self.refresh_token.raw_token
        if self.identity_token and self.identity_token.raw_token:
            data["id_token"] = self.identity_token.raw_token
        if self.expires_in is not None:
            data["expires_in"] = self.expires_in
        if self.token_type is not None:
            data["token_type"] = self.token_type
        if self.scope:
            data["scope"] = " ".join(self.scope)
        if self.shared_session_key is not None:
            data["shared_session_key"] = self.shared_session_key
        return data


def _is_token_valid(token: PrusaAccessToken | PrusaRefreshToken | PrusaIdentityToken) -> bool:
    """Checks if the token is valid (will not expire within 30 seconds)."""
    expires_at = token.expires_at
    now = datetime.datetime.now() if expires_at.tzinfo is None else datetime.datetime.now(datetime.UTC)
    logger.debug(
        "Checking token validity",
        token_type=type(token),
        expires_at=expires_at,
        now=now,
        valid=(expires_at - now) > datetime.timedelta(seconds=30),
    )
    return (expires_at - now) > datetime.timedelta(seconds=30)


def get_default_token_path() -> Path:
    """Returns the platform-specific path for the token file using platformdirs."""
    config_dir = Path(platformdirs.user_config_dir(consts.APP_NAME, consts.APP_AUTHOR))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "prusa_tokens.json"


class PrusaConnectCredentials:
    """Authentication credentials that allow making authorized API calls.

    This class manages the lifecycle of the access token, including
    automatic refreshing when expired.
    """

    def __init__(
        self,
        token_info: dict[str, typing.Any] | PrusaJWTTokenSet,
        token_saver: collections.abc.Callable[[dict], None] | None = None,
    ):
        """Initialize credentials.

        Args:
            token_info: Dictionary or PrusaJWTTokenSet containing access_token, etc.
            token_saver: Optional callback executed when tokens are refreshed (to save to disk).
        """
        self._load_tokens(token_info)
        self.token_saver = token_saver
        self._session = requests.Session()  # Session for refresh calls

    def _load_tokens(self, data: dict[str, typing.Any] | PrusaJWTTokenSet) -> None:
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
            raise exceptions.PrusaAuthError("Cannot refresh token: No refresh token present.")

        if not _is_token_valid(self.tokens.refresh_token):
            logger.error("Refresh token expired", expires_at=self.tokens.refresh_token.expires_at)
            raise exceptions.PrusaAuthError("Cannot refresh token: Refresh token is expired.")

        logger.debug("Refreshing access token...", refresh_token_id=self.tokens.refresh_token.token_id)
        payload = {
            "grant_type": "refresh_token",
            "client_id": consts.CLIENT_ID,
            "refresh_token": self.tokens.refresh_token.raw_token,
        }

        resp = self._session.post(consts.TOKEN_URL, data=payload)

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
            raise exceptions.PrusaAuthError("Failed to refresh token. Re-authentication required.")

    def before_request(self, headers: collections.abc.MutableMapping[str, str | bytes]) -> None:
        """Injects the Authorization header into the request headers.

        Refreshes the token automatically if needed.
        """
        if not self.valid:
            self.refresh()

        headers["Authorization"] = f"Bearer {self.tokens.access_token.raw_token}"

    @classmethod
    def from_file(cls, path: Path | str) -> PrusaConnectCredentials | None:
        """Factory: Load credentials from a JSON file."""
        if isinstance(path, str):
            path = Path(path)

        try:
            logger.debug(f"Loading credentials from file: {path}")
            with path.open() as f:
                data = json.load(f)

            # Define a saver that updates this specific file
            def save_to_disk(new_data):
                logger.debug(f"Saving credentials to file: {path}")
                # Ensure directory exists (in case it was deleted)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w") as f:
                    json.dump(new_data, f, indent=2)

                # Best-effort secure permissions
                with contextlib.suppress(OSError):
                    os.chmod(path, 0o600)

            return cls(data, token_saver=save_to_disk)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.debug(f"No credentials found at file: {path.absolute()}")
            return None

    @classmethod
    def from_env(cls) -> PrusaConnectCredentials | None:
        """Factory: Load credentials from environment variables.

        Checks:
        1. PRUSA_TOKENS_JSON: A JSON string containing the full token set.
        2. PRUSA_TOKEN: A raw Access Token (JWT).
        """
        if json_str := os.environ.get("PRUSA_TOKENS_JSON"):
            logger.debug("Loading credentials from env: PRUSA_TOKENS_JSON")
            try:
                return cls(json.loads(json_str))
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in PRUSA_TOKENS_JSON")

        if token := os.environ.get("PRUSA_TOKEN"):
            logger.debug("Loading credentials from env: PRUSA_TOKEN")
            try:
                # Pydantic will attempt to parse the string into the AccessToken model
                return cls({"access_token": token})
            except Exception as e:
                logger.debug(f"Could not create credentials from PRUSA_TOKEN: {e}")

        return None

    @classmethod
    def load_default(cls) -> PrusaConnectCredentials | None:
        """Factory: Attempt to load credentials from default locations.

        Priority:
        1. Environment Variables (PRUSA_TOKENS_JSON, PRUSA_TOKEN)
        2. Platform default config file
        """
        # 1. Environment
        if creds := cls.from_env():
            return creds

        # 2. Platform default file
        default_path = get_default_token_path()
        logger.debug("Checking for credentials at default path", path=default_path)
        if default_path.exists():
            return cls.from_file(default_path)

        return None


# --- PKCE & Login Flow Helpers ---


def _generate_pkce() -> tuple[str, str]:
    """Generates (code_verifier, code_challenge)."""
    verifier = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")
    m = hashlib.sha256()
    m.update(verifier.encode("ascii"))
    challenge = base64.urlsafe_b64encode(m.digest()).decode("utf-8").rstrip("=")
    return verifier, challenge


def interactive_login(email: str, password: str, otp_callback: collections.abc.Callable[[], str]) -> PrusaJWTTokenSet:
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
        "client_id": consts.CLIENT_ID,
        "redirect_uri": consts.REDIRECT_URI,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    }

    logger.info("Initiating login flow...")
    logger.debug("Login params", url=consts.AUTH_URL, params=params)
    resp = session.get(consts.AUTH_URL, params=params)
    if resp.status_code != 200:
        raise exceptions.PrusaAuthError(f"Could not load login page (Status: {resp.status_code})")

    csrf = _extract_csrf(resp.text)
    if not csrf:
        logger.error("CSRF token missing from login page")
        raise exceptions.PrusaAuthError("Could not find CSRF token on login page.")

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
        raise exceptions.PrusaAuthError("Invalid email or password.")

    if "/login/totp/" in resp.url:
        logger.info("2FA Challenge detected.")
        resp = _handle_totp(session, resp, otp_callback)

    # 5. Handle Callback
    parsed = urllib.parse.urlparse(resp.url)
    if not parsed.path.endswith("/auth-callback"):
        raise exceptions.PrusaAuthError("Login failed: Did not redirect to auth-callback.")

    query = urllib.parse.parse_qs(parsed.query)
    if "code" not in query:
        raise exceptions.PrusaAuthError("Login failed: No authorization code in callback.")

    auth_code = query["code"][0]

    # 6. Exchange Code
    token_resp = session.post(
        consts.TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": consts.CLIENT_ID,
            "code": auth_code,
            "code_verifier": verifier,
            "redirect_uri": consts.REDIRECT_URI,
        },
    )

    if token_resp.status_code != 200:
        raise exceptions.PrusaAuthError(f"Token exchange failed: {token_resp.text}")

    logger.info("Token exchange successful.", user_id=token_resp.json().get("sub"))
    logger.debug("Token response", json=token_resp.json())

    return PrusaJWTTokenSet(**token_resp.json())


def _handle_totp(
    session: requests.Session, resp: requests.Response, otp_callback: collections.abc.Callable
) -> requests.Response:
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
