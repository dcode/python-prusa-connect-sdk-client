"""Prusa Connect REST API Client.

This module provides a high-level interface to interact with the Prusa Connect API,
handling authentication, error parsing, and response validation.
"""

from typing import Any, Protocol

import requests
import structlog

from prusa_connect.exceptions import (
    PrusaApiError,
    PrusaAuthError,
    PrusaNetworkError,
)
from prusa_connect.models import Camera, File, Job, Printer, Team

logger = structlog.get_logger()

DEFAULT_BASE_URL = "https://connect.prusa3d.com/app"
DEFAULT_TIMEOUT = 10.0

__all__ = ["PrusaConnectClient"]


class AuthStrategy(Protocol):
    """Protocol defining how authentication credentials behave."""

    def before_request(self, headers: dict[str, str]) -> None:
        """Inject credentials into the request headers.

        This method is called immediately before every request.
        Implementations can check token expiry and refresh if needed here.
        """
        ...


class PrusaConnectClient:
    """Client for the Prusa Connect API.

    Attributes:
        token: The API Bearer token.
        base_url: The API base URL.
    """

    def __init__(self, credentials: AuthStrategy, base_url: str = DEFAULT_BASE_URL) -> None:
        """Initializes the client.

        Args:
            credentials: An object adhering to the AuthStrategy protocol.
                         (e.g. PrusaConnectCredentials)
            base_url: Optional override for the API endpoint.
        """
        self._base_url = base_url.rstrip("/")
        self._credentials = credentials
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "prusa-connect-python/0.1.0",
                "Accept": "application/json",
            }
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        raw: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> Any:
        """Internal method to handle requests, errors, and logging.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint (e.g., '/printers').
            raw: If True, return the raw response object instead of parsing JSON.
            timeout: Request timeout in seconds.
            **kwargs: Additional arguments passed to requests.request.

        Returns:
            The parsed JSON response, or the Requests Response object if raw=True.

        Raises:
            PrusaAuthError: On 401/403.
            PrusaNetworkError: On connection/timeout issues.
            PrusaApiError: On other non-2xx statuses.
        """
        # We trust the credentials object to do the right thing.
        # The Client doesn't know IF it's a token, a key, or magic.
        self._credentials.before_request(self._session.headers)

        url = f"{self._base_url}/{endpoint.lstrip('/')}"

        try:
            logger.debug("API Request", method=method, url=url)
            response = self._session.request(method, url, timeout=timeout, **kwargs)
            logger.debug(
                "API Response",
                status_code=response.status_code,
                headers=response.headers,
                body_len=len(response.content),
            )

            if response.status_code in (401, 403):
                raise PrusaAuthError("Invalid or expired credentials.")

            if response.status_code >= 400:
                message = f"Request failed: {response.reason}"
                # Attempt to parse detailed error message from JSON response
                try:
                    error_json = response.json()
                    # Common patterns: {"message": "..."}, {"error": "..."}, {"detail": "..."}
                    if isinstance(error_json, dict):
                        for key in ("message", "error", "detail"):
                            if key in error_json and isinstance(error_json[key], str):
                                message = error_json[key]
                                break
                except ValueError:
                    # Not JSON, stick to reason
                    pass

                raise PrusaApiError(
                    message=message,
                    status_code=response.status_code,
                    response_body=response.text[:500],
                )

            if response.status_code == 204:
                return None

            if raw:
                return response

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error("Network error", error=str(e))
            raise PrusaNetworkError(f"Failed to connect to Prusa Connect: {e}") from e

    def get_printers(self) -> list[Printer]:
        """Fetch all printers associated with the account.

        Returns:
            A list of Printer objects.

        Usage Example:
            >>> printers = client.get_printers()
            >>> for printer in printers:
            ...     print(printer.name)
        """
        data = self._request("GET", "/printers")

        # Handle the case where the API returns a wrapper dict {"printers": [...]}
        # or sometimes a raw list depending on the endpoint version/context.
        if isinstance(data, dict) and "printers" in data:
            return [Printer.model_validate(p) for p in data["printers"]]
        elif isinstance(data, list):
            return [Printer.model_validate(p) for p in data]

        logger.warning("Unexpected printer response format", data=data)
        return []

    def get_printer(self, uuid: str) -> Printer:
        """Fetch details for a specific printer.

        Args:
            uuid: The UUID of the printer.

        Returns:
            A Printer object.

        Usage Example:
            >>> printer = client.get_printer("c0ffee-1234")
            >>> print(printer.printer_state)
        """
        data = self._request("GET", f"/printers/{uuid}")
        return Printer.model_validate(data)

    def get_file_list(self, team_id: int) -> list[File]:
        """Fetch files for a specific team.

        Args:
            team_id: The team ID to fetch files for.

        Returns:
            A list of File objects.

        Usage Example:
            >>> files = client.get_file_list(team_id=123)
            >>> for file in files:
            ...     print(file.name)
        """
        # Note: The endpoint might vary based on your reverse engineering.
        # Assuming /teams/{id}/files based on typical Prusa structure or similar.
        data = self._request("GET", f"/teams/{team_id}/files")

        if isinstance(data, dict) and "files" in data:
            return [File.model_validate(f) for f in data["files"]]
        return []

    def get_cameras(self) -> list[Camera]:
        """Fetch all cameras.

        Returns:
            A list of Camera objects.

        Usage Example:
            >>> cameras = client.get_cameras()
            >>> for cam in cameras:
            ...     print(cam.name)
        """
        data = self._request("GET", "/cameras")
        if isinstance(data, dict) and "cameras" in data:
            return [Camera.model_validate(c) for c in data["cameras"]]
        return []

    def get_teams(self) -> list[Team]:
        """Fetch all teams the user belongs to.

        Returns:
            A list of Team objects.

        Usage Example:
            >>> teams = client.get_teams()
            >>> for team in teams:
            ...     print(team.name)
        """
        data = self._request("GET", "/users/teams")
        if isinstance(data, dict) and "teams" in data:
            return [Team.model_validate(t) for t in data["teams"]]
        return []

    def get_team_jobs(self, team_id: int) -> list[Job]:
        """Fetch job history for a team.

        Args:
            team_id: The team ID.

        Returns:
            A list of Job objects.

        Usage Example:
            >>> jobs = client.get_team_jobs(team_id=123)
            >>> for job in jobs:
            ...     print(job.state)
        """
        data = self._request("GET", f"/teams/{team_id}/jobs")
        if isinstance(data, dict) and "jobs" in data:
            return [Job.model_validate(j) for j in data["jobs"]]
        return []

    def get_printer_jobs(self, printer_uuid: str) -> list[Job]:
        """Fetch job history for a printer.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            A list of Job objects.

        Usage Example:
            >>> jobs = client.get_printer_jobs("c0ffee-1234")
            >>> for job in jobs:
            ...     print(job.progress)
        """
        data = self._request("GET", f"/printers/{printer_uuid}/jobs")
        if isinstance(data, dict) and "jobs" in data:
            return [Job.model_validate(j) for j in data["jobs"]]
        return []

    def send_command(self, printer_uuid: str, command: str, kwargs: dict | None = None) -> bool:
        """Send a command to a printer.

        Args:
            printer_uuid: The printer UUID.
            command: The command string (e.g., 'PAUSE_PRINT', 'MOVE_Z').
            kwargs: Optional arguments for the command.

        Returns:
            True if successful.

        Usage Example:
            >>> success = client.send_command("c0ffee-1234", "PAUSE_PRINT")
        """
        payload = {"command": command}
        if kwargs:
            payload["kwargs"] = kwargs

        # discovery says /commands/sync is definitive
        self._request("POST", f"/printers/{printer_uuid}/commands/sync", json=payload)
        return True

    def get_snapshot(self, camera_id: str) -> bytes:
        """Fetch a snapshot from a camera.

        Args:
            camera_id: The numeric camera ID.

        Returns:
            The binary image data.

        Usage Example:
            >>> image_data = client.get_snapshot("camera_1")
            >>> with open("snap.jpg", "wb") as f:
            ...     f.write(image_data)
        """
        # Raw response for binary data
        response = self._request("GET", f"/cameras/{camera_id}/snapshots/last", raw=True)
        return response.content

    def trigger_snapshot(self, camera_token: str) -> bool:
        """Trigger a new snapshot locally on the camera/server.

        Args:
            camera_token: The camera token (alphanumeric).

        Returns:
            True if triggered.

        Usage Example:
            >>> client.trigger_snapshot("token_abc_123")
        """
        self._request("POST", f"/cameras/{camera_token}/snapshots")
        return True
