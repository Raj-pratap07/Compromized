from __future__ import annotations

import sys

import pytest

from scripts import demo


@pytest.mark.parametrize("flags", [["--plain"], []], ids=["plain", "unicode"])
def test_offline_demo_fails_with_one_share_and_succeeds_with_two_and_three(monkeypatch, capsys, flags):
    monkeypatch.setattr(sys, "argv", ["demo", "--auto", "--secret", "CANARY-demo-secret-123", *flags])

    exit_code = demo.main()

    output = capsys.readouterr().out
    assert exit_code == 0, output
    rounds = output.split("ROUND ")[1:]
    assert len(rounds) == 3
    assert "CANNOT REBUILD" in rounds[0] and "SECRET REBUILT" not in rounds[0]
    assert "SECRET REBUILT: " in rounds[1] and "CANARY-demo-secret-123" in rounds[1]
    assert "SECRET REBUILT from every pair" in rounds[2] and "1+2" in rounds[2] and "2+3" in rounds[2]
    assert "deleted from all 3 clouds" in output
    assert "UNEXPECTED" not in output and "ERROR CORE" not in output
    assert max(len(line) for line in output.splitlines()) <= 78  # never wraps in a normal terminal
