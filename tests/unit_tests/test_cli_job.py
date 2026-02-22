import contextlib
from unittest.mock import MagicMock, patch

import pytest

from prusa.connect.client import PrusaConnectClient
from prusa.connect.client.cli import app
from prusa.connect.client.models import Job, Printer

SAMPLE_JOB = {
    "id": 100,
    "printer_uuid": "printer-1",
    "state": "FINISHED",
    "progress": 100,
    "start": 1672531200,
    "end": 1672534800,
    "file": {"name": "test.gcode", "size": 1024, "type": "PRINT_FILE"},
}


@pytest.fixture
def mock_client():
    with patch("prusa.connect.client.cli.commands.job.common.get_client") as mock:
        client = MagicMock(spec=PrusaConnectClient)
        client.printers = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_settings():
    with patch("prusa.connect.client.cli.commands.job.config.settings") as s_mock:
        s_mock.default_printer_id = "printer-1"
        yield s_mock


def test_job_list_printer(mock_client):
    mock_client.get_printer_jobs.return_value = [Job.model_validate(SAMPLE_JOB)]

    with contextlib.suppress(SystemExit):
        app(["job", "list", "--printer", "printer-1"], exit_on_error=False)

    mock_client.get_printer_jobs.assert_called()


def test_job_list_team(mock_client):
    mock_client.get_team_jobs.return_value = [Job.model_validate(SAMPLE_JOB)]

    with contextlib.suppress(SystemExit):
        app(["job", "list", "--team", "1"], exit_on_error=False)

    mock_client.get_team_jobs.assert_called()


def test_job_list_aggregate(mock_client):
    # Mocking printers.list_printers and then get_printer_jobs for each
    mock_client.printers.list_printers.return_value = [Printer.model_validate({"uuid": "p1", "name": "Pr1"})]
    mock_client.get_printer_jobs.return_value = [Job.model_validate(SAMPLE_JOB)]

    with contextlib.suppress(SystemExit):
        app(["job", "list"], exit_on_error=False)

    mock_client.printers.list_printers.assert_called()
    mock_client.get_printer_jobs.assert_called()


def test_job_queued(mock_client):
    mock_client.get_printer_queue.return_value = [Job.model_validate(SAMPLE_JOB)]
    with contextlib.suppress(SystemExit):
        app(["job", "queued", "--printer", "printer-1"], exit_on_error=False)
    mock_client.get_printer_queue.assert_called_with("printer-1")


def test_job_show(mock_client, mock_settings):
    mock_client.get_job.return_value = Job.model_validate(SAMPLE_JOB)
    with contextlib.suppress(SystemExit):
        app(["job", "show", "100"], exit_on_error=False)
    mock_client.get_job.assert_called_with("printer-1", 100)


def test_job_show_missing_printer(mock_client):
    with patch("prusa.connect.client.cli.commands.job.config.settings") as s_mock:
        s_mock.default_printer_id = None
        with contextlib.suppress(SystemExit):
            app(["job", "show", "100"], exit_on_error=False)
