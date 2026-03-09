# How-to Guides and Examples

## Headless Authentication (CI/CD)

For environments where interactive login isn't possible, use the `PRUSA_TOKEN`
or `PRUSA_TOKENS_JSON` environment variables. See
[Authentication](authentication.md#3-headless-cicd-authentication) for full
details.

## Controlling a Printer

You can send commands like PAUSE, RESUME, or STOP.

```python
from prusa.connect.client import PrusaConnectClient

client = PrusaConnectClient()

# Get your printer's UUID (e.g., from client.printers.list_printers())
printer_uuid = "c0ffee-uuid-1234"

# Pause the print
client.pause_print(printer_uuid)
print("Printer paused.")
```

## Accessing Cameras

Fetch the latest snapshot from your printer's camera.

```python
from prusa.connect.client import PrusaConnectClient

client = PrusaConnectClient()
cameras = client.cameras.list()

if cameras:
    cam = cameras[0]
    print(f"Taking snapshot from {cam.name}...")

    # Get binary image data
    image_data = client.get_snapshot(cam.id)

    with open("snapshot.jpg", "wb") as f:
        f.write(image_data)
    print("Saved to snapshot.jpg")
```

## WebRTC Camera Streaming

For live video feeds, Prusa Connect supports low-latency WebRTC streaming. To
set up a WebRTC stream, you need the camera's token and a valid JWT token from
an authenticated client.

```python
from prusa.connect.client import PrusaConnectClient
from importlib import resources

client = PrusaConnectClient()
cameras = client.cameras.list()

if cameras:
    cam = cameras[0]
    camera_token = cam.token

    # Extract the JWT Token safely
    jwt_token = ""
    if hasattr(client, "_credentials") and hasattr(client._credentials, "tokens"):
        jwt_token = client._credentials.tokens.access_token.raw_token

    print(f"Camera Token: {camera_token}")
    print(f"JWT Token: {jwt_token}")

    # Load the protobuf definition needed by the signaling server
    proto_path = resources.files("prusa.connect.client") / "camera_v2.proto"
    proto_content = proto_path.read_text("utf-8")

    # You can now use these credentials and the protobuf definition to
    # initialize a WebRTC connection via the Prusa Connect signaling endpoint.
    # See the CLI 'prusactl camera webrtc' command for an example of injecting
    # these into a local HTML template for browser-based playback.
```

## Managing Files

List files on your team's storage.

```python
from prusa.connect.client import PrusaConnectClient

client = PrusaConnectClient()
teams = client.teams.list_teams()
if teams:
    my_team_id = teams[0].id
    files = client.files.list(my_team_id)

    for file in files:
        print(f"{file.name} ({file.size.human_readable() if file.size else 'N/A'})")
```
