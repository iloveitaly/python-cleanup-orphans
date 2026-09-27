"""Test python-cleanup-orphans."""

import python_cleanup_orphans


def test_import() -> None:
    """Test that the  can be imported."""
    assert isinstance(python_cleanup_orphans.__name__, str)


def test_version() -> None:
    """Test that the version is available."""
    assert isinstance(python_cleanup_orphans.__version__, str)