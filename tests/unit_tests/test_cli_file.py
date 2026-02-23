import contextlib
import os
from unittest.mock import MagicMock, patch

import pytest

from prusa.connect.client import PrusaConnectClient, models
from prusa.connect.client.cli import app
from prusa.connect.client.models import PrintFile

SAMPLE_TEAM_FILE = {"name": "test.gcode", "type": "PRINT_FILE", "size": 2048, "hash": "hash123"}


@pytest.fixture
def mock_client():
    with patch("prusa.connect.client.cli.commands.file.common.get_client") as mock:
        client = MagicMock(spec=PrusaConnectClient)
        mock.return_value = client
        yield client


@pytest.fixture
def mock_settings():
    with patch("prusa.connect.client.cli.commands.file.config.settings") as s_mock:
        s_mock.default_team_id = 1
        yield s_mock


def test_file_list(mock_client, mock_settings):
    mock_client.get_file_list.return_value = [PrintFile.model_validate(SAMPLE_TEAM_FILE)]

    with contextlib.suppress(SystemExit):
        app(["file", "list"], exit_on_error=False)

    mock_client.get_file_list.assert_called_with(1)

    # With explicit team
    with contextlib.suppress(SystemExit):
        app(["file", "list", "2"], exit_on_error=False)
    mock_client.get_file_list.assert_called_with(2)


def test_file_upload(mock_client, mock_settings, tmp_path):
    local_file = tmp_path / "test.gcode"
    local_file.write_text("dummy gcode")

    mock_client.initiate_team_upload.return_value = models.UploadStatus(
        id=123, team_id=1, name="test.gcode", size=11, state="STARTED"
    )

    with contextlib.suppress(SystemExit):
        app(["file", "upload", str(local_file), "--team-id", "1"], exit_on_error=False)

    mock_client.initiate_team_upload.assert_called_with(1, "/", "test.gcode", 11)
    mock_client.upload_team_file.assert_called()


def test_file_download(mock_client, mock_settings, tmp_path):
    os.chdir(tmp_path)
    mock_client.download_team_file.return_value = b"file content"

    with contextlib.suppress(SystemExit):
        app(["file", "download", "hash123", "--output", "out.gcode"], exit_on_error=False)

    mock_client.download_team_file.assert_called_with(1, "hash123")
    assert (tmp_path / "out.gcode").read_bytes() == b"file content"


def test_file_show(mock_client, mock_settings):
    mock_client.get_team_file.return_value = PrintFile.model_validate(SAMPLE_TEAM_FILE)

    # Simple show
    with contextlib.suppress(SystemExit):
        app(["file", "show", "hash123"], exit_on_error=False)
    mock_client.get_team_file.assert_called_with(1, "hash123")

    # Detailed show
    with contextlib.suppress(SystemExit):
        app(["file", "show", "hash123", "--detailed"], exit_on_error=False)
    mock_client.get_team_file.assert_called_with(1, "hash123")
