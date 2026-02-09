"""Exceptions for the Prusa Connect library.

How to use the most important parts:
- `PrusaConnectError`: Catch this base exception to handle all SDK-related errors.
- `PrusaAuthError`: Catch this for unauthorized or expired credentials.
- `PrusaApiError`: Catch this to inspect detailed API failure responses (like 400 or 500 errors).
"""


class PrusaConnectError(Exception):
    """Base exception for all Prusa Connect library errors."""


class PrusaAuthError(PrusaConnectError):
    """Raised when the API token is invalid or expired (401/403)."""


class PrusaNetworkError(PrusaConnectError):
    """Raised when the API is unreachable (timeouts, DNS issues)."""


class PrusaApiError(PrusaConnectError):
    """Raised when the API returns a 4xx or 5xx error."""

    def __init__(self, message: str, status_code: int, response_body: str) -> None:
        """Initialize the error.

        Args:
            message: Error description.
            status_code: HTTP status code.
            response_body: Raw response body from the server.
        """
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.response_body = response_body


class PrusaCompatibilityError(PrusaConnectError):
    """Raised when the printer supports command set incompatible with this client."""

    def __init__(self, message: str, missing_commands: list[str], report_data: dict) -> None:
        """Initialize exception with details for reporting."""
        super().__init__(message)
        self.missing_commands = missing_commands
        self.report_data = report_data
