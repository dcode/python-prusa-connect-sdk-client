import contextlib
import logging
from unittest.mock import patch

import pytest

cyclopts = pytest.importorskip("cyclopts")
better_exceptions = pytest.importorskip("better_exceptions")

from prusa.connect.client.cli import main  # noqa: E402


@pytest.mark.parametrize(
    "args,expected_level",
    [
        (["printer", "list", "--verbose"], logging.INFO),
        (["--verbose", "printer", "list"], logging.INFO),
        (["printer", "list"], logging.WARNING),
        (["--debug", "printer", "list"], logging.DEBUG),
        (["--verbose", "printer", "list", "--debug"], logging.DEBUG),
    ],
)
def test_logging_levels(args, expected_level):
    # We patch structlog.make_filtering_bound_logger to capture the level passed
    with (
        patch("prusa.connect.client.cli.common.structlog.make_filtering_bound_logger") as mock_maker,
        contextlib.suppress(SystemExit),
        # We expect deprecation warnings because the CLI commands use deprecated client methods
        pytest.warns(DeprecationWarning, match="get_printers"),
    ):
        main(args)

        # We expect at least one call to configure logging with expected level
        # If args have flags, main calls it.
        # Then command calls it (with defaults).
        # We need to ensure the "most verbose" setting won?
        # Actually our logic is: Main sets it. Command inherits it.
        # So check if ANY call used expected_level?
        # Or check the FINAL state?
        # Since we mock the factory, we can't check final state easily unless we mock configure_logging

        calls = mock_maker.call_args_list
        # If defaults (WARN), main might NOT call it. Command calls it with None (defaults to WARN if first run).
        # If explicit, main calls it.

        # We want to verified that the LAST EFFECTIVE call matches.
        # But if command calls with None -> it returns early!
        # So we might check if make_filtering_bound_logger was called with expected level AT ALL
        # and subsequent calls didn't overwrite it with something else (except returning).

        # Filter calls that actually passed a level
        levels_set = [c[0][0] for c in calls if c[0]]

        # If list is empty, it means no configuration?
        # But command calls configure(None, None) which calls... Wait!
        # configure(None, None) returns if initialized.
        # If we reset initialized fixture, then first call initializes it.

        if not levels_set:
            # Should happen?
            # Defaults: None, None -> Falbacks to False, False -> Sets WARN (30)
            # logging.WARNING is 30.
            assert expected_level == logging.WARNING
        else:
            # We expect the Set level to match.
            # If Main sets INFO (20). Command calls (None). Returns.
            # levels_set = [20].
            # If Main sets nothing. Command sets WARN.
            # levels_set = [30].

            # If multiple calls? e.g. main sets INFO. Command sets INFO?
            # Command gets None.

            assert levels_set[-1] == expected_level
