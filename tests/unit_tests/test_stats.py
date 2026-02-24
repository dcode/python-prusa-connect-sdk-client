import datetime
from collections.abc import MutableMapping

import pytest
import responses

from prusa.connect.client import PrusaConnectClient


class MockCredentials:
    """A dummy authentication strategy for testing."""

    def before_request(self, headers: MutableMapping[str, str | bytes]) -> None:
        headers["Authorization"] = "Bearer mock_token"


@pytest.fixture
def client():
    return PrusaConnectClient(credentials=MockCredentials())


@responses.activate
def test_get_printer_usage_stats(client):
    uuid = "test-uuid"
    responses.add(
        responses.GET,
        f"https://connect.prusa3d.com/app/stats/printers/{uuid}/printing_not_printing",
        json={
            "name": "printer-name",
            "uuid": uuid,
            "data": [{"name": "printing", "value": 10}, {"name": "not_printing", "value": 90}],
            "from": 12345,
            "to": 67890,
        },
        status=200,
    )

    stats = client.get_printer_usage_stats(uuid)
    assert stats.printer_name == "printer-name"
    assert len(stats.data) == 2
    assert stats.data[0].name == "printing"
    assert stats.data[0].duration.total_seconds() == 10.0
    assert isinstance(stats.from_time, datetime.date)


@responses.activate
def test_get_printer_material_stats(client):
    uuid = "test-uuid"
    responses.add(
        responses.GET,
        f"https://connect.prusa3d.com/app/stats/printers/{uuid}/material_quantity",
        json={
            "name": "printer-name",
            "uuid": uuid,
            "data": [{"name": "PLA", "value": 150}],
            "from": 12345,
            "to": 67890,
        },
        status=200,
    )

    stats = client.get_printer_material_stats(uuid)
    assert stats.printer_name == "printer-name"
    assert len(stats.data) == 1
    assert stats.data[0]["name"] == "PLA"


@responses.activate
def test_get_printer_planned_tasks_stats(client):
    uuid = "test-uuid"
    responses.add(
        responses.GET,
        f"https://connect.prusa3d.com/app/stats/printers/{uuid}/planned_tasks",
        json={
            "xAxis": [0, 1],
            "series": {"uuid": uuid, "name": "printer-name", "data": [[0, 5], [1, 2]]},
            "from": 12345,
            "to": 67890,
        },
        status=200,
    )

    stats = client.get_printer_planned_tasks_stats(uuid)
    assert stats.series.printer_name == "printer-name"
    assert stats.time_axis == [0, 1]
    assert stats.series.data[0] == (0, 5)


@responses.activate
def test_get_printer_jobs_success_stats(client):
    uuid = "test-uuid"
    responses.add(
        responses.GET,
        f"https://connect.prusa3d.com/app/stats/printers/{uuid}/jobs_success",
        json={
            "xAxis": ["2026-02-13"],
            "name": "printer-name",
            "uuid": uuid,
            "series": [{"name": "FIN_OK", "data": [5]}],
            "from": 12345,
            "to": 67890,
            "time_shift": "+00:00",
        },
        status=200,
    )

    stats = client.get_printer_jobs_success_stats(uuid)
    assert stats.printer_name == "printer-name"
    assert stats.date_axis == ["2026-02-13"]
    assert stats.series[0].status == "FIN_OK"
    assert stats.series[0].data == [5]
