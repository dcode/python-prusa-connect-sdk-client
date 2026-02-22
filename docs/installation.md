# Installation

This guide covers how to install the Unoriginal Prusa Connect Client SDK for
different use cases.

## CLI Users (Recommended)

If you primarily want to manage your printers from the command line, we
recommend using [pipx](https://pypa.github.io/pipx/) to install the application
in an isolated environment.

### 1. Install pipx

If you don't have `pipx` installed:

=== "macOS"

    ```bash
    brew install pipx
    pipx ensurepath
    ```

=== "Windows"

    ```powershell
    scoop install pipx
    pipx ensurepath
    ```

=== "Linux (Debian/Ubuntu)"

    ```bash
    sudo apt install pipx
    pipx ensurepath
    ```

=== "Linux (Fedora/RHEL)"

    ```bash
    sudo dnf install pipx
    pipx ensurepath
    ```

=== "Linux (other)"

    ```bash
    # Universal fallback using pip
    pip install --user pipx
    pipx ensurepath
    ```

### 2. Install prusactl

Install the package with the `cli` extra:

```bash
pipx install "prusa-connect-sdk-client[cli]"
```

Verify the installation:

```bash
prusactl --version
```

## SDK Developers

If you want to build your own Python applications using the SDK, install the
library using `pip`, `uv`, or your preferred package manager.

=== "pip"

    ```bash
    pip install prusa-connect-sdk-client
    ```

=== "uv"

    ```bash
    uv add prusa-connect-sdk-client
    ```

=== "poetry"

    ```bash
    poetry add prusa-connect-sdk-client
    ```

### Optional Dependencies

The `cli` extra installs additional dependencies like `cyclopts` and `rich`. If
you plan to build your own CLI tools using this SDK, you might want to include
them. It also makes authentication easier for development.

=== "pip"

    ```bash
    pip install prusa-connect-sdk-client[cli]
    ```

=== "uv"

    ```bash
    uv add prusa-connect-sdk-client[cli]
    ```

=== "poetry"

    ```bash
    poetry add prusa-connect-sdk-client[cli]
    ```
