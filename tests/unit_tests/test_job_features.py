import contextlib
from unittest.mock import MagicMock, patch

import pytest

cyclopts = pytest.importorskip("cyclopts")
better_exceptions = pytest.importorskip("better_exceptions")

from prusa.connect.client import PrusaConnectClient  # noqa: E402
from prusa.connect.client.cli import app  # noqa: E402
from prusa.connect.client.models import Job, Printer, PrintFile  # noqa: E402


@pytest.fixture
def mock_client():
    with patch("prusa.connect.client.cli.commands.job.common.get_client") as mock:
        client = MagicMock(spec=PrusaConnectClient)
        mock.return_value = client
        yield client


def test_get_printers_caching(tmp_path):
    # Setup
    cache_dir = tmp_path / "cache"
    client = PrusaConnectClient(credentials=MagicMock(), cache_dir=cache_dir)

    # Mock request
    mock_response = {"printers": [{"uuid": "uuid1", "name": "Printer1", "state": "READY", "printer_model": "MK4"}]}

    with patch.object(client, "_request", return_value=mock_response) as mock_req:
        # 1. First call - should hit API
        with pytest.warns(DeprecationWarning, match="get_printers"):
            printers = client.get_printers()
        assert len(printers) == 1
        assert printers[0].uuid == "uuid1"
        assert mock_req.call_count == 1

        # Verify cache file created
        cache_file = cache_dir / "printers" / "list.json"
        assert cache_file.exists()

        # 2. Second call (with API failure) - should use cache
        mock_req.side_effect = Exception("API Down")
        with pytest.warns(DeprecationWarning, match="get_printers"):
            printers_cached = client.get_printers()
        assert len(printers_cached) == 1
        assert printers_cached[0].uuid == "uuid1"


def test_job_filtering():
    client = PrusaConnectClient(credentials=MagicMock())

    # Mock data
    jobs_data = {
        "jobs": [
            {"id": 1, "state": "PRINTING", "file": {"name": "f1", "path": "p1", "type": "PRINT_FILE"}},
            {"id": 2, "state": "FINISHED", "file": {"name": "f2", "path": "p2", "type": "PRINT_FILE"}},
            {"id": 3, "state": "CANCELLED", "file": {"name": "f3", "path": "p3", "type": "PRINT_FILE"}},
        ]
    }

    with patch.object(client, "_request", return_value=jobs_data):
        # 1. Test filtering by state
        filtered = client.get_printer_jobs("uuid", state=["PRINTING"])
        assert len(filtered) == 1
        assert filtered[0].id == 1

        # 2. Test limiting
        limited = client.get_printer_jobs("uuid", limit=2)
        assert len(limited) == 2
        assert limited[1].id == 2


def test_cli_job_list_aggregation(mock_client):
    # Setup mocks
    mock_client.get_printers.return_value = [Printer(uuid="p1", name="Printer 1"), Printer(uuid="p2", name="Printer 2")]

    mock_client.get_printer_jobs.side_effect = [
        [Job(id=1, state="FINISHED", end=100, file=PrintFile(name="j1", path="p"))],  # p1
        [Job(id=2, state="PRINTING", end=None, file=PrintFile(name="j2", path="p"))],  # p2
    ]

    # internal helper to capture output would be nice, but we can verify calls
    # cyclopts testing is a bit integration-heavy, let's just invoke the function if possible
    # or rely on manual verification for output.
    # We can invoke the underlying function directly or via app.

    # We will simulate valid auth by mocking get_client (already done by fixture)

    with contextlib.suppress(SystemExit):
        app(["job", "list"], exit_on_error=False)

    # Verify aggregation
    assert mock_client.get_printers.called
    assert mock_client.get_printer_jobs.call_count == 2
    mock_client.get_printer_jobs.assert_any_call("p1", state=None, limit=None)
    mock_client.get_printer_jobs.assert_any_call("p2", state=None, limit=None)


def test_cli_job_queued(mock_client):
    mock_client.get_printers.return_value = [Printer(uuid="p1", name="Printer 1")]

    # Mock return of get_printer_queue calling the API internally?
    # Actually we mock the client method, so we should test the client method separately
    # or trust the mock.
    # Let's verify the client method parsing logic in a separate test if possible,
    # but here we are testing the CLI.
    # So we just assume get_printer_queue works and returns a list.
    mock_client.get_printer_queue.return_value = [Job(id=1, state="PLANNED", file=PrintFile(name="q1", path="p"))]

    with contextlib.suppress(SystemExit):
        app(["job", "queued"], exit_on_error=False)

    assert mock_client.get_printers.called
    mock_client.get_printer_queue.assert_called_with("p1")


def test_client_queue_parsing():
    client = PrusaConnectClient(credentials=MagicMock())

    # Test GET response style
    with patch.object(
        client,
        "_request",
        return_value={
            "planned_jobs": [{"id": 1, "state": "PLANNED", "file": {"name": "f", "path": "p", "type": "PRINT_FILE"}}]
        },
    ):
        queue = client.get_printer_queue("uuid")
        assert len(queue) == 1
        assert queue[0].id == 1

    # Test Single style (e.g. POST return)
    with patch.object(
        client,
        "_request",
        return_value={"id": 2, "state": "PLANNED", "file": {"name": "f", "path": "p", "type": "PRINT_FILE"}},
    ):
        queue = client.get_printer_queue("uuid")
        assert len(queue) == 1
        assert queue[0].id == 2
