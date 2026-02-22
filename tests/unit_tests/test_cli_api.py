import contextlib
import io
import json
from unittest.mock import MagicMock, patch

import pytest
import requests
import responses

from prusa.connect.client import PrusaConnectClient
from prusa.connect.client.cli import app


@pytest.fixture
def mock_client():
    with patch("prusa.connect.client.cli.commands.api.common.get_client") as mock:
        client = MagicMock(spec=PrusaConnectClient)
        mock.return_value = client
        yield client


def test_api_command_json(mock_client):
    mock_client._request.return_value = {"status": "ok"}

    with contextlib.suppress(SystemExit):
        app(["api", "/app/printers"], exit_on_error=False)

    mock_client._request.assert_called_with("GET", "/app/printers", raw=True)


def test_api_command_post_data(mock_client):
    mock_client._request.return_value = {"status": "ok"}

    with contextlib.suppress(SystemExit):
        app(["api", "/app/printers", "--method", "POST", "--data", '{"name": "new"}'], exit_on_error=False)

    mock_client._request.assert_called_with("POST", "/app/printers", raw=True, json={"name": "new"})


@responses.activate
def test_api_command_output_file(mock_client, tmp_path):
    out_file = tmp_path / "out.json"

    # Mock return value since we're using a mock client
    mock_client._request.return_value = requests.Response()
    mock_client._request.return_value.status_code = 200
    mock_client._request.return_value._content = json.dumps({"status": "ok"}).encode()
    mock_client._request.return_value.headers["Content-Type"] = "application/json"

    with contextlib.suppress(SystemExit):
        app(["api", "/app/printers", "--output", str(out_file)], exit_on_error=False)

    assert out_file.exists()
    assert json.loads(out_file.read_text()) == {"status": "ok"}


@responses.activate
def test_api_command_stream(mock_client, tmp_path):
    out_file = tmp_path / "stream.bin"

    # Mock return value since we're using a mock client
    mock_res = requests.Response()
    mock_res.status_code = 200
    mock_res.raw = io.BytesIO(b"chunk1chunk2")
    mock_client._request.return_value = mock_res

    with contextlib.suppress(SystemExit):
        app(["api", "/app/download", "--stream", "--output", str(out_file)], exit_on_error=False)

    assert out_file.read_bytes() == b"chunk1chunk2"
