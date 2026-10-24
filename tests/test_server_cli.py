"""Unit tests for server CLI entry point."""

import sys
from unittest.mock import patch

import pytest

from stack_scout.server import main


def test_cli_version(capsys):
    with patch.object(sys, "argv", ["stack-scout", "--version"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "stack-scout 0.1.0" in captured.out


def test_cli_help(capsys):
    with patch.object(sys, "argv", ["stack-scout", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Usage:" in captured.out


def test_cli_ping(capsys):
    with patch.object(sys, "argv", ["stack-scout", "ping"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "stack-scout v0.1.0 is active." in captured.out
