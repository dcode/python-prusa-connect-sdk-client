"""Service for Statistics operations."""

import datetime

import pydantic
import structlog

from prusa.connect.client import models
from prusa.connect.client.services.base import BaseService

logger = structlog.get_logger(__name__)


def _to_timestamp(val: datetime.date | int | None, end: bool = False) -> int | None:
    """Helper to convert date/datetime or int to unix timestamp."""
    if val is None:
        return None
    if isinstance(val, datetime.datetime):
        return int(val.timestamp())
    if isinstance(val, datetime.date):
        return int(
            datetime.datetime.combine(
                val, datetime.time.min if not end else datetime.time.max, tzinfo=datetime.UTC
            ).timestamp()
        )
    return val


class StatsService(BaseService):
    """Service for managing statistics."""

    def get_material(
        self,
        printer_uuid: str,
        from_time: datetime.date | int | None = None,
        to_time: datetime.date | int | None = None,
    ) -> models.MaterialQuantity:
        """Fetch material quantity statistics for a printer."""
        params = {}
        if from_time is not None:
            params["from"] = _to_timestamp(from_time)
        if to_time is not None:
            params["to"] = _to_timestamp(to_time)

        data = self._client.request("GET", f"/app/stats/printers/{printer_uuid}/material_quantity", params=params)
        return models.MaterialQuantity.model_validate(data)

    def get_usage(
        self,
        printer_uuid: str,
        from_time: datetime.date | int | None = None,
        to_time: datetime.date | int | None = None,
    ) -> models.PrintingNotPrinting:
        """Fetch printing vs not printing statistics for a printer."""
        params = {}
        if from_time is not None:
            params["from"] = _to_timestamp(from_time)
        if to_time is not None:
            params["to"] = _to_timestamp(to_time)

        data = self._client.request("GET", f"/app/stats/printers/{printer_uuid}/printing_not_printing", params=params)
        return models.PrintingNotPrinting.model_validate(data)

    def get_planned_tasks(
        self,
        printer_uuid: str,
        from_time: datetime.date | int | None = None,
        to_time: datetime.date | int | None = None,
    ) -> models.PlannedTasks:
        """Fetch planned tasks statistics for a printer."""
        params = {}
        if from_time is not None:
            params["from"] = _to_timestamp(from_time)
        if to_time is not None:
            params["to"] = _to_timestamp(to_time)

        data = self._client.request("GET", f"/app/stats/printers/{printer_uuid}/planned_tasks", params=params)
        return models.PlannedTasks.model_validate(data)

    def get_jobs_success(
        self,
        printer_uuid: str,
        from_time: datetime.date | int | None = None,
        to_time: datetime.date | int | None = None,
    ) -> models.JobsSuccess:
        """Fetch jobs success statistics for a printer."""
        params = {}
        if from_time is not None:
            params["from"] = _to_timestamp(from_time)
        if to_time is not None:
            params["to"] = _to_timestamp(to_time)

        data = self._client.request("GET", f"/app/stats/printers/{printer_uuid}/jobs_success", params=params)
        try:
            return models.JobsSuccess.model_validate(data)
        except pydantic.ValidationError as e:
            logger.error("Jobs success stats validation error", error=e)
            raise
