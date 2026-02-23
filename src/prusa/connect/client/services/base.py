"""Base Service for Prusa Connect SDK modules."""

import typing


class AbstractClient(typing.Protocol):
    """Protocol for the Prusa Connect Client."""

    def request(self, method: str, endpoint: str, **kwargs: typing.Any) -> typing.Any:
        """Make an authenticated request to the API."""
        ...

    printers: typing.Any
    teams: typing.Any
    files: typing.Any
    jobs: typing.Any
    cameras: typing.Any
    stats: typing.Any

    @property
    def config(self) -> typing.Any:
        """The application configuration."""
        ...

    _app_config: typing.Any

    def get_app_config(self) -> typing.Any:
        """Fetch the application configuration."""
        ...


class BaseService:
    """Base class for domain-specific services."""

    def __init__(self, client: AbstractClient):
        """Initialize the service."""
        self._client = client
