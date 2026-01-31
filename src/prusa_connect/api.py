from typing import Any, Dict, List, Optional

import requests
import structlog

logger = structlog.get_logger()

BASE_URL = "https://connect.prusa3d.com/app"


class PrusaConnectAPI:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) auto-script",
                "Accept": "application/json",
            }
        )

    def get_api_version(self) -> dict[str,str]:
        logger.info("Getting API Version Info...")
        resp = self.session.get(f"{BASE_URL}/version.json")
        if resp.status_code == 200:
            data = resp.json()
            logger.debug("Version response", data=data)
            return data
        logger.warning("Failed to get API version info", status_code=resp.status_code)
        return {}

    def get_teams(self) -> List[Dict[str, Any]]:
        logger.info("Listing Teams...")
        resp = self.session.get(f"{BASE_URL}/users/teams")
        if resp.status_code == 200:
            data = resp.json()
            logger.debug("Teams response", data=data)
            return data.get("teams", [])
        logger.warning("Failed to get teams", status_code=resp.status_code)
        return []

    def get_printers(self) -> List[Dict[str, Any]]:
        logger.info("Listing Printers...")
        resp = self.session.get(f"{BASE_URL}/printers")
        if resp.status_code == 200:
            data = resp.json()
            logger.debug("Printers response", data=data)
            if isinstance(data, dict):
                return data.get("printers", [])
            return data
        logger.warning("Failed to get printers", status_code=resp.status_code)
        return []

    def get_printer_details(self, uuid: str) -> Optional[Dict[str, Any]]:
        logger.info("Fetching details for printer", uuid=uuid)
        resp = self.session.get(f"{BASE_URL}/printers/{uuid}")
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Failed to get printer details", uuid=uuid, status_code=resp.status_code)
        return None

    def get_printer_cameras(self, uuid: str) -> List[Dict[str, Any]]:
        resp = self.session.get(f"{BASE_URL}/printers/{uuid}/cameras")
        if resp.status_code == 200:
            cams_data = resp.json()
            logger.debug("Camera endpoint response", data=cams_data)
            if isinstance(cams_data, dict):
                return cams_data.get("cameras", [])
            return cams_data
        logger.warning("Failed to get printer cameras", uuid=uuid, status_code=resp.status_code)
        return []

    def get_global_cameras(self) -> List[Dict[str, Any]]:
        """Get all cameras for the user/team."""
        logger.info("Listing Global Cameras...")
        resp = self.session.get(f"{BASE_URL}/cameras")
        if resp.status_code == 200:
            data = resp.json()
            logger.debug("Global cameras response", data=data)
            if isinstance(data, dict):
                return data.get("cameras", [])
            return data
        logger.warning("Failed to get global cameras", status_code=resp.status_code)
        return []

    def get_config(self) -> Dict[str, Any]:
        """Get global configuration/settings."""
        logger.info("Fetching Config...")
        resp = self.session.get(f"{BASE_URL}/config")
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Failed to get config", status_code=resp.status_code)
        return {}

    def get_printer_types(self) -> List[Dict[str, Any]]:
        """Get available printer types."""
        logger.info("Fetching Printer Types...")
        resp = self.session.get(f"{BASE_URL}/printer-types")
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Failed to get printer types", status_code=resp.status_code)
        return []

    def get_printer_groups(self) -> List[Dict[str, Any]]:
        """Get printer groups."""
        logger.info("Fetching Printer Groups...")
        resp = self.session.get(f"{BASE_URL}/printers/groups")
        if resp.status_code == 200:
            data = resp.json()
            return data.get("groups", [])
        logger.warning("Failed to get printer groups", status_code=resp.status_code)
        return []

    def get_notifications(self, unseen_only: bool = False) -> List[Dict[str, Any]]:
        """Get notifications."""
        endpoint = f"{BASE_URL}/notifications/unseen" if unseen_only else f"{BASE_URL}/notifications"
        logger.info("Fetching Notifications...", unseen_only=unseen_only)
        resp = self.session.get(endpoint)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("notifications", [])
        logger.warning("Failed to get notifications", status_code=resp.status_code)
        return []

    def send_printer_command(self, uuid: str, command: str, kwargs: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a command to the printer.
        
        Args:
            uuid: Printer UUID
            command: Command name (e.g. PAUSE_PRINT, RESUME_PRINT, STOP_PRINT, CANCEL_JOB, MOVE_Z)
            kwargs: Optional arguments for the command
        """
        logger.info(f"Sending command '{command}' to printer {uuid}...", kwargs=kwargs)
        
        payload = {
            "command": command,
            "kwargs": kwargs or {}
        }
        
        # New discovery: use /commands/sync endpoint
        resp = self.session.post(f"{BASE_URL}/printers/{uuid}/commands/sync", json=payload)
        
        if resp.status_code in (200, 201, 204):
            logger.info("Command sent successfully", response=resp.json() if resp.content else None)
            return True
            
        logger.warning("Failed to send command", command=command, status_code=resp.status_code, response=resp.text)
        return False

    
    def take_camera_snapshot(self, camera_id: str) -> bool:
        """Trigger a new snapshot for the camera."""
        logger.info(f"Triggering snapshot for camera {camera_id}...")
        resp = self.session.post(f"{BASE_URL}/cameras/{camera_id}/snapshots")
        if resp.status_code in (200, 204):
            return True
        logger.warning(f"Failed to take snapshot", status_code=resp.status_code)
        return False
    
    def get_latest_snapshot(self, camera_id: str) -> Optional[bytes]:
        """Get the latest snapshot image content."""
        logger.info(f"Fetching latest snapshot for camera {camera_id}...")
        # Direct endpoint for latest snapshot content (using integer ID)
        resp = self.session.get(f"{BASE_URL}/cameras/{camera_id}/snapshots/last")
        if resp.status_code == 200:
            return resp.content
        logger.warning("Failed to get snapshot", status_code=resp.status_code)
        return None

    def pause_print(self, uuid: str) -> bool:
        """Pause the current print job."""
        return self.send_printer_command(uuid, "PAUSE_PRINT")

    def resume_print(self, uuid: str) -> bool:
        """Resume the paused print job."""
        return self.send_printer_command(uuid, "RESUME_PRINT")

    def stop_print(self, uuid: str) -> bool:
        """Stop/Cancel the current print job."""
        return self.send_printer_command(uuid, "STOP_PRINT")

    def move_axis(self, uuid: str, axis_data: Dict[str, Any]) -> bool:
        """
        Move printer axes.
        
        Args:
            uuid: Printer UUID
            axis_data: Dictionary of axes and values (e.g. {"x": 10, "y": 20, "feedrate": 3000})
                      Axes can be "x", "y", "z", "e".
        """
        return self.send_printer_command(uuid, "MOVE", kwargs=axis_data)

    def get_telemetry(self, uuid: str, granularity: int = 15, from_ts: Optional[int] = None) -> Dict[str, Any]:
        """
        Get printer telemetry data.
        
        Args:
            uuid: Printer UUID
            granularity: Data granularity in seconds (default: 15)
            from_ts: Optional timestamp to fetch data from
        """
        logger.info("Fetching Telemetry...", uuid=uuid, granularity=granularity)
        params = {"granularity": granularity}
        if from_ts:
            params["from"] = from_ts
            
        resp = self.session.get(f"{BASE_URL}/printers/{uuid}/telemetry", params=params)
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Failed to get telemetry", uuid=uuid, status_code=resp.status_code)
        return {}

    def get_files(self, uuid: str) -> Dict[str, Any]:
        """List files on the printer storage."""
        logger.info("Listing Files...", uuid=uuid)
        resp = self.session.get(f"{BASE_URL}/printers/{uuid}/files")
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Failed to get files", uuid=uuid, status_code=resp.status_code)
        return {}

    def get_job_history(self, uuid: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Get job history for the printer."""
        logger.info("Fetching Job History...", uuid=uuid, limit=limit, offset=offset)
        params = {"limit": limit, "offset": offset}
        resp = self.session.get(f"{BASE_URL}/printers/{uuid}/jobs", params=params)
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Failed to get job history", uuid=uuid, status_code=resp.status_code)
        return {}

    def get_print_queue(self, uuid: str) -> Dict[str, Any]:
        """Get current print queue."""
        logger.info("Fetching Print Queue...", uuid=uuid)
        resp = self.session.get(f"{BASE_URL}/printers/{uuid}/queue")
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Failed to get print queue", uuid=uuid, status_code=resp.status_code)
        return {}
