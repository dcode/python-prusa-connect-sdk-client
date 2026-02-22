import contextlib
from unittest.mock import MagicMock, patch

import pytest

from prusa.connect.client import PrusaConnectClient, models
from prusa.connect.client.models import Camera

cyclopts = pytest.importorskip("cyclopts")


from prusa.connect.client.cli import app  # noqa: E402

SAMPLE_CAMERA_DATA = {
    "id": 123456,
    "name": "Buddy3D Camera",
    "token": "fake-camera-token-123",
    "origin": "OTHER",
    "config": {
        "resolution": {"width": 1920, "height": 1080},
        "firmware": "3.0.0",
        "model": "Buddy3D",
    },
    "printer_uuid": "printer-uuid-abc-123",
}


@pytest.fixture
def mock_client():
    with patch("prusa.connect.client.cli.commands.camera.common.get_client") as mock:
        client = MagicMock(spec=PrusaConnectClient)
        client.cameras = MagicMock()
        mock.return_value = client
        yield client


def test_cli_camera_show(mock_client):
    """Verify camera show command calls get_cameras and exit gracefully."""
    camera = Camera.model_validate(SAMPLE_CAMERA_DATA)
    mock_client.cameras.list.return_value = [camera]

    # Test showing by ID
    with contextlib.suppress(SystemExit):
        app(["camera", "show", "123456"], exit_on_error=False)

    # Test showing by Token
    with contextlib.suppress(SystemExit):
        app(["camera", "show", "fake-camera-token-123"], exit_on_error=False)

    # Test showing by Name
    with contextlib.suppress(SystemExit):
        app(["camera", "show", "Buddy3D Camera"], exit_on_error=False)

    assert mock_client.cameras.list.call_count == 3


def test_cli_camera_list(mock_client):
    mock_client.cameras.list.return_value = [models.Camera(id=1, name="Cam1", token="tok1")]
    with contextlib.suppress(SystemExit):
        app(["camera", "list"], exit_on_error=False)
    # Alias
    with contextlib.suppress(SystemExit):
        app(["cameras"], exit_on_error=False)
    assert mock_client.cameras.list.call_count == 2


def test_cli_camera_snapshot(mock_client, tmp_path):
    mock_client.cameras.list.return_value = [models.Camera(id=123, name="Cam1")]
    mock_client.get_snapshot.return_value = b"jpegdata"
    out_file = tmp_path / "snap.jpg"
    with contextlib.suppress(SystemExit):
        app(["camera", "snapshot", "123", "--output", str(out_file)], exit_on_error=False)
    mock_client.get_snapshot.assert_called_with("123")
    assert out_file.read_bytes() == b"jpegdata"


def test_cli_camera_trigger(mock_client):
    mock_client.cameras.list.return_value = [models.Camera(id=1, token="tok1")]
    mock_client.trigger_snapshot.return_value = True
    with contextlib.suppress(SystemExit):
        app(["camera", "trigger", "1"], exit_on_error=False)
    mock_client.trigger_snapshot.assert_called_with("tok1")


def test_cli_camera_move(mock_client):
    mock_client.cameras.list.return_value = [models.Camera(id=1, token="tok1")]
    mock_cam_client = MagicMock()
    mock_client.get_camera_client.return_value = mock_cam_client
    with contextlib.suppress(SystemExit):
        app(["camera", "move", "1", "LEFT"], exit_on_error=False)
    mock_cam_client.connect.assert_called()
    mock_cam_client.move.assert_called_with("LEFT", 30)


def test_cli_camera_adjust(mock_client):
    mock_client.cameras.list.return_value = [models.Camera(id=1, token="tok1")]
    mock_cam_client = MagicMock()
    mock_client.get_camera_client.return_value = mock_cam_client
    with contextlib.suppress(SystemExit):
        app(["camera", "adjust", "1", "--brightness", "50"], exit_on_error=False)
    mock_cam_client.adjust.assert_called_with(brightness=50)


def test_cli_camera_set_current():
    with (
        patch("prusa.connect.client.cli.commands.camera.config.save_json_config") as save_mock,
        patch("prusa.connect.client.cli.commands.camera.config.settings") as s_mock,
    ):
        with contextlib.suppress(SystemExit):
            app(["camera", "set-current", "uuid-123"], exit_on_error=False)
        assert s_mock.default_camera_id == "uuid-123"
        assert save_mock.called


def test_cli_camera_show_detailed(mock_client):
    """Verify camera show --detailed command."""
    camera = Camera.model_validate(SAMPLE_CAMERA_DATA)
    mock_client.cameras.list.return_value = [camera]

    with contextlib.suppress(SystemExit):
        app(["camera", "show", "123456", "--detailed"], exit_on_error=False)

    assert mock_client.cameras.list.called


def test_cli_camera_show_not_found(mock_client):
    """Verify camera show handles non-existent cameras."""
    mock_client.cameras.list.return_value = []

    with pytest.raises(SystemExit) as e:
        app(["camera", "show", "nonexistent"], exit_on_error=False)

    assert e.value.code == 1
