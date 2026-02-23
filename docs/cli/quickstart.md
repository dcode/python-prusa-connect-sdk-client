# CLI Quickstart

This guide assumes you have already installed `prusactl` using `pipx`. If not,
please see the [Installation](../installation.md) guide.

## Step 1: Authenticate

Run the following command in your terminal to log in to your Prusa Account. This
will save a secure token locally to your user configuration directory.

```bash
prusactl auth login
```

*Follow the interactive prompts to enter your credentials and 2FA code (if
required).*

The CLI will display a success message and save your credentials securely.

## Step 2: Verify Authentication

You can check your current authentication status at any time:

```bash
prusactl auth show
```

## Step 3: List Your Printers

Now that you are authenticated, list your printers:

```bash
prusactl printer list
```

## Step 4: Set a Default Printer

Most commands require a printer UUID. To avoid typing it every time, set a
default:

```bash
prusactl printer set-current <uuid>
```

Once set, commands like `prusactl printer show`, `prusactl stats usage`, and
others will automatically use this printer.

## Step 5: Monitor Printer Statistics

Track usage over time with the `stats` command group:

```bash
# Printing time vs idle time for the last 7 days
prusactl stats usage

# Material consumption
prusactl stats material --days 30

# Job success/failure breakdown
prusactl stats jobs

# Planned task schedule (hour-by-hour heatmap)
prusactl stats planned
```

All `stats` subcommands accept `--from` and `--to` date flags for custom date
ranges, and `--days N` as a shorthand for the last N days.

## Step 6: Work with Teams and Cameras

List the teams you belong to and manage cameras:

```bash
# Teams
prusactl team list
prusactl team show          # Show default team details

# Cameras
prusactl camera list
prusactl camera snapshot <camera-id> --output snapshot.jpg
prusactl camera show <camera-id>
```

## Step 7: Configure Defaults

Set defaults for team and camera to avoid passing IDs repeatedly:

```bash
prusactl team set-current <team-id>
prusactl camera set-current <camera-id>
```

## Step 8: Enable Shell Completion

`prusactl` supports tab completion for all commands and flags. Install it for
your shell:

```bash
prusactl --install-completion
```

Restart your shell (or source your profile) to activate it.

## Step 9: Explore Commands

Use the `--help` flag to discover available commands and flags at any level:

```bash
prusactl --help
prusactl printer --help
prusactl stats --help
```

## Configuration File

Settings like default printer, team, and camera IDs are stored in a JSON file in
your platform config directory:

| Platform | Path                                                                 |
| -------- | -------------------------------------------------------------------- |
| Linux    | `~/.config/prusa-connect-sdk-client/config.json`                     |
| macOS    | `~/Library/Application Support/prusa-connect-sdk-client/config.json` |
| Windows  | `%APPDATA%\prusa-connect-sdk-client\config.json`                     |

You can edit this file directly. Supported keys:

```json
{
  "default_printer_id": "your-printer-uuid",
  "default_team_id": 12345,
  "default_camera_id": "your-camera-id"
}
```

Environment variables (e.g. `DEFAULT_PRINTER_ID`) override file values.
