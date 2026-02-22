import contextlib
from unittest.mock import MagicMock, patch

import pytest

from prusa.connect.client import PrusaConnectClient, models
from prusa.connect.client.cli import app
from prusa.connect.client.models import Printer, Team

SAMPLE_PRINTER = {
    "uuid": "printer-1",
    "name": "MK4-1",
    "printer_state": "IDLE",
    "printer_model": "MK4",
    "team_name": "Team A",
}


@pytest.fixture
def mock_client():
    # Mock multiple common.get_client calls in different modules if necessary
    with (
        patch("prusa.connect.client.cli.commands.printer.common.get_client") as p_mock,
        patch("prusa.connect.client.cli.commands.file.common.get_client") as f_mock,
    ):
        client = MagicMock(spec=PrusaConnectClient)
        p_mock.return_value = client
        f_mock.return_value = client
        yield client


@pytest.fixture
def mock_settings():
    with patch("prusa.connect.client.cli.commands.printer.config.settings") as s_mock:
        s_mock.default_printer_id = "default-uuid"
        yield s_mock


def test_printer_list(mock_client):
    mock_client.get_printers.return_value = [Printer.model_validate(SAMPLE_PRINTER)]

    with contextlib.suppress(SystemExit):
        app(["printer", "list"], exit_on_error=False)

    # Test alias
    with contextlib.suppress(SystemExit):
        app(["printers"], exit_on_error=False)

    # Test pattern
    with contextlib.suppress(SystemExit):
        app(["printer", "list", "--pattern", "MK*"], exit_on_error=False)

    assert mock_client.get_printers.call_count == 3


def test_printer_pause_resume(mock_client, mock_settings):
    mock_client.send_command.return_value = True

    # Explicit ID
    with contextlib.suppress(SystemExit):
        app(["printer", "pause", "printer-1"], exit_on_error=False)
    mock_client.send_command.assert_called_with("printer-1", "PAUSE_PRINT")

    # Default ID
    with contextlib.suppress(SystemExit):
        app(["printer", "resume"], exit_on_error=False)
    mock_client.send_command.assert_called_with("default-uuid", "RESUME_PRINT")


def test_printer_stop(mock_client, mock_settings):
    mock_client.stop_print.return_value = True
    mock_client.get_printer.return_value = Printer.model_validate({**SAMPLE_PRINTER, "job_info": {"id": 123}})
    mock_client.set_job_failure_reason.return_value = True

    # Simple stop
    with contextlib.suppress(SystemExit):
        app(["printer", "stop", "printer-1"], exit_on_error=False)
    mock_client.stop_print.assert_called_with("printer-1")

    # Stop with reason
    with contextlib.suppress(SystemExit):
        app(["printer", "stop", "printer-1", "--reason", "SPAGHETTI_MONSTER", "--note", "oops"], exit_on_error=False)
    mock_client.set_job_failure_reason.assert_called_with(
        "printer-1", 123, models.JobFailureTag.SPAGHETTI_MONSTER, "oops"
    )


def test_printer_cancel_object(mock_client, mock_settings):
    mock_client.cancel_object.return_value = True
    with contextlib.suppress(SystemExit):
        app(["printer", "cancel-object", "1", "printer-1"], exit_on_error=False)
    mock_client.cancel_object.assert_called_with("printer-1", 1)


def test_printer_move(mock_client, mock_settings):
    mock_client.move_axis.return_value = True
    with contextlib.suppress(SystemExit):
        app(["printer", "move", "--x", "10", "--speed", "100"], exit_on_error=False)
    mock_client.move_axis.assert_called_with("default-uuid", x=10.0, y=None, z=None, e=None, speed=100.0)


def test_printer_flash(mock_client, mock_settings):
    mock_client.flash_firmware.return_value = True
    with contextlib.suppress(SystemExit):
        app(["printer", "flash", "/usb/fw.bbf", "printer-1"], exit_on_error=False)
    mock_client.flash_firmware.assert_called_with("printer-1", "/usb/fw.bbf")


def test_printer_commands(mock_client, mock_settings):
    from prusa.connect.client.command_models import CommandArgument, CommandDefinition

    cmd = CommandDefinition(
        command="G28", description="Home", args=[CommandArgument(name="axes", type="string", required=False)]
    )
    mock_client.get_supported_commands.return_value = [cmd]

    with contextlib.suppress(SystemExit):
        app(["printer", "commands", "printer-1"], exit_on_error=False)
    mock_client.get_supported_commands.assert_called_with("printer-1")


def test_printer_execute_command(mock_client, mock_settings):
    from prusa.connect.client.command_models import CommandArgument, CommandDefinition

    cmd = CommandDefinition(
        command="MOVE_Z",
        args=[
            CommandArgument(name="z", type="number", required=True),
            CommandArgument(name="speed", type="integer", required=False),
            CommandArgument(name="active", type="boolean", required=False),
        ],
    )
    mock_client.get_supported_commands.return_value = [cmd]
    mock_client.execute_printer_command.return_value = True

    # Using flags
    with contextlib.suppress(SystemExit):
        app(["printer", "command", "MOVE_Z", "--z", "10.5", "--speed", "100", "--active", "true"], exit_on_error=False)
    mock_client.execute_printer_command.assert_called()
    args = mock_client.execute_printer_command.call_args[0][2]
    assert args["z"] == 10.5
    assert args["speed"] == 100
    assert args["active"] is True

    # Using JSON --args
    with contextlib.suppress(SystemExit):
        app(["printer", "command", "MOVE_Z", "--args", '{"z": 5.0}'], exit_on_error=False)
    args_json = mock_client.execute_printer_command.call_args[0][2]
    assert args_json["z"] == 5.0


def test_printer_storages(mock_client, mock_settings):
    mock_client.get_printer_storages.return_value = [
        models.Storage(name="USB", type="USB", path="/usb", free_space=1024 * 1024 * 1024)
    ]
    with contextlib.suppress(SystemExit):
        app(["printer", "storages", "printer-1"], exit_on_error=False)
    mock_client.get_printer_storages.assert_called_with("printer-1")


def test_printer_files_list(mock_client, mock_settings):
    mock_client.get_printer_files.return_value = [models.RegularFile(name="test.txt", path="/usb/test.txt", size=1024)]
    with contextlib.suppress(SystemExit):
        app(["printer", "files", "list", "printer-1"], exit_on_error=False)
    mock_client.get_printer_files.assert_called_with("printer-1")


def test_printer_files_upload_download(mock_client, mock_settings, tmp_path):
    # Setup mocks for printer details and teams
    mock_client.get_printer.return_value = Printer.model_validate(SAMPLE_PRINTER)
    mock_client.get_teams.return_value = [Team(id=1, name="Team A")]
    mock_client.initiate_team_upload.return_value = models.UploadStatus(
        id=99, team_id=1, name="f.gcode", size=10, state="STARTED"
    )

    local_file = tmp_path / "f.gcode"
    local_file.write_text("dummy gcode")

    # Upload
    with contextlib.suppress(SystemExit):
        app(["printer", "files", "upload", str(local_file), "printer-1"], exit_on_error=False)
    mock_client.initiate_team_upload.assert_called()

    # Download
    mock_client.download_team_file.return_value = b"content"
    with contextlib.suppress(SystemExit):
        app(["printer", "files", "download", "hash123", "printer-1"], exit_on_error=False)
    mock_client.download_team_file.assert_called_with(1, "hash123")


def test_set_current_printer():
    with (
        patch("prusa.connect.client.cli.commands.printer.config.save_json_config") as save_mock,
        patch("prusa.connect.client.cli.commands.printer.config.settings") as s_mock,
    ):
        with contextlib.suppress(SystemExit):
            app(["printer", "set-current", "new-u"], exit_on_error=False)
        assert s_mock.default_printer_id == "new-u"
        save_mock.assert_called()


def test_printer_missing_uuid(mock_client):
    with patch("prusa.connect.client.cli.commands.printer.config.settings") as s_mock:
        s_mock.default_printer_id = None
        with contextlib.suppress(SystemExit):
            app(["printer", "pause"], exit_on_error=False)
        # Should print error and return
