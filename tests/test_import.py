def test_package_import() -> None:
    import mobile_research

    assert mobile_research.__version__ == "0.1.0"
