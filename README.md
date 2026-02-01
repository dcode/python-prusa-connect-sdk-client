# Prusa Connect Python Client

[![PyPI version](https://badge.fury.io/py/prusa-connect.svg)](https://badge.fury.io/py/prusa-connect)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python Versions](https://img.shields.io/pypi/pyversions/prusa-connect.svg)](https://pypi.org/project/prusa-connect/)

Control your Prusa 3D printers programmatically with Python. This library provides a frictionless, strongly-typed interface for the Prusa Connect API.

**Features:**
*   **Zero-Config Authentication:** Log in once via CLI, use everywhere in Python.
*   **Strong Typing:** Full Pydantic models for printers, jobs, cameras, and files.
*   **Batteries Included:** Retries, timeouts, and error handling out of the box.
*   **CLI Tool:** Managing printers from the terminal.

---

## 1. Installation

Install the package with the CLI tools (recommended for easiest setup):

```bash
pip install "prusa-connect[cli]"
```

Or install the lightweight library only:

```bash
pip install prusa-connect
```

## 2. Quickstart

### Step 1: Authenticate

Run the following command in your terminal to log in to your Prusa Account. This will save a secure token locally.

```bash
prusactl list-printers
```
*Follow the interactive prompts to enter your credentials and 2FA code.*

### Step 2: Hello World

Create a Python script (`hello_prusa.py`) to list your printers. The client automatically loads the credentials you just saved.

```python
from prusa_connect import PrusaConnectClient

# Credentials are automatically loaded from your environment or local file
client = PrusaConnectClient()

print("My Printers:")
for printer in client.get_printers():
    status = printer.printer_state or "UNKNOWN"
    print(f"- {printer.name} ({status})")

    if printer.telemetry:
        print(f"  Temp: {printer.telemetry.temp_nozzle}°C")
```

Run it:

```bash
python hello_prusa.py
```

---

## 3. How-to Guides

### Headless Authentication (CI/CD)

For environments where interactive login isn't possible (like CI/CD pipelines or servers), you can use environment variables.

1.  **Option A: Raw Token**
    Set the `PRUSA_TOKEN` environment variable with your raw JWT access token.

    ```bash
    export PRUSA_TOKEN="ey..."
    ```

2.  **Option B: Token JSON**
    Set the `PRUSA_TOKENS_JSON` environment variable with the full JSON object containing access and refresh tokens.

    ```bash
    export PRUSA_TOKENS_JSON='{"access_token": "...", "refresh_token": "..."}'
    ```

The `PrusaConnectClient` will automatically detect these variables.

### Controlling a Printer

You can send commands like PAUSE, RESUME, or STOP.

```python
client = PrusaConnectClient()

# Get your printer's UUID (e.g., from client.get_printers())
printer_uuid = "c0ffee-uuid-1234"

# Pause the print
client.send_command(printer_uuid, "PAUSE_PRINT")
print("Printer paused.")
```

### Accessing Cameras

Fetch the latest snapshot from your printer's camera.

```python
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

### Managing Files

List files on your team's storage.

```python
teams = client.get_teams()
if teams:
    my_team_id = teams[0].id
    files = client.get_file_list(my_team_id)

    for file in files:
        print(f"{file.name} ({file.size} bytes)")
```

---

## 4. Reference

### `PrusaConnectClient`

The main entry point for the API.

**Initialization:**
```python
client = PrusaConnectClient(
    credentials=None, # Auto-loads if None
    base_url="https://connect.prusa3d.com/app",
    timeout=30.0
)
```

**Key Methods:**
*   `get_printers() -> list[Printer]`
*   `get_printer(uuid) -> Printer`
*   `send_command(uuid, command)`
*   `get_cameras() -> list[Camera]`
*   `get_snapshot(camera_id) -> bytes`
*   `get_team_jobs(team_id) -> list[Job]`

### Data Models

All responses are validated Pydantic models.

*   `Printer`: `uuid`, `name`, `printer_state`, `telemetry` (temps), `job` (current status).
*   `Job`: `state`, `progress`, `time_remaining`, `file`.
*   `Camera`: `id`, `name`, `resolution`.

---

## 5. Explanation

### Authentication Flow

Prusa Connect uses a secure OAuth2-like flow with PKCE.
*   **Interactive:** The CLI (`prusactl`) handles the complex exchange of username, password, and 2FA to obtain a **Refresh Token** and **Access Token**.
*   **Refresh:** The `PrusaConnectClient` automatically checks if the Access Token is expired and uses the Refresh Token to get a new one, ensuring your long-running scripts don't break.
*   **Storage:** Tokens are stored in `prusa_tokens.json` by default. Treat this file like a password.
