import contextlib
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from prusa.connect.client.cli import common, config


@pytest.fixture(autouse=True)
def reset_output_format():
    """Reset the global output format before and after each test."""
    common._output_format = None
    yield
    common._output_format = None


def test_set_output_format_valid():
    common.set_output_format("json")
    assert common.get_output_format() == config.OutputFormat.JSON

    common.set_output_format("plain")
    assert common.get_output_format() == config.OutputFormat.PLAIN

    common.set_output_format("rich")
    assert common.get_output_format() == config.OutputFormat.RICH


def test_set_output_format_invalid():
    with pytest.raises(SystemExit) as excinfo:
        common.set_output_format("invalid")
    assert excinfo.value.code == 1


def test_get_output_format_default_tty(monkeypatch):
    # Mock sys.stdout.isatty to return True
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert common.get_output_format() == config.OutputFormat.RICH


def test_get_output_format_default_no_tty(monkeypatch):
    # Mock sys.stdout.isatty to return False
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    assert common.get_output_format() == config.OutputFormat.PLAIN


def test_get_output_format_from_config():
    with patch("prusa.connect.client.cli.config.settings") as mock_settings:
        mock_settings.output_format = config.OutputFormat.JSON
        assert common.get_output_format() == config.OutputFormat.JSON


def test_output_message_rich(capsys):
    common.set_output_format("rich")
    # We can't easily test rich's actual colored output here because it depends on terminal
    # but we can check if it calls the console.
    with patch("prusa.connect.client.cli.common.console") as mock_console:
        common.output_message("Hello [bold]World[/bold]")
        mock_console.print.assert_called_once_with("Hello [bold]World[/bold]")


def test_output_message_plain(capsys):
    common.set_output_format("plain")
    common.output_message("Hello [bold]World[/bold]")
    captured = capsys.readouterr()
    assert captured.out == "Hello World\n"


def test_output_message_json(capsys):
    common.set_output_format("json")
    # JSON format should send messages to stderr
    common.output_message("Hello [bold]World[/bold]")
    captured = capsys.readouterr()
    assert "Hello World" in captured.err


def test_output_table_plain(capsys):
    common.set_output_format("plain")
    common.output_table("My Table", ["Col1", "Col2"], [["R1C1", "R1C2"], ["R2C1", "R2C2"]])
    captured = capsys.readouterr()
    expected = "# My Table\nCol1\tCol2\nR1C1\tR1C2\nR2C1\tR2C2\n"
    assert captured.out == expected


def test_output_table_json(capsys):
    common.set_output_format("json")
    common.output_table("My Table", ["Col 1", "Col 2"], [["R1C1", "R1C2"]])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data == [{"col_1": "R1C1", "col_2": "R1C2"}]


def test_cli_format_flag():
    from prusa.connect.client.cli.main import app

    # Use a command that output something, like 'printer list'
    # We need to mock the client to avoid network calls
    with patch("prusa.connect.client.cli.commands.printer.common.get_client") as mock_get_client:
        client = MagicMock()
        client.printers.list_printers.return_value = []
        mock_get_client.return_value = client

        # Test with --format json
        with patch("prusa.connect.client.cli.common.set_output_format") as mock_set, contextlib.suppress(SystemExit):
            # Use app.meta to handle global flags
            app.meta(["--format", "json", "printer", "list"])

            mock_set.assert_called_with("json")
