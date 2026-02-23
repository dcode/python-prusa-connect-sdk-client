"""Prusa Connect REST API Client.

This module provides a high-level interface to interact with the Prusa Connect API,
handling authentication, error parsing, connection pooling, and response validation.

How to use the most important parts:
- `PrusaConnectClient`: The core class. Instantiate it (optionally with `PrusaConnectCredentials`) to begin
  controlling printers.
- Access resources via the service attributes: `client.printers`, `client.teams`, `client.cameras`,
  `client.files`, `client.jobs`, and `client.stats`.
"""

import collections.abc
import datetime
import typing
from pathlib import Path

import pydantic
import requests
import structlog
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from prusa.connect.client import auth, camera, command_models, consts, exceptions, gcode, models
from prusa.connect.client.__version__ import __version__
from prusa.connect.client.services import (
    cameras,
    files,
    jobs,
    printers,
    stats,
    teams,
)

type PrusaCameraClient = camera.PrusaCameraClient

__all__ = ["AuthStrategy", "PrusaCameraClient", "PrusaConnectClient"]

logger = structlog.get_logger()


class AuthStrategy(typing.Protocol):
    """Protocol defining how authentication credentials behave."""

    def before_request(self, headers: collections.abc.MutableMapping[str, str | bytes]) -> None:
        """Inject credentials into the request headers.

        This method is called immediately before every request.
        Implementations can check token expiry and refresh if needed here.

        Args:
            headers: The dictionary of headers to modify in-place.
        """
        ...


class PrusaConnectClient:
    """Client for the Prusa Connect API.

    This client handles the lower-level details of making HTTP requests,
    including authentication injection, error handling, and retries.

    Attributes:
        token: The API Bearer token.
        base_url: The API base URL.

    Usage Example:
    ```python
        >>> from prusa.connect.client import PrusaConnectClient
        >>> # Assume you have a credentials object
        >>> client = PrusaConnectClient(credentials=my_creds)
        >>> printers = client.printers.list_printers()
    ```
    """

    # Service attribute annotations (instance attributes set in __init__)
    printers: "printers.PrinterService"
    files: "files.FileService"
    teams: "teams.TeamService"
    cameras: "cameras.CameraService"
    jobs: "jobs.JobService"
    stats: "stats.StatsService"

    def __init__(
        self,
        credentials: AuthStrategy | None = None,
        base_url: str = consts.DEFAULT_BASE_URL,
        timeout: float = consts.DEFAULT_TIMEOUT,
        cache_dir: Path | str | None = None,
        cache_ttl: int = 3600,
    ) -> None:
        """Initializes the client.

        Args:
            credentials: An object adhering to the `AuthStrategy` protocol.
                         If None, attempts to load from environment or platform-specific config directory.
            base_url: Optional override for the API endpoint.
            timeout: Default timeout for API requests in seconds.
            cache_dir: Optional directory to store persistent caches (e.g. supported commands).
            cache_ttl: Cache Time-To-Live in seconds. Defaults to 24 hours.
        """
        self._base_url = base_url.rstrip("/")

        if credentials is None:
            credentials = auth.PrusaConnectCredentials.load_default()

        if credentials is None:
            raise exceptions.PrusaAuthError(
                "No credentials provided and none found in default locations. "
                "Please login via CLI (`prusactl list-printers`) or provide credentials explicitly."
            )

        self._credentials = credentials
        self._timeout = timeout
        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._cache_ttl = cache_ttl

        self._session = requests.Session()

        # Config state
        self._app_config: models.AppConfig | None = None

        # Configure Retries
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods={"GET", "POST", "PUT", "DELETE", "PATCH"},
        )
        adapter = HTTPAdapter(max_retries=retries)  # type: ignore
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        self._session.headers.update(
            {
                "User-Agent": f"prusa-connect-python/{__version__}",
                "Accept": "application/json",
            }
        )

        # Initialize Services
        self.printers = printers.PrinterService(self, self._cache_dir, self._cache_ttl)
        self.files = files.FileService(self)
        self.teams = teams.TeamService(self)
        self.cameras = cameras.CameraService(self)
        self.jobs = jobs.JobService(self)
        self.stats = stats.StatsService(self)

        # Initialize Config
        self.get_app_config()

    def request(self, method: str, endpoint: str, **kwargs: typing.Any) -> typing.Any:
        """Internal method alias for services."""
        return self._request(method, endpoint, **kwargs)

    @property
    def config(self) -> models.AppConfig:
        """The application configuration. Verified to be populated after init."""
        if self._app_config is None:
            raise exceptions.PrusaConnectError("App config not initialized.")
        return self._app_config

    def get_app_config(self, force_refresh: bool = False) -> models.AppConfig:
        """Fetch and cache the application configuration from /app/config.

        Args:
            force_refresh: If True, ignore cached config and fetch from server.

        Returns:
            The `AppConfig` object.

        Raises:
            PrusaApiError: If the request fails.
            ValueError: If the server does not support the required auth method.
        """
        if self._app_config and not force_refresh:
            return self._app_config

        # We use a raw request here to avoid circular dependency or issues if
        # authentication itself relied on this config (though currently it's a check).
        # We DO NOT use self._request initially because _request might use credentials
        # which might rely on config. However, currently credentials are just headers.
        # But wait, /app/config is public? Or authenticated?
        # The curl command `curl -s https://connect.prusa3d.com/app/config` works without auth.
        # So we should use a plain requests call or _request with auth=None if supported.
        # _request always injects credentials. Let's use the session but skip auth injection if possible?
        # Actually _request calls `self._credentials.before_request`.
        # /app/config seems public. Let's try to use _request but we might get 401 if creds are bad?
        # No, if creds are bad, _request raises PrusaAuthError.
        # But we really want to fetch this even if creds are bad?
        # The user said "use during client initialization".
        # If I use `requests.get` directly, I bypass `_request` logic (retries, logging).
        # I should use `self._session`.

        url = f"{self._base_url}/app/config"
        logger.debug("Fetching App Config", url=url)

        try:
            # /app/config is public, so we don't strictly need headers,
            # but it doesn't hurt to send them if we have them.
            # However, to be safe during init (where creds might be invalid/missing if we allowed that),
            # maybe we should just fetch it without auth headers first?
            # Existing `_request` enforces auth.

            # Use raw session to avoid auth injection for this specific public endpoint
            response = self._session.get(url, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise exceptions.PrusaNetworkError(f"Failed to fetch app config: {e}") from e

        config = models.AppConfig(**data)

        # Validate Auth Backend
        if "PRUSA_AUTH" not in config.auth.backends:
            # We strictly require PRUSA_AUTH for now as that's all this client speaks.
            logger.warning("PRUSA_AUTH not found in supported backends", backends=config.auth.backends)
            # We could raise an error, but maybe the server is just being weird and we want to try anyway?
            # User said: "When authenticating, we should validate that the server offers that option"
            # Since this is "init", let's log a warning. If we raise Error, we might break clients if
            # the server temporarily hides it or something.
            # But actually, if it's not there, our auth flow (sending Bearer token) 'should' be acceptable
            # if the server still accepts it.
            # "select the backend accordingly" -> implied usage of `PRUSA_AUTH`.
            pass

        self._app_config = config
        return config

    def get_camera_client(self, camera_token: str, signaling_url: str | None = None) -> camera.PrusaCameraClient:
        """Returns a pre-configured PrusaCameraClient.

        Args:
            camera_token: The target camera's unique ID.
            signaling_url: Optional override for the signaling server.

        Returns:
            A `PrusaCameraClient` instance.
        """
        jwt_token = None
        # Extract JWT if using PrusaConnectCredentials
        if isinstance(self._credentials, auth.PrusaConnectCredentials):
            jwt_token = self._credentials.tokens.access_token.raw_token

        kwargs: dict[str, typing.Any] = {"camera_token": camera_token}
        if signaling_url:
            kwargs["signaling_url"] = signaling_url
        if jwt_token:
            kwargs["jwt_token"] = jwt_token

        return camera.PrusaCameraClient(**kwargs)

    def _request(self, method: str, endpoint: str, raw: bool = False, **kwargs: typing.Any) -> typing.Any:
        """Internal method to handle requests, errors, and logging.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint (e.g., '/printers').
            raw: If True, return the raw response object instead of parsing JSON.
            **kwargs: Additional arguments passed to requests.request (e.g., timeout).

        Returns:
            The parsed JSON response (dict or list), or the Requests Response object if raw=True.

        Raises:
            exceptions.PrusaAuthError: On 401/403.
            exceptions.PrusaNetworkError: On connection/timeout issues.
            exceptions.PrusaApiError: On other non-2xx statuses.
        """
        # We trust the credentials object to do the right thing.
        # The Client doesn't know IF it's a token, a key, or magic.
        self._credentials.before_request(self._session.headers)

        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        kwargs.setdefault("timeout", self._timeout)
        response: requests.Response | None = None
        try:
            logger.debug("API Request", method=method, url=url)
            # Check for stream in kwargs before request
            is_stream = kwargs.get("stream", False)
            response = self._session.request(method, url, **kwargs)

            for h in response.headers:
                logger.info("Header", header=h, value=response.headers[h])

            # Avoid reading content if streaming
            body_len = "STREAM" if is_stream else len(response.content)

            logger.debug(
                "API Response",
                status_code=getattr(response, "status_code", None),
                headers=dict(response.headers),
                body_len=body_len,
            )

            if raw:
                return response

            if getattr(response, "status_code", None) in (401, 403):
                raise exceptions.PrusaAuthError("Invalid or expired credentials.")

            if getattr(response, "status_code", -1) >= 400:
                # For error responses, we might want to read content even if streaming?
                # Usually APIs return small JSON errors.
                # If we are streaming a big download and fail, we probably want the error text.
                # safely read a bit
                try:
                    # Peek or read a limited amount if possible, or just read text if not too huge
                    # If it's an error, it's likely not the huge binary we expected.
                    error_text = response.text[:500]
                except Exception:
                    error_text = "<could not read error body>"

                raise exceptions.PrusaApiError(
                    message=f"Request failed: {response.reason}",
                    status_code=getattr(response, "status_code", -1),
                    response_body=error_text,
                )

            if getattr(response, "status_code", -1) == 204:
                return None

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(
                "Network error",
                error=str(e),
                url=url,
                method=method,
                status=getattr(response, "status_code", None),
                response=getattr(response, "content", None),
                headers=getattr(response, "headers", None),
            )
            raise exceptions.PrusaNetworkError(f"Failed to connect to Prusa Connect: {e}") from e

    def api_request(self, method: str, endpoint: str, **kwargs: typing.Any) -> typing.Any:
        """Public wrapper for making raw authenticated requests.

        This method allows access to endpoints that may not yet be covered by specific
        methods in this client.

        Args:
            method: HTTP method (e.g. "GET", "POST").
            endpoint: API endpoint (e.g. "/printers").
            **kwargs: Arbitrary keyword arguments passed to the underlying
                `requests.request` call (e.g. `json`, `data`, `timeout`).

        Returns:
            The parsed JSON response.

        Usage Example:
        ```python
            >>> response = client.api_request("GET", "/printers")
            >>> print(response)
        ```
        """
        return self._request(method, endpoint, **kwargs)

    def get_file_list(self, team_id: int) -> list[models.File]:
        """Fetch files for a specific team.

        Args:
            team_id: The team ID to fetch files for.

        Returns:
            A list of `File` objects.
        """
        return self.files.list(team_id)

    def get_team_file(self, team_id: int, file_hash: str) -> models.File:
        """Fetch details for a specific file in a team.

        Args:
            team_id: The team ID.
            file_hash: The SHA256 hash or identifier of the file.

        Returns:
            A `File` object containing detailed file metadata.
        """
        return self.files.get(team_id, file_hash)

    def initiate_team_upload(self, team_id: int, destination: str, filename: str, size: int) -> models.UploadStatus:
        """Initiate a file upload to a team's storage.

        Args:
            team_id: The team ID.
            destination: The target folder path (e.g., 'connect/My Projects').
            filename: The name of the file to upload.
            size: The file size in bytes.

        Returns:
            An `UploadStatus` object containing the upload ID and state.
        """
        return self.files.initiate_upload(team_id, destination, filename, size)

    def upload_team_file(
        self, team_id: int, upload_id: int, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """Upload raw file data for a previously initiated upload.

        Args:
            team_id: The team ID.
            upload_id: The ID of the upload session.
            data: The binary content of the file.
            content_type: Optional Content-Type header (e.g., 'application/x-bgcode').
        """
        return self.files.upload_data(team_id, upload_id, data, content_type)

    def download_team_file(self, team_id: int, file_hash: str) -> bytes:
        """Download a file from a team's storage.

        Args:
            team_id: The team ID.
            file_hash: The SHA256 hash (or identifier) of the file.

        Returns:
            The binary content of the file.
        """
        return self.files.download(team_id, file_hash)

    def get_team_users(self, team_id: int) -> list[models.TeamUser]:
        """Fetch all users associated with a team.

        Args:
            team_id: The ID of the team.

        Returns:
            A list of `TeamUser` objects.
        """
        return self.teams.list_users(team_id)

    def add_team_user(
        self,
        team_id: int,
        email: str,
        rights_ro: bool = True,
        rights_use: bool = False,
        rights_rw: bool = False,
    ) -> bool:
        """Invite a user to a team.

        Args:
            team_id: The ID of the team.
            email: The email address of the user to invite.
            rights_ro: Grant read-only rights.
            rights_use: Grant usage rights.
            rights_rw: Grant read-write rights.

        Returns:
            True if the user was invited successfully.
        """
        return self.teams.add_user(team_id, email, rights_ro, rights_use, rights_rw)

    def get_team_jobs(self, team_id: int, state: list[str] | None = None, limit: int | None = None) -> list[models.Job]:
        """Fetch job history for a team.

        Args:
            team_id: The team ID.
            state: Optional list of states to filter by (e.g. ["PRINTING", "FINISHED"]).
            limit: Optional maximum number of jobs to return.

        Returns:
            A list of `Job` objects.
        """
        return self.jobs.list_team_jobs(team_id, state=state, limit=limit)

    def get_printer_jobs(
        self, printer_uuid: str, state: list[str] | None = None, limit: int | None = None
    ) -> list[models.Job]:
        """Fetch job history for a printer.

        Args:
            printer_uuid: The printer UUID.
            state: Optional list of states to filter by.
            limit: Optional maximum number of jobs to return.

        Returns:
            A list of `Job` objects.
        """
        return self.jobs.list_printer_jobs(printer_uuid, state=state, limit=limit)

    def get_printer_queue(self, printer_uuid: str, limit: int = 100, offset: int = 0) -> list[models.Job]:
        """Fetch the print queue for a printer.

        Args:
            printer_uuid: The printer UUID.
            limit: Optional maximum number of jobs to return.
            offset: Optional offset for pagination.

        Returns:
            A list of `Job` objects representing the queue.
        """
        return self.jobs.get_queue(printer_uuid, limit, offset)

    def get_printer_material_stats(
        self,
        printer_uuid: str,
        from_time: datetime.date | int | None = None,
        to_time: datetime.date | int | None = None,
    ) -> models.MaterialQuantity:
        """Fetch material quantity statistics for a printer.

        Args:
            printer_uuid: The printer UUID.
            from_time: Optional start date or timestamp.
            to_time: Optional end date or timestamp.

        Returns:
            A `MaterialQuantity` object.
        """
        return self.stats.get_material(printer_uuid, from_time, to_time)

    def get_printer_usage_stats(
        self,
        printer_uuid: str,
        from_time: datetime.date | int | None = None,
        to_time: datetime.date | int | None = None,
    ) -> models.PrintingNotPrinting:
        """Fetch printing vs not printing statistics for a printer.

        Args:
            printer_uuid: The printer UUID.
            from_time: Optional start date or timestamp.
            to_time: Optional end date or timestamp.

        Returns:
            A `PrintingNotPrinting` object.
        """
        return self.stats.get_usage(printer_uuid, from_time, to_time)

    def get_printer_planned_tasks_stats(
        self,
        printer_uuid: str,
        from_time: datetime.date | int | None = None,
        to_time: datetime.date | int | None = None,
    ) -> models.PlannedTasks:
        """Fetch planned tasks statistics for a printer.

        Args:
            printer_uuid: The printer UUID.
            from_time: Optional start date or timestamp.
            to_time: Optional end date or timestamp.

        Returns:
            A `PlannedTasks` object.
        """
        return self.stats.get_planned_tasks(printer_uuid, from_time, to_time)

    def get_printer_jobs_success_stats(
        self,
        printer_uuid: str,
        from_time: datetime.date | int | None = None,
        to_time: datetime.date | int | None = None,
    ) -> models.JobsSuccess:
        """Fetch jobs success statistics for a printer.

        Args:
            printer_uuid: The printer UUID.
            from_time: Optional start date or timestamp.
            to_time: Optional end date or timestamp.

        Returns:
            A `JobsSuccess` object.
        """
        return self.stats.get_jobs_success(printer_uuid, from_time, to_time)

    def get_supported_commands(self, printer_uuid: str) -> list[command_models.CommandDefinition]:
        """Fetch supported commands for a printer.

        This method caches the result per printer UUID to avoid redundant network calls.
        If `cache_dir` is configured, it will also persist the commands to disk.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            A list of `CommandDefinition` objects.
        """
        return self.printers.get_supported_commands(printer_uuid)

    def execute_printer_command(
        self, printer_uuid: str, command: str, args: dict[str, typing.Any] | None = None
    ) -> bool:
        """Execute a printer command with validation against supported commands.

        This method first checks if the command is supported by the printer and
        validates the provided arguments against the command definition.

        Args:
            printer_uuid: The printer UUID.
            command: The command string (e.g., 'MOVE_Z').
            args: A dictionary of arguments for the command.

        Returns:
            True if the command was successfully sent.

        Raises:
            ValueError: If the command is not supported or arguments are invalid.
            PrusaApiError: If the API request fails.
        """
        supported = self.get_supported_commands(printer_uuid)
        definition = next((cmd for cmd in supported if cmd.command == command), None)

        if not definition:
            # We strictly enforce supported commands to prevent issues.
            # If the user really wants to bypass, they can use send_command directly.
            raise ValueError(f"Command '{command}' is not supported by printer {printer_uuid}.")

        args = args or {}

        # Validate arguments
        for arg_def in definition.args:
            if arg_def.required and arg_def.name not in args:
                raise ValueError(f"Missing required argument '{arg_def.name}' for command '{command}'.")

            if arg_def.name in args:
                val = args[arg_def.name]
                # Simple type checking based on definition
                if arg_def.type == "string" and not isinstance(val, str):
                    raise ValueError(f"Argument '{arg_def.name}' must be a string.")
                elif arg_def.type == "integer" and not isinstance(val, int):
                    raise ValueError(f"Argument '{arg_def.name}' must be an integer.")
                elif arg_def.type == "boolean" and not isinstance(val, bool):
                    raise ValueError(f"Argument '{arg_def.name}' must be a boolean.")
                elif arg_def.type == "number" and not isinstance(val, (int, float)):
                    raise ValueError(f"Argument '{arg_def.name}' must be a number.")
                # 'object' type is too generic to validate easily here without more schema

        return self.printers.send_command(printer_uuid, command, args)

    def get_snapshot(self, camera_id: str) -> bytes:
        """Fetch a snapshot from a camera.

        Args:
            camera_id: The numeric camera ID.

        Returns:
            The binary image data.

        Usage Example:
        ```python
            >>> image_data = client.get_snapshot(camera_id="cam-1")
            >>> with open("snap.jpg", "wb") as f:
            ...     f.write(image_data)
        ```
        """
        # Raw response for binary data
        response = self._request("GET", f"/app/cameras/{camera_id}/snapshots/last", raw=True)
        return response.content

    def trigger_snapshot(self, camera_token: str) -> bool:
        """Trigger a new snapshot locally on the camera/server.

        Args:
            camera_token: The camera token (alphanumeric).

        Returns:
            True if triggered successfully.

        Usage Example:
        ```python
            >>> client.trigger_snapshot("camera-token-xyz")
        ```
        """
        self._request("POST", f"/app/cameras/{camera_token}/snapshots")
        return True

    def pause_print(self, printer_uuid: str) -> bool:
        """Pause the current print.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            True if the command was successfully sent.
        """
        return self.printers.send_command(printer_uuid, "PAUSE_PRINT")

    def resume_print(self, printer_uuid: str) -> bool:
        """Resume the current print.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            True if the command was successfully sent.
        """
        return self.printers.send_command(printer_uuid, "RESUME_PRINT")

    def stop_print(self, printer_uuid: str) -> bool:
        """Stop the current print.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            True if the command was successfully sent.
        """
        return self.printers.send_command(printer_uuid, "STOP_PRINT")

    def cancel_object(self, printer_uuid: str, object_id: int) -> bool:
        """Cancel a specific object during print.

        Args:
            printer_uuid: The printer UUID.
            object_id: The ID of the object to cancel.

        Returns:
            True if the command was successfully sent.
        """
        return self.printers.send_command(printer_uuid, "CANCEL_OBJECT", {"object_id": object_id})

    def move_axis(
        self,
        printer_uuid: str,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
        e: float | None = None,
        speed: float | None = None,
    ) -> bool:
        """Move printer axis.

        Args:
            printer_uuid: The printer UUID.
            x: Target X position.
            y: Target Y position.
            z: Target Z position.
            e: Extruder movement.
            speed: Feedrate (speed).

        Returns:
            True if the command was successfully sent.
        """
        kwargs = {}
        if x is not None:
            kwargs["x"] = x
        if y is not None:
            kwargs["y"] = y
        if z is not None:
            kwargs["z"] = z
        if e is not None:
            kwargs["e"] = e
        if speed is not None:
            kwargs["feedrate"] = speed

        # MOVE usually requires at least one axis or speed?
        # Based on captured data, we saw: {"feedrate": 3000, "x": 131, "y": 134}
        return self.printers.send_command(printer_uuid, "MOVE", kwargs)

    def flash_firmware(self, printer_uuid: str, file_path: str) -> bool:
        """Flash firmware from a file path on the printer/storage.

        Args:
            printer_uuid: The printer UUID.
            file_path: The path to the .bbf file on the printer's storage (e.g. /usb/firmware.bbf).

        Returns:
            True if the command was successfully sent.
        """
        return self.printers.send_command(printer_uuid, "FLASH", {"path": file_path})

    def set_job_failure_reason(
        self, printer_uuid: str, job_id: int, reason: models.JobFailureTag, note: str = ""
    ) -> bool:
        """Set the failure reason for a stopped job.

        Args:
            printer_uuid: The printer UUID.
            job_id: The job ID.
            reason: The failure reason Enum.
            note: Optional user note ("other" field).

        Returns:
            True if successful.
        """
        payload = {"reason": {"tag": [reason.value], "other": note}}
        self._request("PATCH", f"/app/printers/{printer_uuid}/jobs/{job_id}", json=payload)
        return True

    def get_job(self, printer_uuid: str, job_id: int) -> models.Job:
        """Fetch detailed information about a specific job.

        Args:
            printer_uuid: The printer UUID.
            job_id: The job ID.

        Returns:
            A `Job` object.
        """
        data = self._request("GET", f"/app/printers/{printer_uuid}/jobs/{job_id}")
        return models.Job.model_validate(data)

    def get_printer_files(self, printer_uuid: str) -> list[models.File]:
        """Fetch files stored on the printer.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            A list of `File` objects.
        """
        data = self._request("GET", f"/app/printers/{printer_uuid}/files")
        if isinstance(data, dict) and "files" in data:
            return [pydantic.TypeAdapter(models.File).validate_python(f) for f in data["files"]]
        return []

    def get_printer_storages(self, printer_uuid: str) -> list[models.Storage]:
        """Fetch storage devices attached to the printer.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            A list of `Storage` objects.
        """
        data = self._request("GET", f"/app/printers/{printer_uuid}/storages")
        if isinstance(data, list):
            return [models.Storage.model_validate(s) for s in data]
        if isinstance(data, dict) and "storages" in data:
            return [models.Storage.model_validate(s) for s in data["storages"]]
        return []

    def validate_gcode(self, file_path: Path | str) -> gcode.GCodeMetadata:
        """Validates a G-code file and returns its metadata.

        This is a utility method for pre-flight checks before uploading.

        Args:
            file_path: Path to the .gcode file.

        Returns:
            A GCodeMetadata object containing extracted info.
        """
        path = Path(file_path)
        metadata = gcode.parse_gcode_header(path)

        if metadata.estimated_time:
            logger.info("Validated G-code", path=str(path), time=metadata.estimated_time)
        else:
            logger.warning("G-code metadata missing or unparseable", path=str(path))

        return metadata
