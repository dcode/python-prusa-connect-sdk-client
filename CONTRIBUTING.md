# Contributing to Prusa Connect Client SDK

First off, thank you for considering contributing to the Python Prusa Connect
Client SDK! It's people like you that make this tool great.

## Development Environment Setup

This project uses `uv` for dependency management and packaging, ensuring a
blazingly fast and reproducible development environment.

### Prerequisites

1. **Install `uv`**: If you haven't already, install
   [astral-sh/uv](https://docs.astral.sh/uv/getting-started/installation/).

2. **Clone the Repository**:

    ```bash
    git clone https://github.com/dcode/python-prusa-connect-sdk-client.git
    cd python-prusa-connect-sdk-client
    ```

### Install Dependencies

To set up your local development environment with all necessary dependencies
(including development tools, testing frameworks, documentation builders, and
the optional `cli` feature):

```bash
uv sync --all-extras --all-groups
```

This command will automatically create a virtual environment at `.venv/` and
synchronize it lock-step with `uv.lock`.

To activate the virtual environment so your terminal recognizes the installed
tools:

```bash
source .venv/bin/activate
```

## Linting and Code Style

This project strictly adheres to continuous integration checks to maintain high
code quality. We use `pre-commit` to catch linting, formatting, and
type-checking issues *before* they are committed.

1. **Install the pre-commit hooks**:

    ```bash
    pre-commit install
    ```

    Now, every time you run `git commit`, the hooks will automatically format and
    check your code.

2. **Run hooks manually** (optional, but recommended before pushing):

    ```bash
    pre-commit run --all-files
    ```

### Tools Used

- **Formatting/Linting:** `ruff` (configured in `pyproject.toml`)
- **Type Checking:** `pyrefly` (a `pyright` replacement)
- **Markdown:** `mdformat` and `markdownlint`

## Running Tests

We use `pytest` for our unit testing framework. To run the full test suite
locally:

```bash
uv run pytest
```

If you add a new feature or fix a bug, please ensure you write a corresponding
test in the `tests/` directory to verify the behavior.

## Building Documentation

The documentation is built using MkDocs and the Material for MkDocs theme. To
preview your changes to the documentation locally:

```bash
uv run mkdocs serve
```

This will start a local web server (usually at `http://127.0.0.1:8000`) that
automatically reloads whenever you save a Markdown file.

## Submitting a Pull Request

1. **Fork** the repository and create a new branch containing your feature or
   bugfix.
2. **Commit** your changes using descriptive commit messages.
3. **Ensure tests and linters pass** locally.
4. **Open a Pull Request** against the `main` branch.
5. Wait for the CI GitHub Actions to complete successfully.

Thank you for contributing!
