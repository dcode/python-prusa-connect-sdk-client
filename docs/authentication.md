# Authentication

Authentication is a crucial part of interacting with the Prusa Connect API. The SDK handles authentication tokens automatically once you've logged in.

## How it Works

The SDK uses OAuth 2.0-like flow to obtain access and refresh tokens.

1.  **Identity Token**: Used to identify the user.
2.  **Access Token**: Used to authenticate API requests. Valid for a short period (usually 1 hour).
3.  **Refresh Token**: Used to obtain new access tokens when they expire. Valid for a longer period (usually 30 days).

## Storing Credentials

The SDK stores tokens securely in a user-specific configuration directory using `platformdirs`.

-   **Linux**: `~/.config/prusa-connect-sdk-client/tokens.json` (or similar)
-   **macOS**: `~/Library/Application Support/prusa-connect-sdk-client/tokens.json`
-   **Windows**: `%APPDATA%\prusa-connect-sdk-client\tokens.json`

The file is JSON-formatted and contains the tokens. It is recommended to restrict access to this file.

## Authentication Methods

### 1. CLI Authentication (Recommended)

Run `prusactl auth login` to start an interactive login session. This will prompt for your email, password, and 2FA code (if enabled).

### 2. Environment Variables

You can also provide credentials via environment variables, although this is generally less secure for long-term use.

-   `PRUSA_EMAIL`: Your Prusa Account email.
-   `PRUSA_PASSWORD`: Your Prusa Account password.

Note: Environment variables are used for initial login if provided, but tokens are preferred.

### 3. Programmatic Authentication

You can use `prusa.connect.client.auth.interactive_login` to perform the login flow in your own application. See the [SDK Quickstart](sdk/quickstart.md) for an example.
