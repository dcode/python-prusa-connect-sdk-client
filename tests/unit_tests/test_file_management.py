from collections.abc import MutableMapping

import pytest
import responses

from prusa.connect.client import PrusaConnectClient


class MockCredentials:
    def before_request(self, headers: MutableMapping[str, str | bytes]) -> None:
        headers["Authorization"] = "Bearer mock_token"


@pytest.fixture
def client():
    return PrusaConnectClient(credentials=MockCredentials())


@responses.activate
def test_get_file_list(client):
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/teams/123/files",
        json={
            "files": [
                {"type": "PRINT_FILE", "name": "test.gcode", "path": "/usb/test.gcode", "size": 1024, "hash": "abc"}
            ]
        },
        status=200,
    )

    files = client.get_file_list(team_id=123)
    assert len(files) == 1
    assert files[0].name == "test.gcode"
    assert files[0].size == 1024


@responses.activate
def test_team_upload_flow(client):
    # 1. Initiate
    responses.add(
        responses.POST,
        "https://connect.prusa3d.com/app/users/teams/123/uploads",
        json={"id": 456, "team_id": 123, "name": "test.bgcode", "size": 100, "state": "INITIATED"},
        status=200,
    )

    status = client.initiate_team_upload(123, "/dest", "test.bgcode", 100)
    assert status.id == 456
    assert status.state == "INITIATED"

    # 2. Upload raw
    responses.add(
        responses.PUT,
        "https://connect.prusa3d.com/app/teams/123/files/raw?upload_id=456",
        status=204,
    )

    client.upload_team_file(123, 456, b"raw data", content_type="application/x-bgcode")
    # No error means success


@responses.activate
def test_download_team_file(client):
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/teams/123/files/abc/raw",
        body=b"file content",
        status=200,
    )

    data = client.download_team_file(123, "abc")
    assert data == b"file content"


@responses.activate
def test_get_printer_files(client):
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/uuid-1/files",
        json={"files": [{"type": "PRINT_FILE", "name": "p.gcode", "path": "/usb/p.gcode"}]},
        status=200,
    )

    files = client.get_printer_files("uuid-1")
    assert len(files) == 1
    assert files[0].name == "p.gcode"


@responses.activate
def test_get_printer_storages(client):
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/uuid-1/storages",
        json=[{"type": "USB", "path": "/usb", "name": "USB1", "free_space": 1000}],
        status=200,
    )

    storages = client.get_printer_storages("uuid-1")
    assert len(storages) == 1
    assert storages[0].name == "USB1"
    assert storages[0].type == "USB"
