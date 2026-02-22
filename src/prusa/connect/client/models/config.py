"""Models for the /app/config endpoint."""

from prusa.connect.client.models.common import WarnExtraFieldsModel


class AuthConfig(WarnExtraFieldsModel):
    """Authentication configuration."""

    backends: list[str]
    server_url: str
    client_id: str
    redirect_url: str
    avatar_server_url: str
    max_upload_size: int
    max_snapshot_size: int
    max_preview_size: int
    afs_enabled: bool
    afs_group_id: int


class AppConfig(WarnExtraFieldsModel):
    """Application configuration returned by /app/config."""

    auth: AuthConfig
