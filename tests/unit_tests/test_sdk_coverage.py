import datetime
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import requests
import responses

from prusa.connect.client import PrusaConnectClient, auth, exceptions, models
from prusa.connect.client.services.stats import _to_timestamp


class MockCredentials:
    def before_request(self, headers):
        headers["Authorization"] = "Bearer mock_token"


@pytest.fixture
def client():
    with patch("prusa.connect.client.PrusaConnectClient.get_app_config"):
        c = PrusaConnectClient(credentials=MockCredentials())
        c._app_config = MagicMock()

    # Disable retries for testing
    from requests.adapters import HTTPAdapter

    adapter = HTTPAdapter(max_retries=0)
    c._session.mount("https://", adapter)
    c._session.mount("http://", adapter)
    return c


def test_to_timestamp():
    # Test None
    assert _to_timestamp(None) is None

    # Test int
    assert _to_timestamp(123456) == 123456

    # Test datetime
    dt = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.UTC)
    assert _to_timestamp(dt) == int(dt.timestamp())

    # Test date start of day
    d = datetime.date(2023, 1, 1)
    expected_start = int(datetime.datetime(2023, 1, 1, 0, 0, 0, tzinfo=datetime.UTC).timestamp())
    assert _to_timestamp(d) == expected_start

    # Test date end of day
    expected_end = int(datetime.datetime(2023, 1, 1, 23, 59, 59, 999999, tzinfo=datetime.UTC).timestamp())
    assert _to_timestamp(d, end=True) == expected_end


@responses.activate
def test_get_camera_client(client):
    # Mocking PrusaConnectCredentials for the access token extraction logic
    class MockPrusaCredentials(auth.PrusaConnectCredentials):
        def __init__(self):
            class MockToken:
                raw_token = "raw_jwt_token"

            class MockTokens:
                access_token = MockToken()

            self.tokens = MockTokens()  # type: ignore

        def before_request(self, headers):
            pass

    client_with_creds = PrusaConnectClient(credentials=MockPrusaCredentials())
    cam = client_with_creds.get_camera_client("cam123")
    assert cam.camera_token == "cam123"
    assert cam.jwt_token == "raw_jwt_token"

    # Test with signaling_url override
    cam2 = client_with_creds.get_camera_client("cam456", signaling_url="https://signaling.example.com")
    assert cam2.camera_token == "cam456"

    # Test with non-PrusaConnectCredentials (no JWT)
    client_no_jwt = PrusaConnectClient(credentials=MockCredentials())
    cam3 = client_no_jwt.get_camera_client("cam789")
    assert cam3.camera_token == "cam789"
    assert cam3.jwt_token is None


@responses.activate
def test_request_error_body_reading(client):
    responses.add(responses.GET, "https://connect.prusa3d.com/app/error", status=500, body="Critical Error Details")

    with pytest.raises(exceptions.PrusaApiError) as excinfo:
        client.api_request("GET", "/app/error")

    assert "Critical Error Details" in str(excinfo.value.response_body)

    # Test failure to read error body
    responses.add(responses.GET, "https://connect.prusa3d.com/app/error-bad", status=500)
    with MagicMock(spec=requests.Response) as mock_resp:
        mock_resp.status_code = 500
        mock_resp.reason = "Internal Error"
        type(mock_resp).text = PropertyMock(side_effect=Exception("Failed to decode"))
        with MagicMock() as mock_session:
            mock_session.request.return_value = mock_resp
            client._session = mock_session
            with pytest.raises(exceptions.PrusaApiError) as excinfo2:
                client.api_request("GET", "/app/error-bad")
            assert "<could not read error body>" in str(excinfo2.value.response_body)


@responses.activate
def test_get_cameras(client):
    # Test dict response
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/cameras",
        json={"cameras": [{"id": 1, "name": "Camera 1"}]},
        status=200,
    )
    with pytest.warns(DeprecationWarning, match="get_cameras"):
        cameras = client.get_cameras()
    assert len(cameras) == 1
    assert cameras[0].name == "Camera 1"

    # Test list response
    responses.add(
        responses.GET, "https://connect.prusa3d.com/app/cameras-list", json=[{"id": 2, "name": "Camera 2"}], status=200
    )
    # We need to manually call it or change the mock if we want to hit the branch
    # But get_cameras uses "/cameras"
    responses.replace(
        responses.GET, "https://connect.prusa3d.com/app/cameras", json=[{"id": 2, "name": "Camera 2"}], status=200
    )
    with pytest.warns(DeprecationWarning, match="get_cameras"):
        cameras2 = client.get_cameras()
    assert len(cameras2) == 1
    assert cameras2[0].name == "Camera 2"

    # Test empty/unexpected response
    responses.replace(responses.GET, "https://connect.prusa3d.com/app/cameras", json={"something_else": []}, status=200)
    with pytest.warns(DeprecationWarning, match="get_cameras"):
        assert client.get_cameras() == []


@responses.activate
def test_get_teams_and_users(client):
    responses.add(
        responses.GET, "https://connect.prusa3d.com/app/users/teams", json=[{"id": 1, "name": "Team A"}], status=200
    )
    with pytest.warns(DeprecationWarning, match="get_teams"):
        teams = client.get_teams()
    assert len(teams) == 1
    assert teams[0].name == "Team A"

    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/users/teams/1",
        json={
            "id": 1,
            "name": "Team A",
            "users": [
                {
                    "id": 10,
                    "username": "user1",
                    "email": "u1@e.com",
                    "rights_ro": True,
                    "rights_use": True,
                    "rights_rw": True,
                }
            ],
        },
        status=200,
    )
    with pytest.warns(DeprecationWarning, match="get_team"):
        team = client.get_team(1)
    assert team.name == "Team A"

    users = client.get_team_users(1)
    assert len(users) == 1
    assert users[0].username == "user1"


@responses.activate
def test_add_team_user(client):
    responses.add(responses.POST, "https://connect.prusa3d.com/app/teams/1/add-user", status=204)
    assert client.add_team_user(1, "new@user.com", rights_rw=True) is True


@responses.activate
def test_job_management(client):
    # 2. Team Jobs (Aggregation mode)
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers?team_id=1",
        json=[{"uuid": "printer-1", "name": "MK4-1", "team_id": 1}],
        status=200,
    )
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/printer-1/jobs",
        json={"jobs": [{"id": 1690023, "state": "FIN_OK"}]},
        status=200,
    )
    jobs = client.get_team_jobs(1)
    assert len(jobs) == 1
    assert jobs[0].id == 1690023
    assert jobs[0].state == "FIN_OK"

    # state filter
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/printer-1/jobs",
        json={"jobs": [{"id": 100, "state": "FINISHED"}]},
        status=200,
    )
    jobs = client.get_team_jobs(1, state=["FINISHED"])
    assert len(jobs) == 1
    assert jobs[0].id == 100
    assert jobs[0].state == "FINISHED"

    # limit filter
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/printer-1/jobs",
        json={"jobs": [{"id": 101, "state": "FINISHED"}]},
        status=200,
    )
    jobs = client.get_team_jobs(1, limit=5)
    assert len(jobs) == 1
    assert jobs[0].id == 101

    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/printer-uuid/jobs/100",
        json={"id": 100, "state": "FINISHED"},
        status=200,
    )
    job = client.get_job("printer-uuid", 100)
    assert job.id == 100

    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/printer-uuid/jobs",
        json={"jobs": [{"id": 101, "state": "FINISHED"}]},
        status=200,
    )
    jobs = client.get_printer_jobs("printer-uuid", state=["FINISHED"], limit=1)
    assert len(jobs) == 1


@responses.activate
def test_status_and_control(client):
    # send_command
    responses.add(responses.POST, "https://connect.prusa3d.com/app/printers/uuid/commands/sync", status=204)
    assert client.pause_print("uuid") is True
    assert client.resume_print("uuid") is True
    assert client.stop_print("uuid") is True
    assert client.cancel_object("uuid", 1) is True
    assert client.move_axis("uuid", x=10, speed=100) is True
    assert client.flash_firmware("uuid", "/usb/fw.bbf") is True

    # statistics
    common_stats = {"from": 1672531200, "to": 1672617600, "name": "MK4", "uuid": "uuid"}

    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/stats/printers/uuid/material_quantity",
        json={**common_stats, "data": []},
        status=200,
    )
    stats = client.get_printer_material_stats("uuid", from_time=datetime.date(2023, 1, 1))
    assert stats.printer_name == "MK4"

    # usage stats
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/stats/printers/uuid/printing_not_printing",
        json={**common_stats, "data": [{"name": "printing", "value": 100}]},
        status=200,
    )
    u_stats = client.get_printer_usage_stats("uuid", to_time=1672617600)
    assert u_stats.printer_uuid == "uuid"

    # planned tasks
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/stats/printers/uuid/planned_tasks",
        json={**common_stats, "xAxis": [], "series": {"uuid": "uuid", "name": "MK4", "data": []}},
        status=200,
    )
    p_tasks = client.get_printer_planned_tasks_stats("uuid", from_time=1672531200)
    assert len(p_tasks.time_axis) == 0

    # jobs success
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/stats/printers/uuid/jobs_success",
        json={**common_stats, "xAxis": [], "series": [], "time_shift": "0"},
        status=200,
    )
    js_stats = client.get_printer_jobs_success_stats("uuid", to_time=datetime.datetime.now())
    assert js_stats.printer_name == "MK4"


@responses.activate
def test_printer_files_and_storages(client):
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/uuid/files",
        json={"files": [{"name": "test.gcode", "size": 100, "type": "FILE"}]},
        status=200,
    )
    files = client.get_printer_files("uuid")
    assert len(files) == 1

    # Test list response for storages
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/uuid/storages",
        json=[{"name": "USB", "type": "USB", "path": "/usb", "mountpoint": "/usb", "read_only": False}],
        status=200,
    )
    storages = client.get_printer_storages("uuid")
    assert len(storages) == 1
    assert storages[0].name == "USB"

    # Test dict response for storages
    responses.replace(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/uuid/storages",
        json={"storages": [{"name": "SD", "type": "SD", "path": "/sd", "mountpoint": "/sd", "read_only": True}]},
        status=200,
    )
    storages2 = client.get_printer_storages("uuid")
    assert len(storages2) == 1
    assert storages2[0].name == "SD"


@responses.activate
def test_job_failure_reason(client):
    responses.add(responses.PATCH, "https://connect.prusa3d.com/app/printers/uuid/jobs/1", status=204)
    assert client.set_job_failure_reason("uuid", 1, models.JobFailureTag.OTHER, "Test note") is True


@responses.activate
def test_get_printer_queue_quirks(client):
    # Test dictionary with planned_jobs
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/uuid/queue",
        json={"planned_jobs": [{"id": 1, "state": "PLANNED"}]},
        status=200,
    )
    queue = client.get_printer_queue("uuid")
    assert len(queue) == 1

    # Test list format
    responses.replace(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/uuid/queue",
        json=[{"id": 2, "state": "PLANNED"}],
        status=200,
    )
    queue = client.get_printer_queue("uuid")
    assert len(queue) == 1
    assert queue[0].id == 2


@responses.activate
def test_compatibility_error_and_redaction(client):
    # Mock get_supported_commands to trigger missing commands
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/uuid/commands",
        json={"commands": []},
        status=200,
    )
    # Mock get_printer for redaction test
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/uuid",
        json={"uuid": "uuid-123", "name": "Secret Printer", "serial": "SN001", "telemetry": {"temp_nozzle": 200}},
        status=200,
    )

    with pytest.raises(exceptions.PrusaCompatibilityError) as excinfo:
        client.get_supported_commands("uuid")

    report = excinfo.value.report_data
    assert "STOP_PRINT" in excinfo.value.missing_commands
    # Check redaction
    details = report["printer_details"]
    assert details["uuid"] == "[REDACTED]"
    assert details["name"] == "[REDACTED]"
    assert details["serial"] == "[REDACTED]"
    assert details["telemetry"]["temp_nozzle"] == 200


@responses.activate
def test_execute_printer_command_validation(client):
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers/uuid/commands",
        json={
            "commands": [
                {
                    "command": "MOVE_Z",
                    "args": [
                        {"name": "z", "type": "number", "required": True},
                        {"name": "speed", "type": "integer", "required": False},
                        {"name": "msg", "type": "string", "required": False},
                        {"name": "active", "type": "boolean", "required": False},
                    ],
                },
                {"command": "STOP_PRINT", "args": []},
                {"command": "PAUSE_PRINT", "args": []},
            ]
        },
        status=200,
    )

    # Valid call
    responses.add(responses.POST, "https://connect.prusa3d.com/app/printers/uuid/commands/sync", status=204)
    assert (
        client.execute_printer_command("uuid", "MOVE_Z", {"z": 10.5, "speed": 100, "msg": "hi", "active": True}) is True
    )

    # Unsupported command
    with pytest.raises(ValueError, match="is not supported"):
        client.execute_printer_command("uuid", "G28")

    # Missing required arg
    with pytest.raises(ValueError, match="Missing required argument 'z'"):
        client.execute_printer_command("uuid", "MOVE_Z", {"speed": 100})

    # Invalid types
    with pytest.raises(ValueError, match="must be a number"):
        client.execute_printer_command("uuid", "MOVE_Z", {"z": "high"})
    with pytest.raises(ValueError, match="must be an integer"):
        client.execute_printer_command("uuid", "MOVE_Z", {"z": 10, "speed": "fast"})
    with pytest.raises(ValueError, match="must be a string"):
        client.execute_printer_command("uuid", "MOVE_Z", {"z": 10, "msg": 123})
    with pytest.raises(ValueError, match="must be a boolean"):
        client.execute_printer_command("uuid", "MOVE_Z", {"z": 10, "active": 1})


@responses.activate
def test_validate_gcode_wrapper(client, tmp_path):
    # Create a dummy gcode file
    gcode_file = tmp_path / "test.gcode"
    gcode_file.write_text("; HEADER\n; estimated printing time (normal mode) = 1h 2m 3s\n")

    metadata = client.validate_gcode(gcode_file)
    assert metadata.estimated_time == 3723


@responses.activate
def test_cache_save_error_handling(client, tmp_path):
    # Setup client with a cache dir that will fail on mkdir
    bad_cache = tmp_path / "file_not_dir"
    bad_cache.write_text("not a directory")

    client_bad_cache = PrusaConnectClient(credentials=MockCredentials(), cache_dir=bad_cache)

    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/printers",
        json={"printers": [{"uuid": "uuid", "name": "MK4", "state": "IDLE"}]},
        status=200,
    )

    # Should not crash even if cache saving fails
    with pytest.warns(DeprecationWarning, match="get_printers"):
        printers = client_bad_cache.get_printers()
    assert len(printers) == 1


@responses.activate
def test_file_management_more(client):
    responses.add(
        responses.GET,
        "https://connect.prusa3d.com/app/teams/1/files/abc",
        json={"name": "test.gcode", "size": 100, "hash": "abc", "type": "PRINT_FILE"},
        status=200,
    )
    file_info = client.get_team_file(1, "abc")
    assert file_info.hash == "abc"

    responses.add(
        responses.GET, "https://connect.prusa3d.com/app/teams/1/files/abc/raw", body=b"gcode_content", status=200
    )
    content = client.download_team_file(1, "abc")
    assert content == b"gcode_content"


@responses.activate
def test_snapshot(client):
    responses.add(
        responses.GET, "https://connect.prusa3d.com/app/cameras/1/snapshots/last", body=b"image_data", status=200
    )
    snap = client.get_snapshot("1")
    assert snap == b"image_data"

    responses.add(responses.POST, "https://connect.prusa3d.com/app/cameras/camtoken/snapshots", status=204)
    assert client.trigger_snapshot("camtoken") is True


@responses.activate
def test_raw_request(client):
    responses.add(responses.GET, "https://connect.prusa3d.com/app/raw", body="raw content", status=200)
    resp = client._request("GET", "/app/raw", raw=True)
    assert resp.text == "raw content"


def test_request_network_error(client):
    # PrusaNetworkError
    with MagicMock() as mock_session:
        mock_session.request.side_effect = requests.exceptions.ConnectionError("Failed")
        client._session = mock_session
        with pytest.raises(exceptions.PrusaNetworkError):
            client.api_request("GET", "/any")
