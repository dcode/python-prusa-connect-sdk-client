"""Service for Camera operations."""

import json

import structlog

from prusa.connect.client import models
from prusa.connect.client.services.base import BaseService

logger = structlog.get_logger(__name__)


class CameraService(BaseService):
    """Service for managing cameras."""

    def list(self, limit: int = 50, offset: int = 0) -> list[models.Camera]:
        """Fetch all cameras.

        Args:
            limit: Maximum number of teams to return.
            offset: Number of teams to skip.

        Returns:
            A list of `Camera` objects.
        """
        params = {"limit": limit, "offset": offset}
        data = self._client.request("GET", "/app/cameras", params=params)
        if isinstance(data, dict) and "cameras" in data:
            logger.debug("Received cameras.", cameras=json.dumps(data["cameras"], default=str))
            return [models.Camera.model_validate(c) for c in data["cameras"]]
        elif isinstance(data, list):
            logger.debug("Received cameras.", cameras=json.dumps(data, default=str))
            return [models.Camera.model_validate(c) for c in data]
        return []

    # Note: get_client logic requires credentials access.
    # The SDK refactor plan says PrusaConnectClient should delegate.
    # But PrusaConnectClient holds _credentials.
    # PrusaCameraClient needs a jwt token.
    # This might need to stay on PrusaConnectClient or receive the token.
    # For now, I'll omit it here and keep it on the main client,
    # OR pass the token generator here.
    # Since `BaseService` only has `request`, it doesn't have credentials access.
    # Actually, `request` implementation on usage side (PrusaConnectClient) handles auth.
    # So CameraService cannot easily get the raw token unless we expose it.
    # I will leave `get_camera_client` on `PrusaConnectClient` directly for now as it's a factory method.
