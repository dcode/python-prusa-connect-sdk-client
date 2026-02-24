# SDK Quickstart

This guide assumes you have already installed `prusa-connect-sdk-client` using
your preferred package manager. If not, please see the
[Installation](../installation.md) guide.

## Step 1: Authentication

The easiest way to get started is to use the CLI to authenticate. The SDK will
automatically detect and load the credentials saved by the CLI.

### Option 1: Use the CLI (Recommended)

Run:

```bash
prusactl auth login
```

### Option 2: Programmatic Authentication

If you cannot use the CLI or prefer to manage credentials manually, you can use
the `interactive_login` helper function.

```python
from prusa.connect.client import auth
from prusa.connect.client import PrusaConnectClient, PrusaConnectCredentials

# Assume you retrieve the credentials from a secure location
CONNECT_USERNAME = "my@email.com"
CONNECT_PASSWORD = "my_password"


def otp_callback() -> str:
    # If you have 2FA enabled, you need a callback function
    # that returns the OTP code.
    return input("Enter OTP: ")


# Perform interactive login
token_data = auth.interactive_login(CONNECT_USERNAME, CONNECT_PASSWORD, otp_callback)

# Save tokens somewhere (e.g., database, secret manager)
# Or use the default token saver if you want to store it locally
# credentials = PrusaConnectCredentials(token_data, token_saver=auth.save_tokens)

# Or construct a credentials object manually
credentials = PrusaConnectCredentials(tokens=token_data)

client = PrusaConnectClient(credentials=credentials)
```

## Step 2: Hello World

Create a Python script (`hello_prusa.py`) to list your printers.

```python
from prusa.connect.client import PrusaConnectClient

# Credentials are automatically loaded from your environment or default local file
client = PrusaConnectClient()

print("My Printers:")
for printer in client.printers.list_printers():
    status = printer.printer_state or "UNKNOWN"
    print(f"- {printer.name} ({status})")

    if printer.telemetry:
        print(f"  Temp: {printer.telemetry.temp_nozzle}°C")
```

Run it:

```bash
python3 hello_prusa.py
```

## Step 3: Handle Errors

The SDK raises typed exceptions you can catch for robust applications:

```python
from prusa.connect.client import PrusaConnectClient
from prusa.connect.client.exceptions import PrusaApiError, PrusaNetworkError

client = PrusaConnectClient()

try:
    printers = client.printers.list_printers()
except PrusaApiError as e:
    # HTTP error from the Prusa Connect API (4xx / 5xx)
    print(f"API error {e.status_code}: {e}")
    if e.response_body:
        print(f"Details: {e.response_body}")
except PrusaNetworkError as e:
    # Connection timeout, DNS failure, etc.
    print(f"Network error: {e}")
```

## Step 4: Explore the API

Check out the [API Reference](../api/client.md) for a full list of available
methods on `PrusaConnectClient`.
