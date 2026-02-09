"""Prusa Connect REST API Client.

This module provides a high-level interface to interact with the Prusa Connect API,
handling authentication, error parsing, connection pooling, and response validation.

How to use the most important parts:
- `PrusaConnectClient`: The core class. Instantiate it (optionally with `PrusaConnectCredentials`) to begin
  controlling printers.
- Look at the methods available on `PrusaConnectClient`, such as `get_printers()`, `send_command(...)`,
  and `get_team_users(...)`, for an exhaustive list of actions supported.
"""

import collections.abc
import json
import time
import typing
from pathlib import Path

import pydantic
import requests
import structlog
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from prusa.connect.client import auth, camera, command_models, consts, exceptions, gcode, models
from prusa.connect.client.__version__ import __version__

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
        >>> printers = client.get_printers()
    ```
    """

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
        self._supported_commands_cache: dict[str, list[command_models.CommandDefinition]] = {}

        # Configure Retries
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods={"GET", "POST", "PUT", "DELETE", "PATCH"},
        )
        adapter = HTTPAdapter(max_retries=retries)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        self._session.headers.update(
            {
                "User-Agent": f"prusa-connect-python/{__version__}",
                "Accept": "application/json",
            }
        )

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

        try:
            logger.debug("API Request", method=method, url=url)
            # Check for stream in kwargs before request
            is_stream = kwargs.get("stream", False)
            response = self._session.request(method, url, **kwargs)

            # Avoid reading content if streaming
            body_len = "STREAM" if is_stream else len(response.content)

            logger.debug(
                "API Response",
                status_code=response.status_code,
                headers=dict(response.headers),
                body_len=body_len,
            )

            if response.status_code in (401, 403):
                raise exceptions.PrusaAuthError("Invalid or expired credentials.")

            if response.status_code >= 400:
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
                    status_code=response.status_code,
                    response_body=error_text,
                )

            if response.status_code == 204:
                return None

            if raw:
                return response

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error("Network error", error=str(e))
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

    def get_printers(self) -> list[models.Printer]:
        """Fetch all printers associated with the account.

        This method caches the result to avoid redundant network calls if `cache_dir` is configured.
        The cache is updated on every successful network call. If the network call fails,
        it attempts to return cached data.

        Returns:
            A list of `Printer` objects.

        Usage Example:
        ```python
            >>> printers = client.get_printers()
            >>> for printer in printers:
            ...     print(printer.name, printer.printer_state)
        ```
        """
        cache_file = None
        if self._cache_dir:
            cache_file = self._cache_dir / "printers" / "list.json"

        try:
            data = self._request("GET", "/printers")

            # Helper to parse data
            parsed_printers = []
            if isinstance(data, dict) and "printers" in data:
                parsed_printers = [models.Printer.model_validate(p) for p in data["printers"]]
            elif isinstance(data, list):
                parsed_printers = [models.Printer.model_validate(p) for p in data]
            else:
                logger.warning("Unexpected printer response format", data=data)

            # Update cache if successful
            if cache_file and parsed_printers:
                try:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    # We store the raw API response or a simplified list?
                    # Let's store the list of models for consistency
                    cache_data = {"printers": [p.model_dump(mode="json") for p in parsed_printers]}
                    cache_file.write_text(json.dumps(cache_data, indent=2))
                except Exception as e:
                    logger.warning("Failed to save printers to cache", error=str(e))

            return parsed_printers

        except Exception as e:
            # Fallback to cache
            if cache_file and cache_file.exists():
                try:
                    # Check TTL
                    mtime = cache_file.stat().st_mtime
                    age = time.time() - mtime
                    if age > self._cache_ttl:
                        logger.warning("Cached printer list expired", age=age, ttl=self._cache_ttl)
                        raise exceptions.PrusaAuthError("Cache expired and network failed.")  # Or just fail

                    logger.info("Using cached printer list due to error", error=str(e))
                    data = json.loads(cache_file.read_text())
                    if isinstance(data, dict) and "printers" in data:
                        return [models.Printer.model_validate(p) for p in data["printers"]]
                except Exception as cache_e:
                    logger.warning("Failed to load cached printers", error=str(cache_e))

            # if no cache or cache failed, re-raise original error
            raise e

    def get_printer(self, uuid: str) -> models.Printer:
        """Fetch details for a specific printer.

        Args:
            uuid: The UUID of the printer.

        Returns:
            A `Printer` object containing detailed telemetry and state.

        Usage Example:
        ```python
            >>> printer = client.get_printer("c0ffee-uuid")
            >>> print(printer.telemetry.temp_nozzle)
        ```
        """
        data = self._request("GET", f"/printers/{uuid}")
        return models.Printer.model_validate(data)

    def get_file_list(self, team_id: int) -> list[models.File]:
        """Fetch files for a specific team.

        Args:
            team_id: The team ID to fetch files for.

        Returns:
            A list of `File` objects.

        Usage Example:
        ```python
            >>> files = client.get_file_list(1)
            >>> for file in files:
            ...     print(file.name)
        ```
        """
        data = self._request("GET", f"/teams/{team_id}/files")

        if isinstance(data, dict) and "files" in data:
            logger.debug("Fetched files for team", team_id=team_id)
            files = []
            for f in data["files"]:
                logger.debug("File", file=f)
                files.append(pydantic.TypeAdapter(models.File).validate_python(f))
            return files
        return []

    def get_team_file(self, team_id: int, file_hash: str) -> models.File:
        """Fetch details for a specific file in a team.

        Args:
            team_id: The team ID.
            file_hash: The SHA256 hash or identifier of the file.

        Returns:
            A `File` object containing detailed file metadata.

        Usage Example:
        ```python
            >>> file_info = client.get_team_file(1, "file_hash")
            >>> print(file_info.name)
        ```
        """
        data = self._request("GET", f"/teams/{team_id}/files/{file_hash}")
        logger.debug("Fetched team file", team_id=team_id, file_hash=file_hash)
        return pydantic.TypeAdapter(models.File).validate_python(data)

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
        payload = {"destination": destination, "filename": filename, "size": size}
        data = self._request("POST", f"/users/teams/{team_id}/uploads", json=payload)
        return models.UploadStatus.model_validate(data)

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
        headers = {"Content-Type": content_type, "Upload-Size": str(len(data))}
        self._request("PUT", f"/teams/{team_id}/files/raw?upload_id={upload_id}", data=data, headers=headers)

    def download_team_file(self, team_id: int, file_hash: str) -> bytes:
        """Download a file from a team's storage.

        Args:
            team_id: The team ID.
            file_hash: The SHA256 hash (or identifier) of the file.

        Returns:
            The binary content of the file.
        """
        response = self._request("GET", f"/teams/{team_id}/files/{file_hash}/raw", raw=True)
        return response.content

    def get_cameras(self) -> list[models.Camera]:
        """Fetch all cameras.

        Returns:
            A list of `Camera` objects.

        Usage Example:
        ```python
            >>> cameras = client.get_cameras()
            >>> for cam in cameras:
            ...     print(cam.name)
        ```
        """
        data = self._request("GET", "/cameras")
        if isinstance(data, dict) and "cameras" in data:
            logger.debug("Received cameras.", cameras=json.dumps(data["cameras"]))
            return [models.Camera.model_validate(c) for c in data["cameras"]]
        return []

    def get_teams(self) -> list[models.Team]:
        """Fetch all teams associated with the account.

        Returns:
            A list of `Team` objects.

        Usage Example:
        ```python
            >>> teams = client.get_teams()
            >>> for team in teams:
            ...     print(team.name)
        ```
        """
        data = self._request("GET", "/users/teams")
        teams: list[models.Team] = []
        if isinstance(data, list):
            logger.debug("Fetched multiple teams")
            teams = [models.Team.model_validate(t) for t in data]
        return teams

    def get_team(self, team_id: int) -> models.Team:
        """Fetch detailed information for a specific team.

        Args:
            team_id: The ID of the team.

        Returns:
            A `Team` object.
        """
        data = self._request("GET", f"/users/teams/{team_id}")
        return models.Team.model_validate(data)

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
        payload = {
            "email": email,
            "rights_ro": rights_ro,
            "rights_use": rights_use,
            "rights_rw": rights_rw,
        }
        self._request("POST", f"/teams/{team_id}/add-user", json=payload)
        return True

    def get_team_jobs(self, team_id: int, state: list[str] | None = None, limit: int | None = None) -> list[models.Job]:
        """Fetch job history for a team.

        Args:
            team_id: The team ID.
            state: Optional list of states to filter by (e.g. ["PRINTING", "FINISHED"]).
            limit: Optional maximum number of jobs to return.

        Returns:
            A list of `Job` objects.

        Usage Example:
        ```python
            >>> jobs = client.get_team_jobs(team_id=123, limit=5)
            >>> print(f"Found {len(jobs)} jobs")
        ```
        """
        data = self._request("GET", f"/teams/{team_id}/jobs")
        jobs: list[models.Job] = []
        if isinstance(data, dict) and "jobs" in data:
            jobs = [models.Job.model_validate(j) for j in data["jobs"]]

        # Client-side filtering/limiting since API params are not fully confirmed
        if state:
            state_set = set(state)
            jobs = [j for j in jobs if j.state in state_set]

        if limit is not None:
            jobs = jobs[:limit]

        return jobs

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

        Usage Example:
        ```python
            >>> jobs = client.get_printer_jobs("printer-uuid", state=["FINISHED"])
            >>> if jobs:
            ...     print(jobs[0].state)
        ```
        """
        data = self._request("GET", f"/printers/{printer_uuid}/jobs")
        jobs: list[models.Job] = []
        if isinstance(data, dict) and "jobs" in data:
            jobs = [models.Job.model_validate(j) for j in data["jobs"]]

        # Client-side filtering/limiting
        if state:
            state_set = set(state)
            jobs = [j for j in jobs if j.state in state_set]

        if limit is not None:
            jobs = jobs[:limit]

        return jobs

    def get_printer_queue(self, printer_uuid: str) -> list[models.Job]:
        """Fetch the print queue for a printer.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            A list of `Job` objects representing the queue.

        Usage Example:
        ```python
            >>> queue = client.get_printer_queue("printer-uuid")
            >>> if queue:
            ...     print(queue[0].state)
        ```
        """
        data = self._request("GET", f"/printers/{printer_uuid}/queue")

        # Structure from users reverse engineering:
        # GET response usually: {"planned_jobs": [...] }
        # POST response (adding): single object

        if isinstance(data, dict):
            if "planned_jobs" in data:
                return [models.Job.model_validate(j) for j in data["planned_jobs"]]
            # Fallback for other potential keys or single object if the API is quirky
            if "jobs" in data:
                return [models.Job.model_validate(j) for j in data["jobs"]]
            if "queue" in data:
                return [models.Job.model_validate(j) for j in data["queue"]]

            # If it looks like a single job (has 'id' and 'state')
            if "id" in data and "state" in data:
                return [models.Job.model_validate(data)]

        elif isinstance(data, list):
            return [models.Job.model_validate(j) for j in data]

        # Fallback empty
        return []

    def send_command(self, printer_uuid: str, command: str, kwargs: dict | None = None) -> bool:
        """Send a command to a printer.

        Args:
            printer_uuid: The printer UUID.
            command: The command string (e.g., 'PAUSE_PRINT', 'MOVE_Z').
            kwargs: Optional arguments for the command.

        Returns:
            True if the command was successfully sent.

        Usage Example:
        ```python
            >>> client.send_command("printer-uuid", "PAUSE_PRINT")
        ```
        """
        payload: dict[str, typing.Any] = {"command": command}
        if kwargs:
            payload["kwargs"] = kwargs

        # discovery says /commands/sync is definitive
        self._request("POST", f"/printers/{printer_uuid}/commands/sync", json=payload)
        return True

    def get_supported_commands(self, printer_uuid: str) -> list[command_models.CommandDefinition]:
        """Fetch supported commands for a printer.

        This method caches the result per printer UUID to avoid redundant network calls.
        If `cache_dir` is configured, it will also persist the commands to disk.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            A list of `CommandDefinition` objects.
        """
        # 1. Check Memory Cache
        if printer_uuid in self._supported_commands_cache:
            return self._supported_commands_cache[printer_uuid]

        # 2. Check Disk Cache (if enabled)
        cache_file = None
        if self._cache_dir:
            cache_file = self._cache_dir / "printers" / printer_uuid / "commands.json"
            if cache_file.exists():
                try:
                    mtime = cache_file.stat().st_mtime
                    age = time.time() - mtime
                    if age <= self._cache_ttl:
                        logger.debug("Loading commands from cache", path=str(cache_file))
                        data = json.loads(cache_file.read_text())
                        response = command_models.SupportedCommandsResponse.model_validate(data)
                        self._supported_commands_cache[printer_uuid] = response.commands
                        return response.commands
                    else:
                        logger.debug("Cached commands expired", age=age, ttl=self._cache_ttl)
                except Exception as e:
                    logger.warning("Failed to load cached commands", error=str(e))
                    # Fallback to network on error

        # 3. Fetch from Network
        data = self._request("GET", f"/printers/{printer_uuid}/supported-commands")

        # Parse response
        response = command_models.SupportedCommandsResponse.model_validate(data)
        self._supported_commands_cache[printer_uuid] = response.commands

        # 4. Save to Disk (if enabled)
        if cache_file:
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(data, indent=2))
            except Exception as e:
                logger.warning("Failed to save commands to cache", error=str(e))

        # 5. Check Compatibility
        # We ensure core commands are present.
        cmd_names = {c.command for c in response.commands}
        # The user specifically mentioned STOP_PRINT as core functionality.
        # We can add others later if needed.
        required = {"STOP_PRINT", "PAUSE_PRINT"}
        missing = required - cmd_names

        if missing:
            # Gather details for failure report
            report_data = {
                "missing_commands": list(missing),
                "supported_commands": [c.model_dump(mode="json") for c in response.commands],
                "printer_details": {},
                "timestamp": time.time(),
            }

            try:
                # Try to fetch printer details for context
                p_details = self.get_printer(printer_uuid)
                p_dump = p_details.model_dump(mode="json")

                # Redact sensitive info
                # serial number (uuid?), printer name, owner name, printer IP, location, team name
                keys_to_redact = {"name", "location", "team_name", "uuid", "serial", "ip", "hostname", "ipv4", "mac"}

                def redact_recursive(d):
                    if isinstance(d, dict):
                        for k, v in d.items():
                            if k.lower() in keys_to_redact or any(
                                x in k.lower() for x in ["ip", "mac", "serial", "token"]
                            ):
                                d[k] = "[REDACTED]"
                            else:
                                redact_recursive(v)
                    elif isinstance(d, list):
                        for i in d:
                            redact_recursive(i)

                redact_recursive(p_dump)
                report_data["printer_details"] = p_dump

            except Exception as e:
                logger.warning("Failed to fetch printer details for error report", error=str(e))
                report_data["printer_details"] = {"error": str(e)}

            raise exceptions.PrusaCompatibilityError(
                (
                    f"Printer {printer_uuid} is missing required commands: {missing}."
                    " This may indicate a firmware incompatibility."
                ),
                missing_commands=list(missing),
                report_data=report_data,
            )

        return response.commands

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

        return self.send_command(printer_uuid, command, args)

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
        response = self._request("GET", f"/cameras/{camera_id}/snapshots/last", raw=True)
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
        self._request("POST", f"/cameras/{camera_token}/snapshots")
        return True

    def pause_print(self, printer_uuid: str) -> bool:
        """Pause the current print.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            True if the command was successfully sent.
        """
        return self.send_command(printer_uuid, "PAUSE_PRINT")

    def resume_print(self, printer_uuid: str) -> bool:
        """Resume the current print.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            True if the command was successfully sent.
        """
        return self.send_command(printer_uuid, "RESUME_PRINT")

    def stop_print(self, printer_uuid: str) -> bool:
        """Stop the current print.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            True if the command was successfully sent.
        """
        return self.send_command(printer_uuid, "STOP_PRINT")

    def cancel_object(self, printer_uuid: str, object_id: int) -> bool:
        """Cancel a specific object during print.

        Args:
            printer_uuid: The printer UUID.
            object_id: The ID of the object to cancel.

        Returns:
            True if the command was successfully sent.
        """
        return self.send_command(printer_uuid, "CANCEL_OBJECT", {"object_id": object_id})

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
        return self.send_command(printer_uuid, "MOVE", kwargs)

    def flash_firmware(self, printer_uuid: str, file_path: str) -> bool:
        """Flash firmware from a file path on the printer/storage.

        Args:
            printer_uuid: The printer UUID.
            file_path: The path to the .bbf file on the printer's storage (e.g. /usb/firmware.bbf).

        Returns:
            True if the command was successfully sent.
        """
        return self.send_command(printer_uuid, "FLASH", {"path": file_path})

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
        self._request("PATCH", f"/printers/{printer_uuid}/jobs/{job_id}", json=payload)
        return True

    def get_job(self, printer_uuid: str, job_id: int) -> models.Job:
        """Fetch detailed information about a specific job.

        Args:
            printer_uuid: The printer UUID.
            job_id: The job ID.

        Returns:
            A `Job` object.
        """
        data = self._request("GET", f"/printers/{printer_uuid}/jobs/{job_id}")
        return models.Job.model_validate(data)

    def get_printer_files(self, printer_uuid: str) -> list[models.File]:
        """Fetch files stored on the printer.

        Args:
            printer_uuid: The printer UUID.

        Returns:
            A list of `File` objects.
        """
        data = self._request("GET", f"/printers/{printer_uuid}/files")
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
        data = self._request("GET", f"/printers/{printer_uuid}/storages")
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
