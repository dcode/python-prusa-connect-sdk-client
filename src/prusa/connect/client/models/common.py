"""Common models for Prusa Connect SDK."""

import datetime
import json
import typing

import pydantic
import structlog

from prusa.connect.client import consts

logger = structlog.get_logger(__name__)


class WarnExtraFieldsModel(pydantic.BaseModel):
    """Base model that logs a warning if extra fields are present."""

    model_config = pydantic.ConfigDict(extra="allow")

    def __init__(self, **data: typing.Any):
        """Initialize the model."""
        super().__init__(**data)
        if self.__pydantic_extra__:
            logger.warning(
                f"Model {self.__class__.__name__} received unknown fields: {list(self.__pydantic_extra__.keys())}"
            )
            logger.debug("Full JSON", json=json.dumps(data, default=str))


class NetworkInfo(WarnExtraFieldsModel):
    """Network configuration details."""

    hostname: str | None = None
    ipv4: str | None = None
    ipv6: str | None = None
    mac: str | None = None
    wifi_ssid: str | None = None
    lan_ipv4: str | None = None
    lan_mac: str | None = None


class SourceInfo(WarnExtraFieldsModel):
    """Information about the source of an action or object (e.g., user)."""

    id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    public_name: str | None = None
    avatar: str | None = None

    @pydantic.field_validator("avatar")
    @classmethod
    def resolve_avatar_url(cls, v: typing.Any) -> typing.Any:
        """Automatically prepend MEDIA_BASE_URL if missing."""
        if isinstance(v, str) and v and not v.startswith(("http://", "https://")):
            return f"{consts.MEDIA_BASE_URL}{v.lstrip('/')}"
        return v


class Owner(SourceInfo):
    """Represents the owner of a resource (same fields as SourceInfo)."""

    pass


class SyncInfo(WarnExtraFieldsModel):
    """Synchronization details for a resource."""

    synced_by: dict[str, typing.Any] | None = None
    synced: datetime.datetime | None = None
    source: str | None = None
