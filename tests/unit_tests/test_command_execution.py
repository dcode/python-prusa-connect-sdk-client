from unittest.mock import MagicMock

import pytest

from prusa.connect.client import PrusaConnectClient
from prusa.connect.client.command_models import CommandArgument, CommandDefinition


@pytest.fixture
def mock_client():
    client = PrusaConnectClient(credentials=MagicMock(), base_url="http://mock")
    client._session = MagicMock()
    return client


def test_get_supported_commands(mock_client):
    # Mock response
    mock_data = {
        "commands": [
            {
                "command": "MOVE_Z",
                "args": [{"name": "distance", "type": "number", "required": True}],
                "executable_from_state": ["IDLE"],
            },
            {"command": "STOP_PRINT", "args": []},
            {"command": "PAUSE_PRINT", "args": []},
        ]
    }
    mock_client._session.request.return_value.json.return_value = mock_data
    mock_client._session.request.return_value.status_code = 200

    cmds = mock_client.get_supported_commands("printer1")

    assert len(cmds) == 3
    assert cmds[0].command == "MOVE_Z"
    assert cmds[0].args[0].name == "distance"

    # Verify cache
    assert "printer1" in mock_client.printers._supported_commands_cache
    assert mock_client.printers._supported_commands_cache["printer1"] == cmds

    # Verify no second request
    mock_client.get_supported_commands("printer1")
    assert mock_client._session.request.call_count == 1


def test_execute_printer_command_valid(mock_client):
    # Setup cache
    cmd_def = CommandDefinition(command="MOVE_Z", args=[CommandArgument(name="distance", type="number", required=True)])
    stop_def = CommandDefinition(command="STOP_PRINT", args=[])
    pause_def = CommandDefinition(command="PAUSE_PRINT", args=[])
    mock_client.printers._supported_commands_cache["printer1"] = [cmd_def, stop_def, pause_def]

    # Execute valid
    mock_client._session.request.return_value.status_code = 200
    mock_client.execute_printer_command("printer1", "MOVE_Z", {"distance": 10.5})

    # Verify call
    mock_client._session.request.assert_called_with(
        "POST",
        "http://mock/app/printers/printer1/commands/sync",
        json={"command": "MOVE_Z", "kwargs": {"distance": 10.5}},
        timeout=30.0,
    )


def test_execute_printer_command_invalid_missing_arg(mock_client):
    cmd_def = CommandDefinition(command="MOVE_Z", args=[CommandArgument(name="distance", type="number", required=True)])
    mock_client.printers._supported_commands_cache["printer1"] = [
        cmd_def,
        CommandDefinition(command="STOP_PRINT"),
        CommandDefinition(command="PAUSE_PRINT"),
    ]

    with pytest.raises(ValueError, match="Missing required argument 'distance'"):
        mock_client.execute_printer_command("printer1", "MOVE_Z", {})


def test_execute_printer_command_invalid_type(mock_client):
    cmd_def = CommandDefinition(command="MOVE_Z", args=[CommandArgument(name="distance", type="number", required=True)])
    mock_client.printers._supported_commands_cache["printer1"] = [
        cmd_def,
        CommandDefinition(command="STOP_PRINT"),
        CommandDefinition(command="PAUSE_PRINT"),
    ]

    with pytest.raises(ValueError, match="must be a number"):
        mock_client.execute_printer_command("printer1", "MOVE_Z", {"distance": "bad"})


def test_execute_printer_command_unsupported(mock_client):
    mock_client.printers._supported_commands_cache["printer1"] = []

    with pytest.raises(ValueError, match="not supported"):
        mock_client.execute_printer_command("printer1", "UNKNOWN_CMD")
