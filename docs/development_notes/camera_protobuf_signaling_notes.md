# Prusa Camera Protobuf & SDK Guide

This document contains the reconstructed Protobuf schema for the Prusa Connect
Camera system, an enumeration of signaling events, and a Python implementation
guide.

## 1. Protobuf Schema (camera_v2.proto)

Based on the encode and decode functions in CamerasPage.js and cross-referenced
with the camera-openapi.yaml, here is the final reconstructed schema.

```proto
syntax = "proto3";

package prusa.camera.v2;

// Used in triggers to request data or toggle persistent features
enum FeatureState {
  FEATURE_INVALID = 0;
  FEATURE_ENABLED = 1;  // Request data / Turn on
  FEATURE_DISABLED = 2; // Stop data / Turn off
}

enum RotationDirection {
  ROTATION_DIRECTION_INVALID = 0;
  LEFT = 1;
  RIGHT = 2;
  UP = 3;
  DOWN = 4;
}

enum CameraMode {
  CAMERA_MODE_INVALID = 0;
  AUTO = 1;
  DAY = 2;
  NIGHT = 3;
}

enum VideoQuality {
  VIDEO_QUALITY_INVALID = 0;
  VIDEO_QUALITY_SD = 1;
  VIDEO_QUALITY_HD = 2;
  VIDEO_QUALITY_FHD = 3;
}

enum TimelapseStatus {
  TIMELAPSE_INVALID = 0;
  TIMELAPSE_IDLE = 1;
  TIMELAPSE_IN_PROGRESS = 2;
  TIMELAPSE_DONE = 3;
  TIMELAPSE_FAILED = 4;
}

// --- Handshake & Trigger Messages ---

message ClientAuthentication {
  string camera_token = 1;
  string client_type = 2;      // "client" or "user"
  string client_jwt_token = 3; // Optional JWT
  string fingerprint = 4;      // Browser/Device fingerprint for auth
}

message CameraTrigger {
  FeatureState get_status = 1;
  FeatureState get_features = 2;
  FeatureState get_snapshot = 3;
  FeatureState set_snapshot_enable = 4;
  FeatureState set_timelapse_enable = 5;
  FeatureState start_fw_update = 8;
  FeatureState start_device_reboot = 9;
  FeatureState start_rtsp_server = 10;
  string camera_token = 11;
  FeatureState get_protocol_information = 12;
  string request_id = 13;
  FeatureState start_timelapse_video = 14; // Triggers MP4 rendering
  FeatureState get_timelapse_file_list = 15;
}

// --- Configuration Messages ---

message RotationSettings {
  RotationDirection direction = 1;
  uint32 angle = 2;
}

message CameraControl {
  RotationSettings rotation = 1;
  FeatureState camera_light = 2;
  uint32 exposure_time = 3;
  CameraMode camera_mode = 4;
  uint32 snapshot_interval = 5;
  int32 contrast = 6;
  uint32 volume = 7;
  int32 brightness = 8;
  int32 saturation = 9;
  string printing_job_name = 10; // Used to name the resulting timelapse file
}

message ServerToCamera {
  CameraControl control = 3;
  string camera_token = 6;
  string request_id = 7;
}

// --- Status & Features (Inbound) ---

message WifiInfo {
  string ssid = 1;
  string mac = 2;
  string ipv4 = 3;
  string ipv6 = 4;
  uint32 signal_quality = 5;
}

message EthernetInfo {
  string mac = 1;
  string ipv4 = 2;
  string ipv6 = 3;
}

message NetworkInfo {
  oneof interface {
    WifiInfo wifi = 1;
    EthernetInfo ethernet = 2;
  }
}

message CameraFeatures {
  bool has_ptz = 1;
  bool has_ir = 2;
  bool has_led = 3;
  bool has_audio = 4;
  bool has_sd_card = 5;
  VideoQuality max_quality = 6;
  string firmware_version = 7;
  string camera_token = 8;
  bool has_webrtc = 9;
}

message CameraStatus {
  float mcu_temperature = 1;
  uint64 uptime_raw = 2;
  string uptime = 3;
  string load = 4;
  uint64 total_ram = 5;
  uint64 free_ram = 6;
  uint64 shared_ram = 7;
  uint64 buffer_ram = 8;
  uint32 procs = 9;
  TimelapseStatus timelapse_video_status = 10; // Found in ClientTrigger/Status
}

message CameraToServer {
  CameraStatus camera_status = 1;
  NetworkInfo network = 4;
  string camera_token = 8;
}
```

## 2. Enumeration of Signaling Events

The SDK communicates with the signaling server using the following Socket.io
events.

| Event Name            | Direction | Format   | Description                                          |
| :-------------------- | :-------- | :------- | :--------------------------------------------------- |
| client_authentication | Out       | Protobuf | Initial handshake.                                   |
| trigger               | Out       | Protobuf | Request actions (Snapshot, Reboot, Timelapse Start). |
| configuration         | Out       | Protobuf | Change settings (PTZ, Camera Name).                  |
| status                | In        | Protobuf | Real-time telemetry and state updates.               |
| features              | In        | Protobuf | Device capability report.                            |
| client_trigger        | In        | Protobuf | Async task updates (like timelapse progress).        |

## 3. Timelapse Workflow

### Phase 1: Preparation

Before starting a print, ensure set_timelapse_enable is FEATURE_ENABLED in a
CameraTrigger. Optionally set the printing_job_name in CameraControl so the
camera knows what to call the file.

### Phase 2: Rendering

Once the print is complete, send a CameraTrigger with start_timelapse_video =
FEATURE_ENABLED. The camera encodes the snapshots on its SD card into an .mp4.

### Phase 3: Monitoring & Upload

Listen for the status or client_trigger events. The camera will transition to
TIMELAPSE_DONE. At this point, the camera pushes the rendered file to Prusa
Connect.

### Phase 4: Download

Finished files are hosted by Prusa Connect. The URL is typically structured as
(this mainly a guess, based on existing convention of the camera OpenAPI spec):

```plaintext
https://connect.prusa3d.com/c/timelapse/{camera_token}/{job_name}.mp4
```

Accessing this requires the same authentication headers used by the camera (as
defined in the OpenAPI spec) or likely the OpenID Connect JWT token approach
used by the Client API:

- **Token:** The camera's unique token.
- **Fingerprint:** The camera's unique hardware fingerprint.

## 4. Python SDK Implementation

### Dependencies

```bash
pip install python-socketio protobuf requests
```

### Cloud Download Example

Alternatively, the download could well likely use the same OAuth2 JWT bearer
token as the rest of the Prusa Connect Client API.

```python
import requests


def download_from_connect(camera_token, fingerprint, job_name, destination):
    url = f"https://connect.prusa3d.com/c/timelapse/{camera_token}/{job_name}.mp4"
    headers = {"Token": camera_token, "Fingerprint": fingerprint}

    response = requests.get(url, headers=headers, stream=True)
    if response.status_code == 200:
        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    else:
        print(f"Failed to download: {response.status_code}")
```
