# How-to Guides and Examples

## Headless Authentication (CI/CD)

For environments where interactive login isn't possible (like CI/CD pipelines or
servers), you can use environment variables.

1. **Option A: Raw Token** Set the `PRUSA_TOKEN` environment variable with your
   raw JWT access token.

    ```bash
    export PRUSA_TOKEN="ey..."
    ```

2. **Option B: Token JSON** Set the `PRUSA_TOKENS_JSON` environment variable
   with the full JSON object containing access and refresh tokens.

    ```bash
    export PRUSA_TOKENS_JSON='{"access_token": "...", "refresh_token": "..."}'
    ```

The `PrusaConnectClient` will automatically detect these variables.

## Controlling a Printer

You can send commands like PAUSE, RESUME, or STOP.

```python
from prusa.connect.client import PrusaConnectClient

client = PrusaConnectClient()

# Get your printer's UUID (e.g., from client.get_printers())
printer_uuid = "c0ffee-uuid-1234"

# Pause the print
client.send_command(printer_uuid, "PAUSE_PRINT")
print("Printer paused.")
```

## Accessing Cameras

Fetch the latest snapshot from your printer's camera.

```python
from prusa.connect.client import PrusaConnectClient

client = PrusaConnectClient()
cameras = client.get_cameras()

if cameras:
    cam = cameras[0]
    print(f"Taking snapshot from {cam.name}...")

    # Get binary image data
    image_data = client.get_snapshot(cam.id)

    with open("snapshot.jpg", "wb") as f:
        f.write(image_data)
    print("Saved to snapshot.jpg")
```

## Managing Files

List files on your team's storage.

```python
from prusa.connect.client import PrusaConnectClient

client = PrusaConnectClient()
teams = client.get_teams()
if teams:
    my_team_id = teams[0].id
    files = client.get_file_list(my_team_id)

    for file in files:
        print(f"{file.name} ({file.size.human_readable() if file.size else 'N/A'})")
```
