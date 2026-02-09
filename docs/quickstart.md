# Quickstart

## CLI Quickstart

### Step 1: Authenticate

Run the following command in your terminal to log in to your Prusa Account. This
will save a secure token locally to your user configuration directory.

```bash
prusactl auth login
```

*Follow the interactive prompts to enter your credentials and 2FA code (if
required).*

Optional: Check your current authentication token status.

```bash
prusactl auth show
```

## Python Quickstart

### Step 1: Authenticate

The easy button is to use the CLI to authenticate. Once you have the tokens
file, the token will refresh automatically until your refresh token expires
(seems to be around 30 days). Let's say you don't want the CLI because whatever
your personal reason is, you can use the `interactive_login` helper function
from the `auth` module. This function performs the same authentication flow as
the official Prusa Connect web app, but implemented purely in Python.

Passing the `save_tokens` function to the `PrusaConnectCredentials` will save
the tokens to `TOKEN_PATH`

```python
from prusa.connect.client.auth import interactive_login

# Assume you retrieve the credentials from a secure location
CONNECT_USERNAME = "<EMAIL_ADDRESS>"
CONNECT_PASSWORD = "<PASSWORD>"


def otp_callback() -> str:
    # If you have 2FA enabled, you need a callback function
    # that returns the OTP code.
    return input("Enter OTP: ")


# This will open a browser window for you to log in
token_data = interactive_login(CONNECT_USERNAME, CONNECT_PASSWORD, otp_callback)

# You can then use the token_data to create the creds object for a client
from prusa.connect.client import PrusaConnectClient, PrusaConnectCredentials

TOKEN_PATH = get_default_token_path()


def save_tokens(token_data: dict[str, Any]):
    with TOKEN_PATH.open("w") as f:
        import json

        json.dumps(token_data, f)


creds = PrusaConnectCredentials(token_data, token_saver=save_tokens)
client = PrusaConnectClient(credentials=creds)
```

### Step 2: Hello World

Create a Python script (`hello_prusa.py`) to list your printers. The client
automatically loads the credentials you just saved.

```python
from prusa.connect.client import PrusaConnectClient

# Credentials are automatically loaded from your environment or default local file
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
python3 hello_prusa.py
```
