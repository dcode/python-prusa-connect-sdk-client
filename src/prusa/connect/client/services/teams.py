"""Service for Team operations."""

import json

import structlog

from prusa.connect.client import models
from prusa.connect.client.services.base import BaseService

logger = structlog.get_logger(__name__)


class TeamService(BaseService):
    """Service for managing teams."""

    def list_teams(self, limit: int = 50, offset: int = 0) -> list[models.Team]:
        """Fetch all teams associated with the account.

        Args:
            limit: Maximum number of teams to return.
            offset: Number of teams to skip.

        Returns:
            A list of `Team` objects.
        """
        params = {"limit": limit, "offset": offset}
        data = self._client.request("GET", "/app/users/teams", params=params)
        teams: list[models.Team] = []
        if isinstance(data, dict) and "teams" in data:
            logger.debug("Received teams.", teams=json.dumps(data["teams"], default=str))
            teams = [models.Team.model_validate(t) for t in data["teams"]]
        elif isinstance(data, list):
            logger.debug("Received teams.", teams=json.dumps(data, default=str))
            teams = [models.Team.model_validate(t) for t in data]
        return teams

    def get(self, team_id: int) -> models.Team:
        """Fetch detailed information for a specific team.

        Args:
            team_id: The ID of the team.

        Returns:
            A `Team` object.
        """
        data = self._client.request("GET", f"/app/users/teams/{team_id}")
        return models.Team.model_validate(data)

    def list_users(self, team_id: int) -> list[models.TeamUser]:
        """Fetch all users associated with a team.

        Args:
            team_id: The ID of the team.

        Returns:
            A list of `TeamUser` objects.
        """
        team = self.get(team_id)
        return team.users or []

    def list_printers(self, team_id: int) -> list[models.Printer]:
        """Fetch all printers associated with a team.

        Args:
            team_id: The ID of the team.

        Returns:
            A list of `Printer` objects.
        """
        data = self._client.request("GET", "/app/printers", params={"team_id": team_id})
        return [models.Printer.model_validate(p) for p in data]

    def add_user(
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
        self._client.request("POST", f"/app/teams/{team_id}/add-user", json=payload)
        return True
