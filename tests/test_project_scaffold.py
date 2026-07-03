def test_package_imports_with_version():
    import handicap_ai

    assert handicap_ai.__version__ == "0.1.0"
