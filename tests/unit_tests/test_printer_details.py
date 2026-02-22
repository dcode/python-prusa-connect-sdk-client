import contextlib
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

cyclopts = pytest.importorskip("cyclopts")
better_excptions = pytest.importorskip("better_exceptions")

from prusa.connect.client import PrusaConnectClient  # noqa: E402
from prusa.connect.client.cli import app  # noqa: E402
from prusa.connect.client.models import FirmwareSupport, NetworkInfo, Printer, SlotInfo, Tool  # noqa: E402

# Sample data mimicking printer_details.json
SAMPLE_PRINTER_DETAILS = {
    "uuid": "3f4ce2a7-de2f-40a0-9514-d124b3d39403",
    "name": "Ministry of Silly Walks",
    "printer_state": "FINISHED",
    "printer_model": "Lumberjack-MK4",
    "firmware": "v1.0-Resting-Parrot",
    "last_online": 155433600.0,  # 1974-12-05 (Last Episode Air Date)
    "location": "Pet Shop",
    "team_name": "Spanish Inquisition",
    "network_info": {"lan_ipv4": "192.168.1.42", "hostname": "nudge-nudge"},
    "support": {"latest": "v2.0-Spam-Spam", "current": "v1.0-Resting-Parrot"},
    "tools": {"1": {"material": "Spam", "nozzle_diameter": 0.4, "fan_print": 0, "fan_hotend": 0}},
    "slot": {
        "active": 2,
        "slots": {"1": {"material": "PLA", "temp": 200}, "2": {"material": "PETG", "temp": 230}},
    },
    "axis_x": 10.5,
    "axis_y": 20.0,
    "axis_z": 30.0,
    "temp": {"temp_nozzle": 210.0, "temp_bed": 60.0},
}


def test_printer_model_parsing():
    """Verify that the Printer model parses the new fields correctly."""
    printer = Printer.model_validate(SAMPLE_PRINTER_DETAILS)

    expected = Printer.model_construct(
        _fields_set=None,
        **{
            "uuid": mock.ANY,
            "name": "Ministry of Silly Walks",
            "printer_state": mock.ANY,
            "printer_model": "Lumberjack-MK4",
            "firmware_version": "v1.0-Resting-Parrot",
            "last_online": pytest.approx(155433600.0),
            "network_info": NetworkInfo.model_construct(
                _fields_set=None,
                **{
                    "lan_ipv4": "192.168.1.42",
                    "hostname": "nudge-nudge",
                },
            ),
            "location": "Pet Shop",
            "slot": SlotInfo.model_construct(
                _fields_set=None,
                **{
                    "active": 2,
                    "slots": {
                        "1": mock.ANY,
                        "2": mock.ANY,
                    },
                },
            ),
            "support": FirmwareSupport.model_construct(
                _fields_set=None,
                **{
                    "latest": "v2.0-Spam-Spam",
                    "current": "v1.0-Resting-Parrot",
                },
            ),
            "team_name": "Spanish Inquisition",
            "tools": {
                "1": Tool.model_construct(
                    _fields_set=None, **{"material": "Spam", "nozzle_diameter": 0.4, "fan_print": 0, "fan_hotend": 0}
                )
            },
            "telemetry": mock.ANY,
            "axis_x": pytest.approx(10.5),
            "axis_y": pytest.approx(20.0),
            "axis_z": pytest.approx(30.0),
        },
    )

    assert expected == printer


@pytest.fixture
def mock_client():
    with patch("prusa.connect.client.cli.commands.printer.common.get_client") as mock:
        client = MagicMock(spec=PrusaConnectClient)
        client.printers = MagicMock()
        mock.return_value = client
        yield client


def test_cli_printer_show(mock_client):
    """Verify printer show command runs and likely outputs some of our new fields."""
    printer = Printer.model_validate(SAMPLE_PRINTER_DETAILS)
    mock_client.printers.get.return_value = printer

    # Run simple show
    with contextlib.suppress(SystemExit):
        app(["printer", "show", "uuid"], exit_on_error=False)

    mock_client.printers.get.assert_called_with("uuid")


def test_cli_printer_show_detailed(mock_client):
    """Verify printer show --detailed command."""
    printer = Printer.model_validate(SAMPLE_PRINTER_DETAILS)
    mock_client.printers.get.return_value = printer

    # Run detailed show
    with contextlib.suppress(SystemExit):
        app(["printer", "show", "uuid", "--detailed"], exit_on_error=False)

    mock_client.printers.get.assert_called_with("uuid")
