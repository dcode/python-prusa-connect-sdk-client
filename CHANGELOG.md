# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - Unreleased

### Breaking Changes

- Removed deprecated shim methods from `PrusaConnectClient` that were present in
  the alpha releases. The service-based API is now the sole public interface:

    | Removed method                   | Replacement                               |
    | -------------------------------- | ----------------------------------------- |
    | `client.get_printers()`          | `client.printers.list_printers()`         |
    | `client.get_printer(uuid)`       | `client.printers.get(uuid)`               |
    | `client.get_cameras()`           | `client.cameras.list()`                   |
    | `client.get_teams()`             | `client.teams.list_teams()`               |
    | `client.get_team(id)`            | `client.teams.get(id)`                    |
    | `client.send_command(uuid, cmd)` | `client.printers.send_command(uuid, cmd)` |

### Added

- **Service-based API:** Resources are now accessed through dedicated service
  objects on the client — `client.printers`, `client.cameras`, `client.teams`,
  `client.files`, `client.jobs`, and `client.stats`.
- **`prusactl` CLI** with full subcommand coverage: `printer`, `camera`, `team`,
  `job`, `file`, `stats`, and `auth`.
- **Statistics service** (`client.stats`) for per-printer material usage, print
  time, planned tasks, and job success metrics.
- **Printer command discovery** — `client.printers.get_supported_commands(uuid)`
  with optional disk caching and TTL.
- **Validated command execution** — `client.execute_printer_command()` validates
  arguments against the printer's reported command schema before sending.
- **Camera WebRTC signaling client** (`PrusaCameraClient`) for pan/tilt control
  and image adjustment via the Prusa signaling protocol.
- **G-code metadata parser** (`client.validate_gcode(path)`) for pre-flight
  checks before uploading.
- **Persistent credential caching** — CLI credentials are stored in the platform
  config directory and auto-loaded by the SDK.

### Changed

- CLI rewritten with [Cyclopts](https://github.com/BrianPugh/cyclopts) for
  richer help output and `--verbose` / `--debug` global flags.
- Pydantic models split into focused submodules under
  `prusa.connect.client.models`.
- `AppConfig` is now fetched at client init time to validate that the server
  supports the `PRUSA_AUTH` backend.

## [1.0.0a2] - 2025-01-13

### Changed

- Refactored CLI to use Cyclopts; split monolithic models into service modules;
  added stats commands and documentation site.

## [1.0.0a0] - Initial alpha release
