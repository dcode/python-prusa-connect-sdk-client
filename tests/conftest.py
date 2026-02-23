import os
from unittest.mock import MagicMock, patch

import pytest


def pytest_load_initial_conftests(early_config, parser, args):
    """Conditionally append coverage report to GITHUB_STEP_SUMMARY.

    Only applies when running in GitHub Actions.
    """
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if (
        os.getenv("GITHUB_ACTIONS") == "true"
        and summary_file
        and not any(arg.startswith("--cov-report=markdown-append:") for arg in args)
    ):
        args.append(f"--cov-report=markdown-append:{summary_file}")


@pytest.fixture(autouse=True)
def mock_get_app_config():
    """Mock get_app_config to prevent network calls during tests."""
    with patch("prusa.connect.client.PrusaConnectClient.get_app_config") as mock:
        mock.return_value = MagicMock()
        yield mock
