import contextlib
from unittest.mock import MagicMock, patch

import pytest

from prusa.connect.client import PrusaConnectClient
from prusa.connect.client.cli import app
from prusa.connect.client.models import Team

SAMPLE_TEAM = {"id": 1, "name": "Team A", "role": "OWNER", "organization_id": "00000000-0000-0000-0000-000000000001"}


@pytest.fixture
def mock_client():
    with patch("prusa.connect.client.cli.commands.team.common.get_client") as mock:
        client = MagicMock(spec=PrusaConnectClient)
        mock.return_value = client
        yield client


@pytest.fixture
def mock_settings():
    with patch("prusa.connect.client.cli.commands.team.config.settings") as s_mock:
        s_mock.default_team_id = 1
        yield s_mock


def test_team_list(mock_client):
    mock_client.get_teams.return_value = [Team.model_validate(SAMPLE_TEAM)]

    with contextlib.suppress(SystemExit):
        app(["team", "list"], exit_on_error=False)

    # Alias
    with contextlib.suppress(SystemExit):
        app(["teams"], exit_on_error=False)

    assert mock_client.get_teams.call_count == 2


def test_team_show(mock_client, mock_settings):
    team_data = {**SAMPLE_TEAM, "users": [{"id": 100, "username": "u1", "email": "u1@e.com", "rights_ro": True}]}
    mock_client.get_team.return_value = Team.model_validate(team_data)

    with contextlib.suppress(SystemExit):
        app(["team", "show"], exit_on_error=False)

    mock_client.get_team.assert_called_with(1)


def test_team_add_user(mock_client, mock_settings):
    mock_client.add_team_user.return_value = True

    with contextlib.suppress(SystemExit):
        app(["team", "add-user", "test@user.com", "--rights-rw"], exit_on_error=False)

    mock_client.add_team_user.assert_called_with(1, "test@user.com", True, False, True)


def test_set_current_team():
    with (
        patch("prusa.connect.client.cli.commands.team.config.save_json_config") as save_mock,
        patch("prusa.connect.client.cli.commands.team.config.settings") as s_mock,
    ):
        with contextlib.suppress(SystemExit):
            app(["team", "set-current", "2"], exit_on_error=False)
        assert s_mock.default_team_id == 2
        save_mock.assert_called()


def test_team_missing_id(mock_client):
    with patch("prusa.connect.client.cli.commands.team.config.settings") as s_mock:
        s_mock.default_team_id = None
        with pytest.raises(SystemExit) as e:
            app(["team", "show"], exit_on_error=False)
        assert e.value.code == 1
