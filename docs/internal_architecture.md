# Architecture & Explanation

## Authentication Flow

Prusa Connect uses a secure OAuth2 flow with PKCE. This library provides an
implementation similar to the `google-auth` library for Google services. The
`PrusaConnectClient` uses an `AuthStrategy` interface to handle authentication.
The `PrusaConnectCredentials` class is a concrete implementation of this
interface that handles the storage and refresh of tokens. For each request, the
`before_request` method of the credentials object is called to inject
credentials, as needed. If the access token has expired and the credentials
object has a valid refresh token, it will be refreshed automatically.

- **Interactive:** The CLI (`prusactl`) handles the complex exchange of
  username, password, and 2FA to obtain a **Refresh Token** and **Access
  Token**.
- **Refresh:** The `PrusaConnectClient` automatically checks if the Access Token
  is expired and uses the Refresh Token to get a new one, ensuring your
  long-running scripts don't break.
- **Storage:** Tokens are stored in a platform-specific configuration directory
  by default (e.g., `~/.config/prusa-connect/prusa_tokens.json` on Linux) with
  permissions restricted to the file owner. Treat this file like a password.
