"""Team models for Prusa Connect SDK."""

import typing
import uuid as uuid_pkg

import pydantic

from .common import WarnExtraFieldsModel


class TeamUser(WarnExtraFieldsModel):
    """User in a team."""

    id: int
    first_name: str | None = None
    last_name: str | None = None
    public_name: str | None = None
    avatar: str | None = None
    rights_ro: bool | None = None
    rights_rw: bool | None = None
    rights_use: bool | None = None


class Team(WarnExtraFieldsModel):
    """Team information."""

    id: int
    name: str
    role: str | None = None
    description: str | None = None
    capacity: int | None = None
    organization_id: uuid_pkg.UUID | None = None
    prusaconnect_api_key: pydantic.SecretStr | None = None
    user_count: int | None = None
    users: list[TeamUser] | None = None
    invitees: list[typing.Any] | None = None
