"""Service for File operations."""

import pydantic
import structlog

from prusa.connect.client import models
from prusa.connect.client.services.base import BaseService

logger = structlog.get_logger(__name__)


class FileService(BaseService):
    """Service for managing files."""

    def list(self, team_id: int) -> list[models.File]:
        """Fetch files for a specific team.

        Args:
            team_id: The team ID to fetch files for.

        Returns:
            A list of `File` objects.
        """
        data = self._client.request("GET", f"/app/teams/{team_id}/files")

        if isinstance(data, dict) and "files" in data:
            logger.debug("Fetched files for team", team_id=team_id)
            files = []
            for f in data["files"]:
                logger.debug("File", file=f)
                files.append(pydantic.TypeAdapter(models.File).validate_python(f))
            return files
        return []

    def get(self, team_id: int, file_hash: str) -> models.File:
        """Fetch details for a specific file in a team.

        Args:
            team_id: The team ID.
            file_hash: The SHA256 hash or identifier of the file.

        Returns:
            A `File` object containing detailed file metadata.
        """
        data = self._client.request("GET", f"/app/teams/{team_id}/files/{file_hash}")
        logger.debug("Fetched team file", team_id=team_id, file_hash=file_hash)
        return pydantic.TypeAdapter(models.File).validate_python(data)

    def initiate_upload(self, team_id: int, destination: str, filename: str, size: int) -> models.UploadStatus:
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
        data = self._client.request("POST", f"/app/users/teams/{team_id}/uploads", json=payload)
        return models.UploadStatus.model_validate(data)

    def upload_data(
        self,
        team_id: int,
        upload_id: int,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload raw file data for a previously initiated upload.

        Args:
            team_id: The team ID.
            upload_id: The ID of the upload session.
            data: The binary content of the file.
            content_type: Optional Content-Type header (e.g., 'application/x-bgcode').
        """
        headers = {"Content-Type": content_type, "Upload-Size": str(len(data))}
        self._client.request(
            "PUT",
            f"/app/teams/{team_id}/files/raw?upload_id={upload_id}",
            data=data,
            headers=headers,
        )

    def download(self, team_id: int, file_hash: str) -> bytes:
        """Download a file from a team's storage.

        Args:
            team_id: The team ID.
            file_hash: The SHA256 hash (or identifier) of the file.

        Returns:
            The binary content of the file.
        """
        response = self._client.request("GET", f"/app/teams/{team_id}/files/{file_hash}/raw", raw=True)
        return response.content
