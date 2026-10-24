"""Unit tests for server CLI entry point."""

import sys
from unittest.mock import patch

import pytest

from skills_but_for_dev import __version__
from skills_but_for_dev.server import main


def test_cli_version(capsys):
    with patch.object(sys, "argv", ["skills-but-for-dev", "--version"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert f"skills-but-for-dev {__version__}" in captured.out


def test_cli_help(capsys):
    with patch.object(sys, "argv", ["skills-but-for-dev", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Usage:" in captured.out


def test_cli_ping(capsys):
    with patch.object(sys, "argv", ["skills-but-for-dev", "ping"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert f"skills-but-for-dev v{__version__} is active." in captured.out

