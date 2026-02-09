import json
from unittest.mock import MagicMock

import pytest

from prusa.connect.client import PrusaConnectClient


@pytest.fixture
def mock_cache_dir(tmp_path):
    return tmp_path / "prusa_cache"


@pytest.fixture
def mock_client(mock_cache_dir):
    client = PrusaConnectClient(credentials=MagicMock(), base_url="http://mock", cache_dir=mock_cache_dir)
    client._session = MagicMock()
    return client


def test_cache_miss_writes_to_disk(mock_client, mock_cache_dir):
    # Setup mock API response
    printer_uuid = "test-printer-1"
    mock_data = {
        "commands": [
            {"command": "CACHE_TEST", "args": []},
            {"command": "STOP_PRINT", "args": []},
            {"command": "PAUSE_PRINT", "args": []},
        ]
    }
    mock_client._session.request.return_value.json.return_value = mock_data
    mock_client._session.request.return_value.status_code = 200

    # Execute
    mock_client.get_supported_commands(printer_uuid)

    # Verify API called
    mock_client._session.request.assert_called_once()

    # Verify file written
    cache_file = mock_cache_dir / "printers" / printer_uuid / "commands.json"
    assert cache_file.exists()

    saved_data = json.loads(cache_file.read_text())
    assert saved_data == mock_data


def test_cache_hit_reads_from_disk(mock_client, mock_cache_dir):
    # Setup cache file
    printer_uuid = "test-printer-2"
    cache_file = mock_cache_dir / "printers" / printer_uuid / "commands.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    cached_data = {
        "commands": [
            {"command": "DISK_HIT", "args": []},
            {"command": "STOP_PRINT", "args": []},
            {"command": "PAUSE_PRINT", "args": []},
        ]
    }
    cache_file.write_text(json.dumps(cached_data))

    # Execute
    commands = mock_client.get_supported_commands(printer_uuid)

    # Verify API NOT called
    mock_client._session.request.assert_not_called()

    # Verify returned data matches cache
    assert len(commands) == 3
    assert commands[0].command == "DISK_HIT"

    # Verify memory cache is populated
    assert printer_uuid in mock_client._supported_commands_cache


def test_corrupt_cache_falls_back_to_network(mock_client, mock_cache_dir):
    # Setup corrupt file
    printer_uuid = "test-printer-3"
    cache_file = mock_cache_dir / "printers" / printer_uuid / "commands.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("{ not valid json ")

    # Setup mock API
    mock_data = {
        "commands": [
            {"command": "FALLBACK", "args": []},
            {"command": "STOP_PRINT", "args": []},
            {"command": "PAUSE_PRINT", "args": []},
        ]
    }
    mock_client._session.request.return_value.json.return_value = mock_data
    mock_client._session.request.return_value.status_code = 200

    # Execute
    commands = mock_client.get_supported_commands(printer_uuid)

    # Verify API called
    mock_client._session.request.assert_called_once()
    assert commands[0].command == "FALLBACK"
