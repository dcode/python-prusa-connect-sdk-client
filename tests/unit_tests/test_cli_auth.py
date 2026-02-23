import contextlib
from unittest.mock import MagicMock, patch

import pytest

from prusa.connect.client.cli import app


@pytest.fixture
def mock_creds():
    with patch("prusa.connect.client.auth.PrusaConnectCredentials.load_default") as mock:
        creds = MagicMock()
        mock.return_value = creds
        yield creds


def test_auth_login(tmp_path):
    # Mocking config and Prompt
    with (
        patch("prusa.connect.client.cli.commands.auth.config.settings") as s_mock,
        patch("prusa.connect.client.cli.commands.auth.Prompt.ask") as p_mock,
        patch("prusa.connect.client.auth.interactive_login") as login_mock,
    ):
        s_mock.tokens_file = tmp_path / "tokens.json"
        p_mock.side_effect = ["email@e.com", "pass", "123456"]

        mock_data = MagicMock()
        mock_data.dump_tokens.return_value = {"acc": "tok"}
        login_mock.return_value = mock_data

        with contextlib.suppress(SystemExit):
            app(["auth", "login"], exit_on_error=False)

        assert login_mock.called
        assert (tmp_path / "tokens.json").exists()


def test_auth_show(mock_creds):
    mock_creds.valid = True
    mock_creds.tokens.access_token.token_id = "jti1"
    mock_creds.tokens.identity_token = None
    mock_creds.tokens.refresh_token = None

    with contextlib.suppress(SystemExit):
        app(["auth", "show"], exit_on_error=False)

    assert mock_creds.tokens.access_token.token_id == "jti1"


def test_auth_clear(tmp_path):
    tokens_file = tmp_path / "tokens.json"
    tokens_file.write_text("{}")

    with (
        patch("prusa.connect.client.cli.commands.auth.config.settings") as s_mock,
        patch("prusa.connect.client.cli.commands.auth.Confirm.ask", return_value=True),
    ):
        s_mock.tokens_file = tokens_file
        with contextlib.suppress(SystemExit):
            app(["auth", "clear"], exit_on_error=False)
        assert not tokens_file.exists()


def test_auth_print_tokens(mock_creds):
    mock_creds.valid = True
    mock_creds.tokens.access_token.raw_token = "raw_acc"
    mock_creds.tokens.identity_token.raw_token = "raw_id"

    with contextlib.suppress(SystemExit):
        app(["auth", "print-access-token"], exit_on_error=False)

    with contextlib.suppress(SystemExit):
        app(["auth", "print-identity-token"], exit_on_error=False)
