def test_package_imports_with_version():
    import handicap_ai

    assert handicap_ai.__version__ == "0.1.0"


def test_cli_entrypoint_target_imports():
    from handicap_ai.cli import app

    assert app is not None
