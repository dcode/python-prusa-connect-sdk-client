from prusa.connect.client.models import Camera, CameraConfig, CameraNetworkInfo, CameraOptions, CameraResolution

SAMPLE_CAMERA_DATA = {
    "id": 123456,
    "name": "Buddy3D Camera",
    "config": {
        "name": "Buddy3D Camera",
        "path": "private",
        "model": "Buddy3D",
        "driver": "private",
        "firmware": "3.0.0",
        "rotation": 0,
        "camera_id": "0000012345",
        "resolution": {"width": 1920, "height": 1080},
        "manufacturer": "Niceboy",
        "network_info": {
            "wifi_mac": "00:11:22:33:44:55",
            "wifi_ipv4": "10.0.0.42",
            "wifi_ssid": "Fake-IoT-WiFi",
        },
        "trigger_scheme": "THIRTY_SEC",
    },
    "options": {"available_resolutions": [{"width": 1920, "height": 1080}]},
    "capabilities": ["trigger_scheme"],
    "features": ["SocketCom", "WiFi", "trigger_scheme"],
    "sort_order": 1,
    "token": "fake-camera-token-123",
    "origin": "OTHER",
    "registered": True,
    "team_id": 31337,
    "printer_uuid": "printer-uuid-abc-123",
}


def test_camera_model_parsing():
    """Verify that the Camera model parses correctly with nested structures."""
    camera = Camera.model_validate(SAMPLE_CAMERA_DATA)

    assert camera.id == 123456
    assert camera.name == "Buddy3D Camera"
    assert camera.token == "fake-camera-token-123"
    assert isinstance(camera.config, CameraConfig)
    assert camera.config.firmware == "3.0.0"
    assert camera.config.manufacturer == "Niceboy"

    assert isinstance(camera.config.resolution, CameraResolution)
    assert camera.config.resolution.width == 1920
    assert camera.config.resolution.height == 1080

    assert isinstance(camera.config.network_info, CameraNetworkInfo)
    assert camera.config.network_info.wifi_ipv4 == "10.0.0.42"
    assert camera.config.network_info.wifi_ssid == "Fake-IoT-WiFi"

    assert isinstance(camera.options, CameraOptions)
    assert camera.options.available_resolutions is not None
    assert len(camera.options.available_resolutions) == 1
    assert camera.options.available_resolutions[0].width == 1920

    assert camera.capabilities == ["trigger_scheme"]
    assert camera.features is not None
    assert "WiFi" in camera.features
    assert camera.registered is True
    assert camera.team_id == 31337
    assert camera.printer_uuid == "printer-uuid-abc-123"


def test_camera_model_missing_fields():
    """Verify that the Camera model handles missing optional fields."""
    minimal_data = {"id": 1, "token": "abc"}
    camera = Camera.model_validate(minimal_data)
    assert camera.id == 1
    assert camera.token == "abc"
    assert camera.config is None
    assert camera.options is None
    assert camera.features is None
