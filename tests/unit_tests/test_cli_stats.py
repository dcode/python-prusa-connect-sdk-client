import contextlib
from unittest.mock import MagicMock, patch

import pytest

from prusa.connect.client import PrusaConnectClient
from prusa.connect.client.cli import app
from prusa.connect.client.models import JobsSuccess, MaterialQuantity, PlannedTasks, PrintingNotPrinting


@pytest.fixture
def mock_client():
    with patch("prusa.connect.client.cli.commands.stats.common.get_client") as mock:
        client = MagicMock(spec=PrusaConnectClient)
        mock.return_value = client
        yield client


@pytest.fixture
def mock_settings():
    with patch("prusa.connect.client.cli.commands.stats.config.settings") as s_mock:
        s_mock.default_printer_id = "uuid-123"
        yield s_mock


def test_stats_usage(mock_client, mock_settings):
    mock_client.get_printer_usage_stats.return_value = PrintingNotPrinting.model_validate(
        {
            "from": 1672531200,
            "to": 1672617600,
            "name": "MK4",
            "uuid": "uuid-123",
            "data": [{"name": "printing", "value": 100}],
        }
    )

    with contextlib.suppress(SystemExit):
        app(["stats", "usage"], exit_on_error=False)

    mock_client.get_printer_usage_stats.assert_called()


def test_stats_material(mock_client, mock_settings):
    mock_client.get_printer_material_stats.return_value = MaterialQuantity.model_validate(
        {
            "from": 1672531200,
            "to": 1672617600,
            "name": "MK4",
            "uuid": "uuid-123",
            "data": [{"name": "PLA", "value": 500}],
        }
    )

    with contextlib.suppress(SystemExit):
        app(["stats", "material", "--days", "10"], exit_on_error=False)

    mock_client.get_printer_material_stats.assert_called()


def test_stats_jobs(mock_client, mock_settings):
    mock_client.get_printer_jobs_success_stats.return_value = JobsSuccess.model_validate(
        {
            "from": 1672531200,
            "to": 1672617600,
            "name": "MK4",
            "uuid": "uuid-123",
            "xAxis": ["2023-01-01"],
            "series": [{"name": "success", "data": [10]}],
            "time_shift": "0",
        }
    )

    with contextlib.suppress(SystemExit):
        app(["stats", "jobs"], exit_on_error=False)

    mock_client.get_printer_jobs_success_stats.assert_called()


def test_stats_planned(mock_client, mock_settings):
    mock_client.get_printer_planned_tasks_stats.return_value = PlannedTasks.model_validate(
        {
            "from": 1672531200,
            "to": 1672617600,
            "name": "MK4",
            "uuid": "uuid-123",
            "xAxis": [],
            "series": {"uuid": "uuid-123", "name": "MK4", "data": [[10, 5]]},
        }
    )

    with contextlib.suppress(SystemExit):
        app(["stats", "planned"], exit_on_error=False)

    mock_client.get_printer_planned_tasks_stats.assert_called()


def test_stats_missing_printer(mock_client):
    with patch("prusa.connect.client.cli.commands.stats.config.settings") as s_mock:
        s_mock.default_printer_id = None
        with contextlib.suppress(SystemExit):
            app(["stats", "usage"], exit_on_error=False)
