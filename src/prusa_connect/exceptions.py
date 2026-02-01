"""Exceptions for the Prusa Connect library."""


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
