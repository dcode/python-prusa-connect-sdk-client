"""Service for Job operations."""

import structlog

from prusa.connect.client import models
from prusa.connect.client.services.base import BaseService

logger = structlog.get_logger(__name__)


class JobService(BaseService):
    """Service for managing jobs."""

    def list_team_jobs(
        self, team_id: int, state: list[str] | None = None, limit: int | None = None
    ) -> list[models.Job]:
        """Fetch job history for a team.

        Since the API does not provide a direct endpoint for team jobs,
        this method aggregates jobs from all printers in the team.
        """
        printers = self._client.teams.list_printers(team_id)
        all_jobs: list[models.Job] = []

        for printer in printers:
            if not printer.uuid:
                continue
            try:
                # Fetch more than 'limit' from each printer to allow better global sort if needed,
                # but for simplicity we'll just take 'limit' or default.
                jobs = self.list_printer_jobs(printer.uuid, state=state, limit=limit)
                all_jobs.extend(jobs)
            except Exception as e:
                logger.warning(
                    "Failed to fetch jobs for printer in team",
                    printer_uuid=printer.uuid,
                    team_id=team_id,
                    error=str(e),
                )

        # Sort aggregated jobs by end time (descending)
        all_jobs.sort(key=lambda j: (j.end or 0, j.start or 0, j.id or 0), reverse=True)

        if limit is not None:
            all_jobs = all_jobs[:limit]

        return all_jobs

    def list_printer_jobs(
        self, printer_uuid: str, state: list[str] | None = None, limit: int | None = None
    ) -> list[models.Job]:
        """Fetch job history for a printer."""
        data = self._client.request("GET", f"/app/printers/{printer_uuid}/jobs")
        jobs: list[models.Job] = []
        if isinstance(data, dict) and "jobs" in data:
            jobs = [models.Job.model_validate(j) for j in data["jobs"]]

        if state:
            state_set = set(state)
            jobs = [j for j in jobs if j.state in state_set]

        if limit is not None:
            jobs = jobs[:limit]

        return jobs

    def get_queue(self, printer_uuid: str, limit: int = 100, offset: int = 0) -> list[models.Job]:
        """Fetch the print queue for a printer."""
        data = self._client.request(
            "GET", f"/app/printers/{printer_uuid}/queue", params={"limit": limit, "offset": offset}
        )

        if isinstance(data, dict):
            if "planned_jobs" in data:
                return [models.Job.model_validate(j) for j in data["planned_jobs"]]
            if "jobs" in data:
                return [models.Job.model_validate(j) for j in data["jobs"]]
            if "queue" in data:
                return [models.Job.model_validate(j) for j in data["queue"]]
            if "id" in data and "state" in data:
                return [models.Job.model_validate(data)]

        elif isinstance(data, list):
            return [models.Job.model_validate(j) for j in data]

        return []
