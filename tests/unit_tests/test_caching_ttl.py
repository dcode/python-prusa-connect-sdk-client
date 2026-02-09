import json
import os
import time
from unittest.mock import MagicMock

import pytest

from prusa.connect.client import PrusaConnectClient


@pytest.fixture
def mock_cache_dir(tmp_path):
    return tmp_path / "prusa_connect_cache"


@pytest.fixture
def mock_client(mock_cache_dir):
    # Set short TTL for testing (1 second)
    client = PrusaConnectClient(credentials=MagicMock(), base_url="http://mock", cache_dir=mock_cache_dir, cache_ttl=1)
    client._session = MagicMock()
    return client


def test_cache_ttl_expiration_commands(mock_client, mock_cache_dir):
    printer_uuid = "ttl-printer"
    cache_file = mock_cache_dir / "printers" / printer_uuid / "commands.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    cached_data = {
        "commands": [
            {"command": "OLD", "args": []},
            {"command": "STOP_PRINT", "args": []},
            {"command": "PAUSE_PRINT", "args": []},
        ]
    }
    cache_file.write_text(json.dumps(cached_data))

    # Set mtime to 2 seconds ago (expired)
    past = time.time() - 2
    os.utime(cache_file, (past, past))

    # Setup mock network response
    network_data = {
        "commands": [
            {"command": "NEW", "args": []},
            {"command": "STOP_PRINT", "args": []},
            {"command": "PAUSE_PRINT", "args": []},
        ]
    }
    mock_client._session.request.return_value.json.return_value = network_data
    mock_client._session.request.return_value.status_code = 200

    # Execute
    commands = mock_client.get_supported_commands(printer_uuid)

    # Should fetch from network
    mock_client._session.request.assert_called_once()
    assert commands[0].command == "NEW"


def test_cache_ttl_hit_commands(mock_client, mock_cache_dir):
    printer_uuid = "ttl-printer-hit"
    cache_file = mock_cache_dir / "printers" / printer_uuid / "commands.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    cached_data = {
        "commands": [
            {"command": "FRESH", "args": []},
            {"command": "STOP_PRINT", "args": []},
            {"command": "PAUSE_PRINT", "args": []},
        ]
    }
    cache_file.write_text(json.dumps(cached_data))

    # Set mtime to now (fresh)
    now = time.time()
    os.utime(cache_file, (now, now))

    # Execute
    commands = mock_client.get_supported_commands(printer_uuid)

    # Should uses cache
    mock_client._session.request.assert_not_called()
    assert commands[0].command == "FRESH"


def test_cache_ttl_expiration_printers(mock_client, mock_cache_dir):
    # Setup cache
    cache_file = mock_cache_dir / "printers" / "list.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cached_printers = {"printers": [{"uuid": "p1", "name": "Cached"}]}
    cache_file.write_text(json.dumps(cached_printers))

    # Set expired
    past = time.time() - 2
    os.utime(cache_file, (past, past))

    # Setup Network Failure
    mock_client._session.request.side_effect = Exception("Network Down")

    # Execute - expect failure because cache is expired
    # get_printers re-raises the original error if cache fails/expires
    with pytest.raises(Exception, match="Network Down"):
        mock_client.get_printers()


def test_cache_ttl_valid_printers_fallback(mock_client, mock_cache_dir):
    # Setup cache
    cache_file = mock_cache_dir / "printers" / "list.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cached_printers = {"printers": [{"uuid": "p1", "name": "Cached"}]}
    cache_file.write_text(json.dumps(cached_printers))

    # Set fresh
    now = time.time()
    os.utime(cache_file, (now, now))

    # Setup Network Failure
    mock_client._session.request.side_effect = Exception("Network Down")

    # Execute - should return cached
    printers = mock_client.get_printers()
    assert len(printers) == 1
    assert printers[0].name == "Cached"
