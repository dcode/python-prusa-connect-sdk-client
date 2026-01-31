import base64
import hashlib
import json
import os
import re
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple

import requests
import structlog

from .config import settings

logger = structlog.get_logger()

AUTH_URL = "https://account.prusa3d.com/o/authorize/"
TOKEN_URL = "https://account.prusa3d.com/o/token/"
CLIENT_ID = "MRHTlZhZqkNrrQ6FUPtjyusAz8nc59ErHXP8XkS4"
REDIRECT_URI = "https://connect.prusa3d.com/login/auth-callback"


def generate_pkce_pair() -> Tuple[str, str]:
    """Generates a code_verifier and code_challenge for PKCE."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")
    m = hashlib.sha256()
    m.update(code_verifier.encode("ascii"))
    code_challenge = base64.urlsafe_b64encode(m.digest()).decode("utf-8").rstrip("=")
    return code_verifier, code_challenge


def login_and_get_token(email: str, password: str) -> Optional[Dict[str, Any]]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )

    # 1. Generate PKCE
    code_verifier, code_challenge = generate_pkce_pair()
    logger.debug("Generated PKCE", code_verifier=code_verifier[:10] + "...")

    # 2. Initiate Authorization Request
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
    }

    logger.info("Fetching login page...", url=AUTH_URL)
    resp = session.get(AUTH_URL, params=params)
    if resp.status_code != 200:
        logger.error("Failed to load login page", status_code=resp.status_code)
        return None

    # 3. Extract CSRF Token
    csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.text)
    if not csrf_match:
        logger.error("Could not find csrfmiddlewaretoken in login page")
        return None
    csrf_token = csrf_match.group(1)

    post_url = resp.url

    # 4. Post Credentials
    next_val_match = re.search(r'name="next" value="([^"]+)"', resp.text)
    next_val = urllib.parse.unquote(next_val_match.group(1)) if next_val_match else ""

    payload = {
        "csrfmiddlewaretoken": csrf_token,
        "next": next_val,
        "email": email,
        "password": password,
    }

    headers = {
        "Referer": post_url,
        "Origin": "https://account.prusa3d.com",
    }

    resp = session.post(post_url, data=payload, headers=headers, allow_redirects=True)

    if "Log in to your Prusa Account" in resp.text and "id_password" in resp.text:
        error_msg = "Login failed"
        error_match = re.search(r'class="invalid-feedback">\s*(.*?)\s*<', resp.text, re.DOTALL)
        if error_match:
            error_msg = error_match.group(1).strip()
        logger.error("Login failed", reason=error_msg)
        return None

    # 4.5. Handle TOTP
    if "/login/totp/" in resp.url:
        logger.info("TOTP Challenge detected", url=resp.url)
        totp_url = resp.url

        csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', resp.text)
        if csrf_match:
            try:
                csrf_token = csrf_match.group(1)
            except IndexError:
                pass

        otp_field_match = re.search(
            r'<input[^>]*name="([^"]+)"[^>]*((type="text")|(type="number")|(autocomplete="one-time-code"))',
            resp.text,
        )
        otp_field_name = otp_field_match.group(1) if otp_field_match else "otp_token"

        # Use python input for now - might need to handling CLI logic separation if strict
        # Ideally auth logic shouldn't do I/O, but for this simplified flow it's okay.
        # Alternatively, callback or injection.
        # I'll keep input() here for now as preserving behavior is key.
        print("Enter 2FA/TOTP Code: ", end="", flush=True)
        otp_code = input().strip()  # Use raw input

        next_val_match = re.search(r'name="next" value="([^"]+)"', resp.text)
        next_val = urllib.parse.unquote(next_val_match.group(1)) if next_val_match else ""

        totp_payload = {
            "csrfmiddlewaretoken": csrf_token,
            "next": next_val,
            otp_field_name: otp_code,
        }

        headers["Referer"] = totp_url
        logger.info("Posting TOTP", url=totp_url)

        resp = session.post(totp_url, data=totp_payload, headers=headers, allow_redirects=True)

        if "/login/totp/" in resp.url:
            logger.error("TOTP failed (still on TOTP page)")
            return None

    # 5. Capture Authorization Code
    logger.info("Final URL after login", url=resp.url)

    parsed_url = urllib.parse.urlparse(resp.url)
    if not parsed_url.path.endswith("/auth-callback"):
        logger.error("Did not end up at auth-callback", current_url=resp.url)
        return None

    query_params = urllib.parse.parse_qs(parsed_url.query)
    if "code" not in query_params:
        logger.error("No authorization code found in callback URL")
        return None

    auth_code = query_params["code"][0]
    logger.debug("Code captured", code=auth_code[:10] + "...")

    # 6. Exchange Code for Token
    logger.info("Exchanging code for token", url=TOKEN_URL)
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": auth_code,
        "code_verifier": code_verifier,
        "redirect_uri": REDIRECT_URI,
    }

    resp = session.post(TOKEN_URL, data=token_payload)

    if resp.status_code == 200:
        logger.debug("Token exchange response", response=resp.json())
        return resp.json()
    else:
        logger.error("Token exchange failed", response=resp.text)
        return None


def refresh_access_token(refresh_token_str: str) -> Optional[Dict[str, Any]]:
    logger.info("Attempting to refresh access token...")
    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": refresh_token_str,
    }

    try:
        resp = requests.post(TOKEN_URL, data=payload)
        if resp.status_code == 200:
            logger.info("Token refresh successful")
            return resp.json()
        else:
            logger.error("Token refresh failed", response=resp.text)
            return None
    except Exception as e:
        logger.error("Token refresh error", error=str(e))
        return None


def is_token_expired(token_data: Dict[str, Any]) -> bool:
    if "expires_at" in token_data:
        return time.time() > (token_data["expires_at"] - 30)

    access_token = token_data.get("access_token")
    if not access_token:
        return True

    try:
        parts = access_token.split(".")
        if len(parts) == 3:
            payload = parts[1]
            payload += "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            claims = json.loads(decoded)
            exp = claims.get("exp")
            if exp:
                return time.time() > (exp - 30)
    except Exception as e:
        logger.warning("Failed to check token expiry", error=str(e))

    return False


def save_tokens(token_data: Dict[str, Any], filename: str = str(settings.tokens_file)):
    if "expires_in" in token_data and "expires_at" not in token_data:
        token_data["expires_at"] = time.time() + token_data["expires_in"]

    try:
        with open(filename, "w") as f:
            json.dump(token_data, f, indent=2)
        logger.info("Tokens saved", filename=filename)
    except IOError as e:
        logger.error("Failed to save tokens", error=str(e))


def load_tokens(filename: str = str(settings.tokens_file)) -> Optional[Dict[str, Any]]:
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
