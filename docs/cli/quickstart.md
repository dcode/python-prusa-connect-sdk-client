# CLI Quickstart

This guide assumes you have already installed `prusactl` using `pipx`. If not, please see the [Installation](../installation.md) guide.

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

## Step 4: Explore Commands

Use the `--help` flag to discover available commands:

```bash
prusactl --help
```

Or for a specific command:

```bash
prusactl printer --help
```
