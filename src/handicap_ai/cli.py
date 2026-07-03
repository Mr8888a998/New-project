from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Local football handicap analysis tool."""


if __name__ == "__main__":
    app()
