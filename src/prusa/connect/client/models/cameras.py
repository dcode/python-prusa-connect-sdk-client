"""Camera models for Prusa Connect SDK."""

from .common import WarnExtraFieldsModel


class CameraResolution(WarnExtraFieldsModel):
    """Camera resolution details."""

    width: int
    height: int


class CameraNetworkInfo(WarnExtraFieldsModel):
    """Camera network configuration."""

    wifi_mac: str | None = None
    wifi_ipv4: str | None = None
    wifi_ssid: str | None = None


class CameraConfig(WarnExtraFieldsModel):
    """Camera internal configuration snapshot."""

    name: str | None = None
    path: str | None = None
    model: str | None = None
    driver: str | None = None
    firmware: str | None = None
    rotation: int | None = None
    camera_id: str | None = None
    resolution: CameraResolution | None = None
    manufacturer: str | None = None
    network_info: CameraNetworkInfo | None = None
    trigger_scheme: str | None = None


class CameraOptions(WarnExtraFieldsModel):
    """Available options/capabilities for the camera."""

    available_resolutions: list[CameraResolution] | None = None


class Camera(WarnExtraFieldsModel):
    """Camera information."""

    id: int | None = None  # Numeric ID for snapshots
    token: str | None = None  # Alphanumeric token/id in some contexts?
    name: str | None = None
    origin: str | None = None
    resolution: str | None = None
    snapshot_url: str | None = None

    config: CameraConfig | None = None
    options: CameraOptions | None = None
    capabilities: list[str] | None = None
    features: list[str] | None = None
    sort_order: int | None = None
    registered: bool | None = None
    team_id: int | None = None
    printer_uuid: str | None = None

    snapshots: list[str] | None = None
