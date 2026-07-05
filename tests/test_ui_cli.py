from typer.testing import CliRunner

from handicap_ai.cli import app


def test_ui_command_exposes_host_port_and_db_options():
    result = CliRunner().invoke(app, ["ui", "--help"])

    assert result.exit_code == 0
    assert "--db" in result.output
    assert "--host" in result.output
    assert "--port" in result.output
