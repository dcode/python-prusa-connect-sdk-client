"""Stats models for Prusa Connect SDK."""

import datetime
import functools
import typing
from enum import StrEnum

import pydantic

from .common import WarnExtraFieldsModel

_job_status_order_map: dict["JobStatus", int] | None = None


@functools.total_ordering
class JobStatus(StrEnum):
    """Enum representing the status of a job."""

    PRINTING = "PRINTING"
    FINISHED = "FINISHED"

    OK = "FIN_OK"
    STOPPED = "FIN_STOPPED"
    ERROR = "FIN_ERROR"
    UNKNOWN = "FIN_UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> typing.Any:
        return cls.UNKNOWN

    @classmethod
    def get_order(cls, member: "JobStatus") -> int:
        """Get the index of the member in the order of declaration."""
        global _job_status_order_map
        if _job_status_order_map is None:
            _job_status_order_map = {m: i for i, m in enumerate(cls)}
        return _job_status_order_map[member]

    def __lt__(self, other):
        """Compare two JobStatus members by order of declaration."""
        if self.__class__ is other.__class__:
            return self.get_order(self) < self.get_order(other)
        return NotImplemented


class StatsModel(WarnExtraFieldsModel):
    """Base model for statistics with date validation."""

    from_time: datetime.date = pydantic.Field(..., alias="from")
    to_time: datetime.date = pydantic.Field(..., alias="to")

    @pydantic.field_validator("from_time", "to_time", mode="before")
    @classmethod
    def _validate_date(cls, v):
        if isinstance(v, (int, float)):
            return datetime.datetime.fromtimestamp(v, datetime.UTC).date()
        return v


class PrintingNotPrintingEntry(WarnExtraFieldsModel):
    """Represents a single entry in printing vs not printing stats."""

    name: str
    value: int


class PrintingNotPrinting(StatsModel):
    """Printer usage statistics: printing vs not printing."""

    printer_name: str = pydantic.Field(..., alias="name")
    printer_uuid: str = pydantic.Field(..., alias="uuid")
    data: list[PrintingNotPrintingEntry]


class MaterialQuantity(StatsModel):
    """Printer usage statistics: material quantity used."""

    printer_name: str = pydantic.Field(..., alias="name")
    printer_uuid: str = pydantic.Field(..., alias="uuid")
    data: list[typing.Any]


class PlannedTasksSeries(WarnExtraFieldsModel):
    """Series data for planned tasks."""

    printer_uuid: str = pydantic.Field(..., alias="uuid")
    printer_name: str = pydantic.Field(..., alias="name")
    data: list[tuple[int, int]]


class PlannedTasks(StatsModel):
    """Printer usage statistics: planned tasks."""

    time_axis: list[int] = pydantic.Field(
        ..., alias="xAxis", validation_alias=pydantic.AliasChoices("xAxis", "time_axis"), description="Time axis"
    )
    series: PlannedTasksSeries


class JobsSuccessSeries(WarnExtraFieldsModel):
    """Series data for job success stats."""

    status: JobStatus = pydantic.Field(..., alias="name")
    data: list[int]


class JobsSuccess(StatsModel):
    """Printer usage statistics: job success history."""

    date_axis: list[str] = pydantic.Field(
        ..., alias="xAxis", validation_alias=pydantic.AliasChoices("xAxis", "date_axis"), description="Date axis"
    )
    printer_name: str = pydantic.Field(..., alias="name")
    printer_uuid: str = pydantic.Field(..., alias="uuid")
    series: list[JobsSuccessSeries]
    time_shift: str
